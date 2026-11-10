"""
Module de capture audio en temps réel via sounddevice avec gestion robuste des erreurs,
détection des périphériques et générateur de signaux synthétiques pour tests sans micro.
"""

import sys
import time
import threading
from typing import Optional, List, Dict, Tuple, Callable
import numpy as np

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except Exception as e:
    SOUNDDEVICE_AVAILABLE = False
    _sd_error = str(e)

from src.utils.constants import DEFAULT_SAMPLE_RATE, DEFAULT_BUFFER_SIZE


class AudioCaptureDevice:
    """
    Gestionnaire de capture audio en streaming temps réel basé sur sounddevice.
    Gère les callbacks non-bloquants, les déconnexions matérielles et les signaux de test.
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        block_size: int = DEFAULT_BUFFER_SIZE,
        device_index: Optional[int] = None,
        callback: Optional[Callable[[np.ndarray], None]] = None
    ):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.device_index = device_index
        self.user_callback = callback
        
        self.stream: Optional[sd.InputStream] = None
        self.is_running = False
        self.is_synthetic_mode = False
        self.error_message: Optional[str] = None
        
        # Variables pour le générateur synthétique
        self._synthetic_thread: Optional[threading.Thread] = None
        self._synthetic_stop_event = threading.Event()
        self._synth_freq = 440.0
        self._synth_waveform = 'harmonics'  # 'sine', 'harmonics', 'noisy', 'missing_fundamental'
        self._synth_noise_level = 0.02
        self._synth_amplitude = 0.8

    @staticmethod
    def get_available_devices() -> List[Dict[str, any]]:
        """
        Liste l'ensemble des périphériques d'entrée audio disponibles sur le système.
        """
        if not SOUNDDEVICE_AVAILABLE:
            return []
            
        devices_list = []
        try:
            device_infos = sd.query_devices()
            default_input = sd.default.device[0]
            
            for idx, dev in enumerate(device_infos):
                # Filtrer uniquement les périphériques d'entrée audio (au moins 1 canal d'entrée)
                if dev.get('max_input_channels', 0) > 0:
                    devices_list.append({
                        'index': idx,
                        'name': dev.get('name', f'Device {idx}'),
                        'channels': dev.get('max_input_channels', 1),
                        'default_samplerate': int(dev.get('default_samplerate', 44100)),
                        'is_default': (idx == default_input)
                    })
        except Exception as e:
            pass
            
        return devices_list

    def set_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        """Définit la fonction callback appelée lors de la réception d'un bloc audio."""
        self.user_callback = callback

    def _audio_stream_callback(self, indata, frames, time_info, status):
        """Callback interne appelé en temps réel par le pilote audio PortAudio/sounddevice."""
        if status:
            # En cas de buffer overflow ou underflow
            pass
            
        if self.is_running and self.user_callback is not None:
            # Conversion en mono 1D float32
            mono_data = np.copy(indata[:, 0]) if indata.ndim > 1 else np.copy(indata)
            self.user_callback(mono_data)

    def start(self, device_index: Optional[int] = None) -> bool:
        """
        Démarre l'acquisition audio depuis le microphone sélectionné.
        
        Returns:
            bool: True si démarré avec succès, False sinon.
        """
        if self.is_running:
            return True
            
        if device_index is not None:
            self.device_index = device_index
            
        self.error_message = None
        self.is_synthetic_mode = False
        
        if not SOUNDDEVICE_AVAILABLE:
            self.error_message = f"Bibliothèque sounddevice indisponible : {_sd_error}"
            return False
            
        try:
            self.stream = sd.InputStream(
                device=self.device_index,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                dtype='float32',
                callback=self._audio_stream_callback
            )
            self.stream.start()
            self.is_running = True
            return True
        except Exception as exc:
            self.error_message = f"Impossible d'ouvrir le périphérique audio : {str(exc)}"
            self.is_running = False
            self.stream = None
            return False

    def stop(self) -> None:
        """Arrête la capture audio du microphone ou le générateur synthétique."""
        self.is_running = False
        
        # Arrêt du flux matériel
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            finally:
                self.stream = None
                
        # Arrêt du générateur synthétique
        if self._synthetic_thread is not None and self._synthetic_thread.is_alive():
            self._synthetic_stop_event.set()
            self._synthetic_thread.join(timeout=1.0)
            self._synthetic_thread = None
            
        self.is_synthetic_mode = False

    def start_synthetic_mode(
        self,
        frequency: float = 440.0,
        waveform: str = 'harmonics',
        noise_level: float = 0.02
    ) -> bool:
        """
        Démarre la génération continue d'un signal audio synthétique.
        Permet de tester et valider l'accordeur et le traitement FFT
        sans dépendre d'un microphone physique.
        """
        self.stop()
        
        self._synth_freq = frequency
        self._synth_waveform = waveform
        self._synth_noise_level = noise_level
        self.is_synthetic_mode = True
        self.is_running = True
        self._synthetic_stop_event.clear()
        
        self._synthetic_thread = threading.Thread(
            target=self._synthetic_loop,
            daemon=True,
            name="SyntheticAudioWorker"
        )
        self._synthetic_thread.start()
        return True

    def set_synthetic_parameters(
        self,
        frequency: Optional[float] = None,
        waveform: Optional[str] = None,
        noise_level: Optional[float] = None
    ) -> None:
        """Met à jour en temps réel les propriétés du signal de synthèse."""
        if frequency is not None:
            self._synth_freq = frequency
        if waveform is not None:
            self._synth_waveform = waveform
        if noise_level is not None:
            self._synth_noise_level = noise_level

    def _synthetic_loop(self) -> None:
        """Boucle de streaming du signal audio de test synthétique."""
        phase = 0.0
        dt = 1.0 / self.sample_rate
        sleep_interval = self.block_size / self.sample_rate * 0.90
        
        while not self._synthetic_stop_event.is_set():
            t = np.arange(self.block_size) * dt + phase
            phase = (phase + self.block_size * dt) % (2.0 * np.pi)
            
            f = self._synth_freq
            
            if self._synth_waveform == 'sine':
                # Sinusoïde pure
                data = self._synth_amplitude * np.sin(2.0 * np.pi * f * t)
            elif self._synth_waveform == 'harmonics':
                # Timbre riche type guitare/corde (Fondamentale + harmoniques décroissantes)
                data = (
                    0.60 * np.sin(2.0 * np.pi * f * t) +
                    0.30 * np.sin(2.0 * np.pi * 2 * f * t) +
                    0.15 * np.sin(2.0 * np.pi * 3 * f * t) +
                    0.08 * np.sin(2.0 * np.pi * 4 * f * t)
                )
            elif self._synth_waveform == 'missing_fundamental':
                # Fondamentale atténuée (f0 atténuée, harmoniques 2f0 et 3f0 prédominantes)
                data = (
                    0.05 * np.sin(2.0 * np.pi * f * t) +
                    0.60 * np.sin(2.0 * np.pi * 2 * f * t) +
                    0.40 * np.sin(2.0 * np.pi * 3 * f * t) +
                    0.20 * np.sin(2.0 * np.pi * 4 * f * t)
                )
            else:
                data = self._synth_amplitude * np.sin(2.0 * np.pi * f * t)
                
            # Ajout de bruit gaussien blanc
            if self._synth_noise_level > 0:
                noise = np.random.normal(0, self._synth_noise_level, self.block_size)
                data = data + noise
                
            data = np.clip(data, -1.0, 1.0).astype(np.float32)
            
            if self.user_callback is not None:
                self.user_callback(data)
                
            time.sleep(sleep_interval)
