"""
Tests unitaires pour le calcul de la DFT, FFT, fenêtrage de Hamming
et interpolation parabolique sous-fréquentielle.
"""

import pytest
import numpy as np
from src.signal.fourier import (
    apply_hamming_window,
    get_window,
    dft_discrete,
    compute_fft_spectrum,
    parabolic_interpolation,
    find_spectral_peaks
)


def test_hamming_window_mathematical_properties():
    """Vérifie la formule analytique et les propriétés aux limites de Hamming."""
    N = 256
    win = get_window('hamming', N)
    
    assert len(win) == N
    # Pour n = 0, w[0] = 0.54 - 0.46 * cos(0) = 0.08
    assert np.isclose(win[0], 0.08, atol=1e-4)
    assert np.isclose(win[-1], 0.08, atol=1e-4)
    # Au centre (n = (N-1)/2), cos(pi) = -1 => w = 0.54 + 0.46 = 1.0
    assert np.isclose(np.max(win), 1.0, atol=1e-3)
    # Symétrie
    assert np.allclose(win, win[::-1])


def test_dft_discrete_vs_numpy_fft():
    """Compare la DFT analytique explicite matricielle avec la FFT sur un signal test."""
    N = 64
    fs = 1000
    t = np.arange(N) / fs
    # Signal bi-harmonique : 100 Hz et 250 Hz
    x = 0.7 * np.sin(2 * np.pi * 100 * t) + 0.3 * np.cos(2 * np.pi * 250 * t)
    
    X_dft = dft_discrete(x)
    X_fft = np.fft.fft(x)
    
    # La DFT explicite et la FFT doivent être numériquement identiques à la précision machine
    assert np.allclose(X_dft, X_fft, atol=1e-10)


def test_fft_spectrum_amplitude_calibration():
    """Vérifie qu'une sinusoïde pure d'amplitude 1.0 produit un pic d'amplitude 1.0 après calibration."""
    fs = 44100
    duration = 0.1
    N = int(fs * duration)
    t = np.arange(N) / fs
    f_test = 440.0
    signal = 1.0 * np.sin(2 * np.pi * f_test * t)
    
    freqs, mags_lin, mags_db = compute_fft_spectrum(signal, fs, window_type='hamming', zero_padding_factor=2)
    
    peak_idx = np.argmax(mags_lin)
    peak_freq = freqs[peak_idx]
    peak_amp = mags_lin[peak_idx]
    
    # La fréquence du pic doit être proche de 440 Hz
    assert abs(peak_freq - 440.0) < (fs / N)
    # L'amplitude doit être calibrée à ~1.0 (marge de 5% due au fenêtrage et zero padding)
    assert np.isclose(peak_amp, 1.0, atol=0.05)
    # Le pic en dB doit être proche de 0 dB FS (20 * log10(1.0) = 0 dB)
    assert abs(mags_db[peak_idx]) < 0.6


def test_parabolic_interpolation_sub_bin_accuracy():
    """Démontre que l'interpolation parabolique raffine la précision en dessous du pas fréquentiel."""
    fs = 44100
    N = 4096
    df = fs / N  # ~10.766 Hz
    
    # Fréquence choisie exactement entre deux bins FFT (ex: bin 40.5 * df)
    target_freq = 40.5 * df
    t = np.arange(N) / fs
    signal = np.cos(2 * np.pi * target_freq * t)
    
    # FFT brute sans zero-padding
    win = get_window('hamming', N)
    fft_raw = np.abs(np.fft.rfft(signal * win))
    raw_peak_bin = int(np.argmax(fft_raw))
    raw_detected_freq = raw_peak_bin * df
    
    # Erreur brute sans interpolation : environ un demi-bin (~5.38 Hz)
    raw_error = abs(raw_detected_freq - target_freq)
    
    # Avec interpolation parabolique
    refined_bin, _ = parabolic_interpolation(fft_raw, raw_peak_bin)
    refined_freq = refined_bin * df
    refined_error = abs(refined_freq - target_freq)
    
    # L'interpolation doit réduire significativement l'erreur
    assert refined_error < raw_error
    assert refined_error < 0.5  # Moins de 0.5 Hz d'erreur !


def test_find_spectral_peaks():
    """Vérifie l'identification correcte des pics harmoniques multiples."""
    fs = 44100
    N = 8192
    t = np.arange(N) / fs
    # Signal avec 3 harmoniques : 200 Hz, 400 Hz, 600 Hz
    signal = (
        0.8 * np.sin(2 * np.pi * 200.0 * t) +
        0.5 * np.sin(2 * np.pi * 400.0 * t) +
        0.3 * np.sin(2 * np.pi * 600.0 * t)
    )
    
    freqs, mags, _ = compute_fft_spectrum(signal, fs, window_type='hamming')
    peaks = find_spectral_peaks(freqs, mags, min_magnitude=0.1, min_freq=50.0, max_peaks=5)
    
    detected_freqs = sorted([p[0] for p in peaks])
    assert len(detected_freqs) >= 3
    assert any(abs(f - 200.0) < 1.0 for f in detected_freqs)
    assert any(abs(f - 400.0) < 1.0 for f in detected_freqs)
    assert any(abs(f - 600.0) < 1.0 for f in detected_freqs)
