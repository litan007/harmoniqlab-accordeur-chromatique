"""
Tests unitaires pour la conversion Fréquence <-> Note musicale,
système tempérament égal 12-TET et calcul de l'écart en cents.
"""

import pytest
import numpy as np
from src.signal.note_converter import NoteConverter


@pytest.fixture
def converter():
    return NoteConverter(concert_pitch_a4=440.0)


def test_standard_concert_pitch_a4(converter):
    """Vérifie la détection exacte du La 4 à 440.0 Hz."""
    info = converter.convert_frequency(440.0)
    
    assert info is not None
    assert info.note_name_en == "A"
    assert info.note_name_fr == "La"
    assert info.octave == 4
    assert info.midi_number == 69
    assert np.isclose(info.target_freq, 440.0, atol=1e-2)
    assert np.isclose(info.cents_deviation, 0.0, atol=0.1)
    assert info.tuning_status == "IN_TUNE"
    assert info.status_label_fr == "Accordé"


@pytest.mark.parametrize("freq, expected_en, expected_fr, expected_octave", [
    (82.41, "E", "Mi", 2),       # Mi 2
    (110.00, "A", "La", 2),      # La 2
    (146.83, "D", "Ré", 3),      # Ré 3
    (196.00, "G", "Sol", 3),     # Sol 3
    (246.94, "B", "Si", 3),      # Si 3
    (261.63, "C", "Do", 4),      # Do 4 (Do central du piano)
    (329.63, "E", "Mi", 4),      # Mi 4
    (523.25, "C", "Do", 5),      # Do 5
    (880.00, "A", "La", 5)       # La 5
])
def test_all_12_chromatic_notes_conversion(converter, freq, expected_en, expected_fr, expected_octave):
    """Vérifie la conversion sur un ensemble de notes représentatives de l'échelle chromatique."""
    info = converter.convert_frequency(freq)
    
    assert info is not None
    assert info.note_name_en == expected_en
    assert info.note_name_fr == expected_fr
    assert info.octave == expected_octave
    assert abs(info.cents_deviation) < 0.5


def test_cents_deviation_sharp(converter):
    """Vérifie le calcul des cents pour une note trop aiguë (ex: 445 Hz au lieu de 440 Hz)."""
    # 1200 * log2(445 / 440) = +19.56 cents
    info = converter.convert_frequency(445.0)
    
    assert info is not None
    assert info.note_name_en == "A"
    assert info.octave == 4
    assert np.isclose(info.cents_deviation, 19.56, atol=0.2)
    assert info.tuning_status == "SHARP"
    assert info.status_label_fr == "Trop aigu"


def test_cents_deviation_flat(converter):
    """Vérifie le calcul des cents pour une note trop grave (ex: 435 Hz au lieu de 440 Hz)."""
    # 1200 * log2(435 / 440) = -19.78 cents
    info = converter.convert_frequency(435.0)
    
    assert info is not None
    assert info.note_name_en == "A"
    assert info.octave == 4
    assert np.isclose(info.cents_deviation, -19.78, atol=0.2)
    assert info.tuning_status == "FLAT"
    assert info.status_label_fr == "Trop grave"


def test_in_tune_tolerance_zone(converter):
    """Vérifie qu'un écart inférieur à la tolérance (<= 4 cents) est classé Accordé."""
    # 440.8 Hz correspond à environ +3.14 cents
    info = converter.convert_frequency(440.8)
    
    assert info is not None
    assert abs(info.cents_deviation) <= 4.0
    assert info.tuning_status == "IN_TUNE"
    assert info.status_label_fr == "Accordé"


def test_custom_concert_pitch_calibration():
    """Vérifie l'étalonnage avec un diapason européen à 442.0 Hz."""
    calibrated_converter = NoteConverter(concert_pitch_a4=442.0)
    
    # 442.0 Hz doit désormais être exactement La 4 à 0.0 cent
    info_442 = calibrated_converter.convert_frequency(442.0)
    assert info_442.note_name_en == "A"
    assert np.isclose(info_442.cents_deviation, 0.0, atol=0.05)
    
    # Alors que 440.0 Hz est désormais considéré comme trop grave (-7.8 cents)
    info_440 = calibrated_converter.convert_frequency(440.0)
    assert info_440.note_name_en == "A"
    assert info_440.tuning_status == "FLAT"
    assert info_440.cents_deviation < -5.0


def test_invalid_and_boundary_frequencies(converter):
    """Vérifie la robustesse face aux entrées non-physiques ou nulles."""
    assert converter.convert_frequency(0.0) is None
    assert converter.convert_frequency(-440.0) is None
    assert converter.convert_frequency(float('nan')) is None
    assert converter.convert_frequency(float('inf')) is None
