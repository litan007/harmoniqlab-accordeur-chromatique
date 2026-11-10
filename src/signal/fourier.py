"""
Module de calcul de la Transformée de Fourier Discrète (DFT / FFT),
fenêtrage mathématique (Hamming, Hann, Blackman) et extraction spectrale.
"""

from typing import Tuple, List, Optional, Literal
import numpy as np


def apply_hamming_window(signal: np.ndarray) -> np.ndarray:
    """
    Applique mathématiquement une fenêtre de Hamming au signal audio temporel.
    
    Formule analytique de Hamming :
        w[n] = 0.54 - 0.46 * cos(2 * pi * n / (N - 1)),  pour 0 <= n < N
        
    Propriétés acoustiques :
        - Atténuation du premier lobe secondaire : environ -43 dB.
        - Réduit considérablement le phénomène de fuite spectrale (spectral leakage)
          dû à la troncature temporelle du signal périodique.
          
    Args:
        signal (np.ndarray): Trame audio 1D de longueur N.
        
    Returns:
        np.ndarray: Signal pondéré par la fenêtre de Hamming.
    """
    N = len(signal)
    if N <= 1:
        return signal.copy()
    
    # Calcul analytique direct de la fenêtre de Hamming
    n = np.arange(N)
    window = 0.54 - 0.46 * np.cos(2.0 * np.pi * n / (N - 1))
    return signal * window


def get_window(window_type: Literal['hamming', 'hann', 'blackman', 'rectangular'], N: int) -> np.ndarray:
    """
    Génère les coefficients de pondération d'une fenêtre d'analyse temporelle.
    
    Args:
        window_type: Type de fenêtre ('hamming', 'hann', 'blackman', 'rectangular').
        N: Longueur de la fenêtre en échantillons.
        
    Returns:
        np.ndarray: Coefficients de la fenêtre de taille N.
    """
    if N <= 1:
        return np.ones(N, dtype=np.float64)
        
    n = np.arange(N)
    if window_type == 'hamming':
        return 0.54 - 0.46 * np.cos(2.0 * np.pi * n / (N - 1))
    elif window_type == 'hann':
        return 0.5 * (1.0 - np.cos(2.0 * np.pi * n / (N - 1)))
    elif window_type == 'blackman':
        return (0.42 
                - 0.50 * np.cos(2.0 * np.pi * n / (N - 1)) 
                + 0.08 * np.cos(4.0 * np.pi * n / (N - 1)))
    elif window_type == 'rectangular':
        return np.ones(N, dtype=np.float64)
    else:
        raise ValueError(f"Type de fenêtre inconnu : {window_type}")


def dft_discrete(signal: np.ndarray) -> np.ndarray:
    """
    Calcule la Transformée de Fourier Discrète (DFT) analytique selon sa définition formelle.
    
    Formule mathématique :
        X[k] = sum_{n=0}^{N-1} x[n] * exp(-j * 2 * pi * k * n / N)
        
    Remarque :
        Complexité algorithmique en O(N^2). Utilisé pour la validation
        théorique ou sur de petits blocs d'échantillons.
        
    Args:
        signal (np.ndarray): Signal temporel 1D réel de longueur N.
        
    Returns:
        np.ndarray: Spectre complexe X[k] de longueur N.
    """
    N = len(signal)
    n = np.arange(N)
    k = n.reshape((N, 1))
    # Matrice des facteurs de rotation (twiddle factors)
    W = np.exp(-2j * np.pi * k * n / N)
    return np.dot(W, signal)


