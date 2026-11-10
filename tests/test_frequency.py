"""
Tests unitaires pour l'extraction de fréquence fondamentale (Pitch Detection) :
YIN, HPS, autocorrélation, fondamentale manquante et résistance au bruit.
"""

import pytest
import numpy as np
from src.signal.frequency_detector import (
    PitchDetector,
    yin_pitch_estimator,
    harmonic_product_spectrum_estimator,
    autocorrelation_pitch_estimator,
    compute_rms
)


def generate_tone(
    freq: float,
    duration: float = 0.2,
    sample_rate: int = 44100,
    harmonics: list = None,
    noise_level: float = 0.0
) -> np.ndarray:
    """Fonction utilitaire générant un signal synthétique calibré."""
    N = int(sample_rate * duration)
    t = np.arange(N) / sample_rate
    
    if harmonics is None:
        signal = 0.8 * np.sin(2.0 * np.pi * freq * t)
    else:
        signal = np.zeros(N, dtype=np.float64)
        for h_num, h_amp in harmonics:
            signal += h_amp * np.sin(2.0 * np.pi * (h_num * freq) * t)
            
    if noise_level > 0.0:
        noise = np.random.normal(0, noise_level, N)
        signal += noise
        
    return signal.astype(np.float32)


def test_yin_detect_440_hz():
    """Vérifie la détection exacte du La 4 (440.0 Hz) avec une précision sub-hertzienne."""
    fs = 44100
    signal = generate_tone(freq=440.0, duration=0.2, sample_rate=fs)
    
    f0, conf = yin_pitch_estimator(signal, fs)
    
    assert abs(f0 - 440.0) < 0.25  # Moins de 0.25 Hz d'écart
    assert conf > 0.95             # Très haute confiance


@pytest.mark.parametrize("target_freq", [
    82.41,   # Mi 2 (Guitare basse / corde Mi grave)
    130.81,  # Do 3
    220.00,  # La 3
    440.00,  # La 4
    659.25,  # Mi 5
    880.00   # La 5
])
def test_yin_detect_chromatic_range(target_freq):
    """Vérifie la détection de fréquence fondamentale sur plusieurs octaves musicales."""
    fs = 44100
    # Durée plus longue pour les fréquences graves afin d'avoir plusieurs cycles
    duration = 0.3 if target_freq < 150 else 0.15
    signal = generate_tone(freq=target_freq, duration=duration, sample_rate=fs)
    
    f0, conf = yin_pitch_estimator(signal, fs)
    
    relative_error = abs(f0 - target_freq) / target_freq
    assert relative_error < 0.005  # Erreur relative inférieure à 0.5%
    assert conf > 0.90


def test_missing_fundamental_detection():
    """
    Vérifie la détection d'une fondamentale très atténuée (missing fundamental).
    Le signal à f0 = 200 Hz n'a que 5% d'énergie, alors que les harmoniques
    400 Hz (2f0) et 600 Hz (3f0) sont prédominantes.
    L'algorithme YIN doit identifier 200 Hz et non 400 Hz (évite l'erreur d'octave).
    """
    fs = 44100
    f0_target = 200.0
    harmonics = [
        (1, 0.05),  # Fondamentale quasi-absente
        (2, 0.70),  # Harmonique 2 prédominante
        (3, 0.45),  # Harmonique 3
        (4, 0.20)   # Harmonique 4
    ]
    signal = generate_tone(freq=f0_target, duration=0.25, sample_rate=fs, harmonics=harmonics)
    
    # 1. Vérification avec YIN
    f0_yin, conf_yin = yin_pitch_estimator(signal, fs)
    assert abs(f0_yin - f0_target) < 1.0
    
    # 2. Vérification avec HPS
    f0_hps, _ = harmonic_product_spectrum_estimator(signal, fs)
    assert abs(f0_hps - f0_target) < 2.0


def test_autocorrelation_estimator():
    """Vérifie l'estimation de pitch par autocorrélation (ACF)."""
    fs = 44100
    signal = generate_tone(freq=330.0, duration=0.2, sample_rate=fs)
    f0, conf = autocorrelation_pitch_estimator(signal, fs)
    
    assert abs(f0 - 330.0) < 1.0
    assert conf > 0.80


def test_noise_robustness():
    """Vérifie la robustesse en présence d'un fort bruit additif blanc (SNR modéré)."""
    np.random.seed(42)
    fs = 44100
    # Bruit blanc gaussien à 15% d'amplitude
    signal = generate_tone(freq=440.0, duration=0.25, sample_rate=fs, noise_level=0.15)
    
    detector = PitchDetector(sample_rate=fs, default_method="yin")
    result = detector.analyze(signal)
    
    assert result.is_voiced
    assert abs(result.frequency - 440.0) < 2.0


def test_silence_detection():
    """Vérifie que le détecteur ignore le silence ou bruit de fond négligeable."""
    fs = 44100
    silence = np.zeros(4096, dtype=np.float32)
    
    detector = PitchDetector(sample_rate=fs)
    result = detector.analyze(silence)
    
    assert not result.is_voiced
    assert result.frequency == 0.0
    assert result.confidence == 0.0
