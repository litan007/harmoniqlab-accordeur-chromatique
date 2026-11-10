"""
Module d'orchestration du traitement du signal audio en continu.
Gère le tampon circulaire (ring buffer), le calcul de la FFT,
l'extraction de pitch et la conversion en note musicale en temps réel.
"""

from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass
import numpy as np

from src.utils.constants import (
    DEFAULT_SAMPLE_RATE,
    DEFAULT_BUFFER_SIZE,
    DEFAULT_CONCERT_PITCH_A4
)
from src.signal.fourier import compute_fft_spectrum, find_spectral_peaks
from src.signal.frequency_detector import PitchDetector, PitchDetectionResult
from src.signal.note_converter import NoteConverter, NoteInfo
from src.audio.microphone import AudioCaptureDevice


@dataclass
class AudioAnalysisFrame:
    """Paquet complet de données généré pour chaque trame d'analyse en temps réel."""
    raw_signal: np.ndarray             # Signal temporel récent
    windowed_signal: np.ndarray        # Signal après application de la fenêtre (Hamming)
    sample_rate: int                   # Fréquence d'échantillonnage
    frequencies: np.ndarray            # Axe fréquentiel FFT (Hz)
    magnitudes_linear: np.ndarray      # Spectre d'amplitude linéaire
    magnitudes_db: np.ndarray          # Spectre en décibels
    pitch_result: PitchDetectionResult # Données de fréquence fondamentale et confiance
    note_info: Optional[NoteInfo]      # Données de la note musicale identifiée (ou None si silence)
    peaks: List[Tuple[float, float]]   # Liste des pics fréquentiels majeurs [(freq, mag)]