def compute_fft_spectrum(
    signal: np.ndarray,
    sample_rate: int,
    window_type: str = 'hamming',
    zero_padding_factor: int = 2
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calcule le spectre d'amplitude et de puissance unilatéral (monolatéral)
    via l'algorithme de Transformée de Fourier Rapide (FFT - Cooley-Tukey).
    
    Étapes :
    1. Soustraction de la composante continue (offset DC).
    2. Application de la fenêtre temporelle sélectionnée.
    3. Normalisation par le gain cohérent de la fenêtre (amplitude correcte).
    4. Remplissage par zéros (Zero-padding) pour interpoler le spectre fréquentiel.
    5. Calcul de la FFT via rfft (optimisé pour signaux réels).
    6. Extraction du module de l'amplitude linéaire et conversion en dB.
    
    Args:
        signal (np.ndarray): Signal audio temporel 1D (mono).
        sample_rate (int): Fréquence d'échantillonnage en Hz (ex: 44100).
        window_type (str): Type de fenêtre ('hamming', 'hann', 'blackman', 'rectangular').
        zero_padding_factor (int): Facteur multiplicatif pour le zero-padding (ex: 2 ou 4).
        
    Returns:
        Tuple[np.ndarray, np.ndarray, np.ndarray]:
            - frequencies: Tableau des fréquences en Hz [0, sample_rate / 2].
            - magnitudes_linear: Amplitudes linéaires crête normalisées.
            - magnitudes_db: Amplitudes relatives en décibels (dB FS).
    """
    N = len(signal)
    if N == 0:
        return np.array([]), np.array([]), np.array([])
        
    # 1. Élimination de la composante continue (offset continu DC)
    detrended_signal = signal - np.mean(signal)
    
    # 2. Fenêtrage
    win = get_window(window_type, N)
    windowed_signal = detrended_signal * win
    
    # 3. Facteur de normalisation du gain cohérent de la fenêtre
    # La somme des coefficients de la fenêtre permet de préserver l'amplitude crête
    window_coherent_gain = np.sum(win)
    if window_coherent_gain <= 1e-12:
        window_coherent_gain = 1.0
        
    # 4. Zero-padding pour affiner la grille fréquentielle apparente
    fft_size = N * max(1, zero_padding_factor)
    
    # 5. Calcul de la FFT réelle
    fft_complex = np.fft.rfft(windowed_signal, n=fft_size)
    frequencies = np.fft.rfftfreq(fft_size, d=1.0 / sample_rate)
    
    # 6. Amplitude unilatérale normalisée
    # Pour un spectre unilatéral, les composantes AC (hors DC et Nyquist) sont multipliées par 2
    magnitudes_linear = (np.abs(fft_complex) / window_coherent_gain) * 2.0
    magnitudes_linear[0] /= 2.0  # La composante DC ne doit pas être doublée
    if fft_size % 2 == 0 and len(magnitudes_linear) > 1:
        magnitudes_linear[-1] /= 2.0  # La fréquence de Nyquist non plus
        
    # 7. Conversion en décibels avec plancher dynamique à -120 dB
    eps = 1e-12
    magnitudes_db = 20.0 * np.log10(np.maximum(magnitudes_linear, eps))
    
    return frequencies, magnitudes_linear, magnitudes_db


def parabolic_interpolation(
    magnitudes: np.ndarray,
    peak_index: int
) -> Tuple[float, float]:
    """
    Effectue une interpolation parabolique quadratique autour d'un pic spectral.
    
    Permet d'obtenir une précision sous-fréquentielle (sub-bin) bien supérieure
    à la résolution brute du bin FFT : delta_f = f_s / N_fft.
    
    Formule :
        Soit alpha = y[k-1], beta = y[k], gamma = y[k+1]
        delta = 0.5 * (alpha - gamma) / (alpha - 2 * beta + gamma)
        k_exact = k + delta
        y_exact = beta - 0.25 * (alpha - gamma) * delta
        
    Args:
        magnitudes (np.ndarray): Tableau des amplitudes du spectre.
        peak_index (int): Indice entier du pic local k.
        
    Returns:
        Tuple[float, float]:
            - refined_index: Indice réel interpolé (k + delta).
            - refined_magnitude: Amplitude maximale interpolée.
    """
    if peak_index <= 0 or peak_index >= len(magnitudes) - 1:
        return float(peak_index), float(magnitudes[peak_index])
        
    alpha = magnitudes[peak_index - 1]
    beta = magnitudes[peak_index]
    gamma = magnitudes[peak_index + 1]
    
    denominator = alpha - 2.0 * beta + gamma
    if abs(denominator) < 1e-12:
        return float(peak_index), float(beta)
        
    delta = 0.5 * (alpha - gamma) / denominator
    # Sécurité pour contraindre delta dans [-0.5, +0.5]
    delta = np.clip(delta, -0.5, 0.5)
    
    refined_index = float(peak_index + delta)
    refined_magnitude = float(beta - 0.25 * (alpha - gamma) * delta)
    
    return refined_index, refined_magnitude


def find_spectral_peaks(
    frequencies: np.ndarray,
    magnitudes: np.ndarray,
    min_magnitude: float = 0.01,
    min_freq: float = 20.0,
    max_freq: float = 5000.0,
    max_peaks: int = 10
) -> List[Tuple[float, float]]:
    """
    Identifie les pics spectraux proéminents avec interpolation parabolique.
    
    Args:
        frequencies (np.ndarray): Tableau des fréquences en Hz.
        magnitudes (np.ndarray): Tableau des amplitudes linéaires.
        min_magnitude (float): Seuil d'amplitude minimal pour valider un pic.
        min_freq (float): Fréquence minimale d'intérêt en Hz.
        max_freq (float): Fréquence maximale d'intérêt en Hz.
        max_peaks (int): Nombre maximal de pics renvoyés (triés par amplitude décroissante).
        
    Returns:
        List[Tuple[float, float]]: Liste de tuples (fréquence_hz, amplitude).
    """
    if len(frequencies) < 3 or len(magnitudes) < 3:
        return []
        
    df = frequencies[1] - frequencies[0] if len(frequencies) > 1 else 1.0
    
    # Masque fréquentiel
    valid_mask = (frequencies >= min_freq) & (frequencies <= max_freq)
    valid_indices = np.where(valid_mask)[0]
    
    peaks = []
    for idx in valid_indices:
        if idx <= 0 or idx >= len(magnitudes) - 1:
            continue
            
        current = magnitudes[idx]
        if current > magnitudes[idx - 1] and current > magnitudes[idx + 1]:
            if current >= min_magnitude:
                refined_idx, refined_mag = parabolic_interpolation(magnitudes, idx)
                refined_freq = refined_idx * df
                peaks.append((refined_freq, refined_mag))
                
    # Trier par amplitude décroissante
    peaks.sort(key=lambda p: p[1], reverse=True)
    return peaks[:max_peaks]
