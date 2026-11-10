"""
Module d'estimation et d'extraction de la fréquence fondamentale (Pitch Detection).
Intègre l'algorithme YIN (De Cheveigné & Kawahara), le spectre de produit harmonique (HPS),
l'autocorrélation normalisée (ACF) et l'analyse FFT interpolée.
"""

from typing import Tuple, Optional, List, Dict, Any, Literal
from dataclasses import dataclass
import numpy as np

from src.utils.constants import (
    MIN_AUDIO_FREQ,
    MAX_AUDIO_FREQ,
    DEFAULT_RMS_GATE,
    DEFAULT_SILENCE_THRESHOLD_DB
)
from src.signal.fourier import compute_fft_spectrum, parabolic_interpolation


@dataclass
class PitchDetectionResult:
    """Structure contenant les résultats complets de l'estimation de pitch."""
    frequency: float               # Fréquence fondamentale estimée en Hz (0.0 si silence/bruit)
    confidence: float              # Indice de confiance entre 0.0 (incertain/bruit) et 1.0 (très pur)
    rms_level: float               # Énergie RMS linéaire du signal analysé
    rms_db: float                  # Niveau RMS en décibels pleine échelle (dB FS)
    is_voiced: bool                # Vrai si le signal est considéré comme musical / périodique
    method: str                    # Algorithme utilisé ('yin', 'hps', 'autocorr', 'fft_peak')
    harmonics: List[float]         # Fréquences des harmoniques détectées


def compute_rms(signal: np.ndarray) -> Tuple[float, float]:
    """
    Calcule la valeur efficace RMS (Root Mean Square) linéaire et en dB FS.
    
    Args:
        signal (np.ndarray): Signal temporel 1D.
        
    Returns:
        Tuple[float, float]: (rms_lineaire, rms_db_fs)
    """
    if len(signal) == 0:
        return 0.0, -120.0
        
    rms = float(np.sqrt(np.mean(signal ** 2)))
    eps = 1e-12
    rms_db = float(20.0 * np.log10(max(rms, eps)))
    return rms, rms_db