class AudioProcessor:
    """
    Processeur audio central connectant la capture microphonique au pipeline DSP.
    Assure un tamponnement circulaire fluide et distribue les résultats d'analyse.
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        concert_pitch: float = DEFAULT_CONCERT_PITCH_A4,
        window_type: str = 'hamming',
        pitch_method: str = 'yin'
    ):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.window_type = window_type
        
        # Sous-systèmes DSP
        self.pitch_detector = PitchDetector(
            sample_rate=self.sample_rate,
            default_method=pitch_method
        )
        self.note_converter = NoteConverter(concert_pitch_a4=concert_pitch)
        self.capture_device = AudioCaptureDevice(
            sample_rate=self.sample_rate,
            block_size=1024,
            callback=self._on_audio_data_received
        )
        
        # Tampon circulaire (ring buffer) d'échantillons
        self._ring_buffer = np.zeros(self.buffer_size, dtype=np.float32)
        self._buffer_lock = False
        
        # Callbacks pour notifications (ex: interface graphique)
        self._frame_callbacks: List[Callable[[AudioAnalysisFrame], None]] = []

    def register_callback(self, callback: Callable[[AudioAnalysisFrame], None]) -> None:
        """Enregistre une fonction recevant chaque trame d'analyse calculée."""
        if callback not in self._frame_callbacks:
            self._frame_callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[AudioAnalysisFrame], None]) -> None:
        """Désenregistre une fonction callback."""
        if callback in self._frame_callbacks:
            self._frame_callbacks.remove(callback)

    def set_sample_rate(self, sample_rate: int) -> None:
        """Configure la fréquence d'échantillonnage."""
        self.sample_rate = sample_rate
        self.pitch_detector.set_sample_rate(sample_rate)
        self.capture_device.sample_rate = sample_rate

    def set_pitch_method(self, method: str) -> None:
        """Définit la méthode de détection de pitch ('yin', 'hps', 'autocorr', 'fft_peak', 'hybrid')."""
        self.pitch_detector.set_method(method)

    def set_concert_pitch(self, pitch_hz: float) -> None:
        """Modifie le diapason de référence (La4)."""
        self.note_converter.set_concert_pitch(pitch_hz)

    def set_window_type(self, window_type: str) -> None:
        """Modifie le type de fenêtre d'analyse spectrale ('hamming', 'hann', 'blackman')."""
        self.window_type = window_type

    def set_rms_gate(self, gate: float) -> None:
        """Modifie le seuil de sensibilité au silence."""
        self.pitch_detector.set_rms_gate(gate)

    def start_listening(self, device_index: Optional[int] = None) -> bool:
        """Démarre l'acquisition sur le microphone."""
        return self.capture_device.start(device_index)

    def stop_listening(self) -> None:
        """Arrête l'acquisition."""
        self.capture_device.stop()

    def start_synthetic_generator(
        self,
        frequency: float = 440.0,
        waveform: str = 'harmonics',
        noise_level: float = 0.02
    ) -> bool:
        """Démarre le générateur de signal de test synthétique."""
        return self.capture_device.start_synthetic_mode(
            frequency=frequency,
            waveform=waveform,
            noise_level=noise_level
        )

    def update_synthetic_generator(
        self,
        frequency: Optional[float] = None,
        waveform: Optional[str] = None,
        noise_level: Optional[float] = None
    ) -> None:
        """Met à jour les paramètres de synthèse sans interrompre la lecture."""
        self.capture_device.set_synthetic_parameters(
            frequency=frequency,
            waveform=waveform,
            noise_level=noise_level
        )

    def _on_audio_data_received(self, chunk: np.ndarray) -> None:
        """
        Callback déclenché lors de la réception d'un nouveau bloc audio.
        Met à jour le tampon circulaire et déclenche l'analyse DSP.
        """
        chunk_len = len(chunk)
        if chunk_len == 0:
            return
            
        # Décalage circulaire à gauche et insertion des nouveaux échantillons
        if chunk_len >= self.buffer_size:
            self._ring_buffer = np.copy(chunk[-self.buffer_size:])
        else:
            self._ring_buffer = np.roll(self._ring_buffer, -chunk_len)
            self._ring_buffer[-chunk_len:] = chunk
            
        # Exécution de l'analyse DSP sur la fenêtre actuelle
        frame = self.process_frame(self._ring_buffer)
        
        # Diffusion de la trame aux observateurs enregistrés
        for cb in self._frame_callbacks:
            try:
                cb(frame)
            except Exception:
                pass

    def process_frame(self, signal: np.ndarray) -> AudioAnalysisFrame:
        """
        Exécute la chaîne mathématique complète de traitement du signal sur un vecteur audio :
        1. Fenêtrage (Hamming par défaut).
        2. Calcul FFT unilatérale & spectre en amplitude et en dB.
        3. Extraction des pics spectraux.
        4. Détection robuste de la fréquence fondamentale (F0).
        5. Conversion en note chromatique et écart en Cents.
        """
        # 1. Calcul du spectre FFT
        frequencies, mags_lin, mags_db = compute_fft_spectrum(
            signal=signal,
            sample_rate=self.sample_rate,
            window_type=self.window_type,
            zero_padding_factor=2
        )
        
        # 2. Détection de la fréquence fondamentale
        pitch_res = self.pitch_detector.analyze(signal)
        
        # 3. Conversion en note musicale
        note_info: Optional[NoteInfo] = None
        if pitch_res.is_voiced and pitch_res.frequency > 0.0:
            note_info = self.note_converter.convert_frequency(pitch_res.frequency)
            
        # 4. Extraction des pics fréquentiels
        peaks = find_spectral_peaks(
            frequencies=frequencies,
            magnitudes=mags_lin,
            min_magnitude=0.015,
            min_freq=30.0,
            max_freq=3500.0,
            max_peaks=8
        )
        
        # Calcul du signal fenêtré pour affichage temporel
        from src.signal.fourier import get_window
        win = get_window(self.window_type, len(signal))
        windowed = (signal - np.mean(signal)) * win
        
        return AudioAnalysisFrame(
            raw_signal=signal.copy(),
            windowed_signal=windowed,
            sample_rate=self.sample_rate,
            frequencies=frequencies,
            magnitudes_linear=mags_lin,
            magnitudes_db=mags_db,
            pitch_result=pitch_res,
            note_info=note_info,
            peaks=peaks
        )