def yin_pitch_estimator(
    signal: np.ndarray,
    sample_rate: int,
    min_freq: float = MIN_AUDIO_FREQ,
    max_freq: float = MAX_AUDIO_FREQ,
    threshold: float = 0.15
) -> Tuple[float, float]:
    """
    Algorithme YIN pour l'estimation robuste de la fréquence fondamentale (F0).
    
    Référence scientifique :
    Alain de Cheveigné & Hideki Kawahara (2002), "YIN, a fundamental frequency
    estimator for speech and music", J. Acoust. Soc. Am. 111, 1917-1930.
    
    Étapes de l'algorithme :
    1. Fonction de différence quadratique d_t(tau).
    2. Fonction de différence cumulée normalisée d'_t(tau) (CMNDF).
    3. Seuil absolu (évite les erreurs d'octave et de sous-harmoniques).
    4. Interpolation parabolique au fond de la cuvette pour une précision sub-échantillon.
    
    Args:
        signal (np.ndarray): Signal audio temporel.
        sample_rate (int): Fréquence d'échantillonnage en Hz.
        min_freq (float): Fréquence minimale mesurable (ex: 30 Hz).
        max_freq (float): Fréquence maximale mesurable (ex: 4000 Hz).
        threshold (float): Seuil de validation YIN (généralement entre 0.10 et 0.20).
        
    Returns:
        Tuple[float, float]: (fréquence_f0_hz, confiance [0.0 - 1.0])
    """
    N = len(signal)
    if N < 4:
        return 0.0, 0.0
        
    # Calcul des retards (tau) min et max selon les bornes de fréquence
    tau_min = int(sample_rate / max_freq)
    tau_max = int(sample_rate / min_freq)
    
    # Sécuriser les bornes par rapport à la taille de la fenêtre
    tau_min = max(2, tau_min)
    tau_max = min(N // 2, tau_max)
    
    if tau_min >= tau_max:
        return 0.0, 0.0
        
    # Fenêtre d'intégration W
    W = N - tau_max
    if W <= 0:
        return 0.0, 0.0
        
    # ---------------------------------------------------------
    # Étape 1 : Fonction de différence d(tau)
    # d(tau) = sum_{j=0}^{W-1} (x[j] - x[j + tau])^2
    # ---------------------------------------------------------
    d = np.zeros(tau_max + 1, dtype=np.float64)
    x = signal.astype(np.float64)
    x_base = x[:W]
    
    for tau in range(1, tau_max + 1):
        diff = x_base - x[tau:W + tau]
        d[tau] = np.sum(diff * diff)
        
    # ---------------------------------------------------------
    # Étape 2 : Fonction de différence cumulée normalisée d'(tau)
    # d'(0) = 1
    # d'(tau) = d(tau) / [ (1/tau) * sum_{j=1}^tau d(j) ]
    # ---------------------------------------------------------
    d_prime = np.zeros(tau_max + 1, dtype=np.float64)
    d_prime[0] = 1.0
    running_sum = 0.0
    
    for tau in range(1, tau_max + 1):
        running_sum += d[tau]
        if running_sum > 1e-12:
            d_prime[tau] = d[tau] / (running_sum / tau)
        else:
            d_prime[tau] = 1.0
            
    # ---------------------------------------------------------
    # Étape 3 : Détection du premier creux sous le seuil absolu
    # ---------------------------------------------------------
    best_tau = -1
    for tau in range(tau_min, tau_max):
        if d_prime[tau] < threshold:
            # Chercher le minimum local dans cette cuvette
            while tau + 1 < tau_max and d_prime[tau + 1] < d_prime[tau]:
                tau += 1
            best_tau = tau
            break
            
    # Si aucun minimum n'est sous le seuil, prendre le minimum absolu dans l'intervalle
    if best_tau == -1:
        best_tau = tau_min + int(np.argmin(d_prime[tau_min:tau_max]))
        # Si même le minimum global reste trop élevé (> 0.85), c'est du bruit non périodique
        if d_prime[best_tau] > 0.85:
            return 0.0, 0.0
            
    # ---------------------------------------------------------
    # Étape 4 : Interpolation parabolique au voisinage du creux
    # ---------------------------------------------------------
    if 0 < best_tau < tau_max:
        alpha = d_prime[best_tau - 1]
        beta = d_prime[best_tau]
        gamma = d_prime[best_tau + 1]
        denom = alpha - 2.0 * beta + gamma
        if abs(denom) > 1e-12:
            delta = 0.5 * (alpha - gamma) / denom
            delta = np.clip(delta, -0.5, 0.5)
            refined_tau = best_tau + delta
        else:
            refined_tau = float(best_tau)
    else:
        refined_tau = float(best_tau)
        
    if refined_tau <= 0:
        return 0.0, 0.0
        
    f0 = sample_rate / refined_tau
    confidence = float(np.clip(1.0 - d_prime[best_tau], 0.0, 1.0))
    
    if min_freq <= f0 <= max_freq:
        return f0, confidence
    return 0.0, 0.0


def harmonic_product_spectrum_estimator(
    signal: np.ndarray,
    sample_rate: int,
    num_harmonics: int = 4,
    min_freq: float = MIN_AUDIO_FREQ,
    max_freq: float = MAX_AUDIO_FREQ
) -> Tuple[float, float]:
    """
    Estimation de pitch par spectre de produit harmonique (HPS - Harmonic Product Spectrum).
    
    Particulièrement efficace lorsqu'une note possède une fondamentale faible
    ou manquante (missing fundamental) mais des harmoniques riches (2f0, 3f0...).
    
    Formule :
        HPS(k) = prod_{r=1}^{R} |X[r * k]|
        
    Args:
        signal (np.ndarray): Signal audio temporel.
        sample_rate (int): Fréquence d'échantillonnage en Hz.
        num_harmonics (int): Nombre de compressions harmoniques R (3 à 5 usuel).
        min_freq (float): Fréquence minimale d'analyse.
        max_freq (float): Fréquence maximale d'analyse.
        
    Returns:
        Tuple[float, float]: (fréquence_f0_hz, confiance)
    """
    N = len(signal)
    if N < 64:
        return 0.0, 0.0
        
    freqs, mags, _ = compute_fft_spectrum(signal, sample_rate, window_type='hamming', zero_padding_factor=2)
    
    L = len(mags)
    max_bin = L // num_harmonics
    if max_bin <= 1:
        return 0.0, 0.0
        
    # Produit des spectres décimés
    hps_spectrum = np.copy(mags[:max_bin])
    for r in range(2, num_harmonics + 1):
        decimated = mags[::r][:max_bin]
        hps_spectrum *= decimated
        
    df = freqs[1] - freqs[0] if len(freqs) > 1 else 1.0
    min_bin = max(1, int(min_freq / df))
    max_search_bin = min(max_bin - 1, int(max_freq / df))
    
    if min_bin >= max_search_bin:
        return 0.0, 0.0
        
    peak_bin = min_bin + int(np.argmax(hps_spectrum[min_bin:max_search_bin]))
    
    # Interpolation parabolique
    refined_bin, _ = parabolic_interpolation(hps_spectrum, peak_bin)
    f0 = refined_bin * df
    
    # Calcul d'un indice de confiance basé sur la proéminence du pic HPS
    peak_val = hps_spectrum[peak_bin]
    mean_val = np.mean(hps_spectrum[min_bin:max_search_bin]) + 1e-12
    prominence_ratio = peak_val / mean_val
    confidence = float(np.clip((prominence_ratio - 1.5) / 5.0, 0.0, 1.0))
    
    if min_freq <= f0 <= max_freq:
        return f0, confidence
    return 0.0, 0.0


def autocorrelation_pitch_estimator(
    signal: np.ndarray,
    sample_rate: int,
    min_freq: float = MIN_AUDIO_FREQ,
    max_freq: float = MAX_AUDIO_FREQ
) -> Tuple[float, float]:
    """
    Estimation de pitch par fonction d'autocorrélation normalisée (ACF).
    
    Args:
        signal (np.ndarray): Signal audio temporel.
        sample_rate (int): Fréquence d'échantillonnage en Hz.
        min_freq (float): Fréquence minimale.
        max_freq (float): Fréquence maximale.
        
    Returns:
        Tuple[float, float]: (fréquence_f0_hz, confiance)
    """
    N = len(signal)
    if N < 64:
        return 0.0, 0.0
        
    x = signal - np.mean(signal)
    
    # Autocorrélation rapide via FFT : R_xx = ifft(|fft(x)|^2)
    n_fft = 2 ** int(np.ceil(np.log2(2 * N - 1)))
    fx = np.fft.fft(x, n=n_fft)
    rxx = np.fft.ifft(fx * np.conj(fx)).real[:N]
    
    r0 = rxx[0]
    if r0 <= 1e-12:
        return 0.0, 0.0
    rxx /= r0  # Normalisation pour avoir R_xx(0) = 1.0
    
    tau_min = max(2, int(sample_rate / max_freq))
    tau_max = min(N - 1, int(sample_rate / min_freq))
    
    if tau_min >= tau_max:
        return 0.0, 0.0
        
    # Recherche du maximum entre tau_min et tau_max
    search_region = rxx[tau_min:tau_max]
    peak_offset = int(np.argmax(search_region))
    peak_tau = tau_min + peak_offset
    
    # Interpolation parabolique
    refined_tau, refined_rxx = parabolic_interpolation(rxx, peak_tau)
    if refined_tau <= 0:
        return 0.0, 0.0
        
    f0 = sample_rate / refined_tau
    confidence = float(np.clip(refined_rxx, 0.0, 1.0))
    
    if min_freq <= f0 <= max_freq:
        return f0, confidence
    return 0.0, 0.0


def find_harmonic_peaks(
    f0: float,
    frequencies: np.ndarray,
    magnitudes: np.ndarray,
    max_harmonics: int = 6,
    tolerance_pct: float = 0.05
) -> List[float]:
    """
    Recherche la présence des harmoniques multiples entiers k * f0 dans le spectre.
    
    Args:
        f0: Fréquence fondamentale estimée.
        frequencies: Tableau des fréquences FFT.
        magnitudes: Tableau des amplitudes spectrales.
        max_harmonics: Nombre d'harmoniques à chercher (2f0, 3f0...).
        tolerance_pct: Tolérance en pourcentage autour de k * f0 (ex: 5%).
        
    Returns:
        List[float]: Liste des fréquences harmoniques détectées.
    """
    if f0 <= 0 or len(frequencies) < 2:
        return []
        
    harmonics = []
    df = frequencies[1] - frequencies[0]
    
    for k in range(2, max_harmonics + 1):
        target_f = k * f0
        if target_f > frequencies[-1]:
            break
            
        f_min = target_f * (1.0 - tolerance_pct)
        f_max = target_f * (1.0 + tolerance_pct)
        
        mask = (frequencies >= f_min) & (frequencies <= f_max)
        indices = np.where(mask)[0]
        if len(indices) > 0:
            local_peak_idx = indices[np.argmax(magnitudes[indices])]
            refined_idx, _ = parabolic_interpolation(magnitudes, local_peak_idx)
            harmonics.append(float(refined_idx * df))
            
    return harmonics


class PitchDetector:
    """
    Moteur unifié de détection de pitch avec filtrage, seuillage du bruit
    et choix de l'algorithme d'analyse.
    """
    
    def __init__(
        self,
        sample_rate: int = 44100,
        default_method: str = "yin",
        rms_gate: float = DEFAULT_RMS_GATE,
        min_freq: float = MIN_AUDIO_FREQ,
        max_freq: float = MAX_AUDIO_FREQ,
        confidence_threshold: float = 0.50
    ):
        self.sample_rate = sample_rate
        self.method = default_method
        self.rms_gate = rms_gate
        self.min_freq = min_freq
        self.max_freq = max_freq
        self.confidence_threshold = confidence_threshold
        
    def set_sample_rate(self, sample_rate: int) -> None:
        """Met à jour la fréquence d'échantillonnage."""
        self.sample_rate = sample_rate
        
    def set_method(self, method: str) -> None:
        """Définit la méthode ('yin', 'hps', 'autocorr', 'fft_peak', 'hybrid')."""
        if method not in ('yin', 'hps', 'autocorr', 'fft_peak', 'hybrid'):
            raise ValueError(f"Méthode inconnue : {method}")
        self.method = method
        
    def set_rms_gate(self, gate: float) -> None:
        """Modifie le seuil de sensibilité au silence."""
        self.rms_gate = max(0.0001, gate)

    def analyze(self, signal: np.ndarray) -> PitchDetectionResult:
        """
        Analyse une trame audio temporelle et extrait la fréquence fondamentale.
        
        Args:
            signal (np.ndarray): Trame d'échantillons audio réels (mono).
            
        Returns:
            PitchDetectionResult: Objet contenant la fréquence, confiance, RMS, etc.
        """
        rms_val, rms_db = compute_rms(signal)
        
        # 1. Porte de bruit (Noise Gate)
        if rms_val < self.rms_gate:
            return PitchDetectionResult(
                frequency=0.0,
                confidence=0.0,
                rms_level=rms_val,
                rms_db=rms_db,
                is_voiced=False,
                method=self.method,
                harmonics=[]
            )
            
        freq = 0.0
        conf = 0.0
        
        # 2. Exécution selon la méthode configurée
        if self.method == 'yin':
            freq, conf = yin_pitch_estimator(
                signal, self.sample_rate, self.min_freq, self.max_freq
            )
        elif self.method == 'hps':
            freq, conf = harmonic_product_spectrum_estimator(
                signal, self.sample_rate, num_harmonics=4, min_freq=self.min_freq, max_freq=self.max_freq
            )
        elif self.method == 'autocorr':
            freq, conf = autocorrelation_pitch_estimator(
                signal, self.sample_rate, self.min_freq, self.max_freq
            )
        elif self.method == 'fft_peak':
            freqs, mags, _ = compute_fft_spectrum(signal, self.sample_rate, window_type='hamming')
            valid_mask = (freqs >= self.min_freq) & (freqs <= self.max_freq)
            if np.any(valid_mask):
                valid_mags = mags[valid_mask]
                valid_freqs = freqs[valid_mask]
                peak_idx = np.argmax(valid_mags)
                global_peak_idx = np.where(valid_mask)[0][peak_idx]
                ref_idx, _ = parabolic_interpolation(mags, global_peak_idx)
                df = freqs[1] - freqs[0]
                freq = ref_idx * df
                conf = float(np.clip(valid_mags[peak_idx] * 5.0, 0.1, 0.95))
        elif self.method == 'hybrid':
            # Méthode hybride : YIN assisté par validation HPS
            f_yin, c_yin = yin_pitch_estimator(signal, self.sample_rate, self.min_freq, self.max_freq)
            f_hps, c_hps = harmonic_product_spectrum_estimator(signal, self.sample_rate, 4, self.min_freq, self.max_freq)
            
            if c_yin >= 0.65:
                freq, conf = f_yin, c_yin
            elif c_hps >= 0.70:
                freq, conf = f_hps, c_hps
            else:
                freq, conf = (f_yin, c_yin) if c_yin >= c_hps else (f_hps, c_hps)
                
        # 3. Validation de confiance
        is_voiced = (freq > 0.0) and (conf >= self.confidence_threshold)
        
        # 4. Identification des harmoniques si une note périodique est validée
        harmonics = []
        if is_voiced:
            freqs, mags, _ = compute_fft_spectrum(signal, self.sample_rate, window_type='hamming')
            harmonics = find_harmonic_peaks(freq, freqs, mags)
            
        return PitchDetectionResult(
            frequency=freq if is_voiced else 0.0,
            confidence=conf,
            rms_level=rms_val,
            rms_db=rms_db,
            is_voiced=is_voiced,
            method=self.method,
            harmonics=harmonics
        )
