"""
Module de conversion entre fréquences acoustiques (Hz), notes chromatiques
et calcul précis de l'écart d'accordage en Cents (Système tempérament égal 12-TET).
"""

from typing import Tuple, Optional, Dict, Literal
from dataclasses import dataclass
import numpy as np

from src.utils.constants import (
    DEFAULT_CONCERT_PITCH_A4,
    MIDI_A4_NOTE_NUMBER,
    NOTE_NAMES_ENGLISH,
    NOTE_NAMES_FRENCH,
    IN_TUNE_TOLERANCE_CENTS,
    CLOSE_TOLERANCE_CENTS
)


@dataclass
class NoteInfo:
    """Structure encapsulant les attributs musicaux et d'accordage d'une note."""
    note_name_en: str         # Ex: "A", "C#", "F"
    note_name_fr: str         # Ex: "La", "Do#", "Fa"
    octave: int               # Ex: 4
    midi_number: int          # Ex: 69 pour A4
    measured_freq: float      # Fréquence réelle mesurée en Hz (ex: 441.2 Hz)
    target_freq: float        # Fréquence théorique idéale en Hz (ex: 440.0 Hz)
    cents_deviation: float    # Écart en Cents entre -50.0 et +50.0
    tuning_status: str        # 'IN_TUNE', 'FLAT' (trop grave), 'SHARP' (trop aigu)
    status_label_fr: str      # 'Accordé', 'Trop grave', 'Trop aigu'
    
    @property
    def full_name_en(self) -> str:
        """Exemple : 'A4' ou 'C#3'"""
        return f"{self.note_name_en}{self.octave}"
        
    @property
    def full_name_fr(self) -> str:
        """Exemple : 'La 4' ou 'Do# 3'"""
        return f"{self.note_name_fr}{self.octave}"


class NoteConverter:
    """
    Convertisseur mathématique Fréquence <-> Note musicale dans le tempérament égal.
    Permet de calibrer le diapason de référence (La4 / A4, par défaut 440 Hz).
    """

    def __init__(self, concert_pitch_a4: float = DEFAULT_CONCERT_PITCH_A4):
        self.concert_pitch_a4 = float(concert_pitch_a4)
        self.in_tune_tolerance = IN_TUNE_TOLERANCE_CENTS

    def set_concert_pitch(self, pitch: float) -> None:
        """Modifie la référence du diapason La4 (ex: 440 Hz, 442 Hz, 432 Hz)."""
        if 400.0 <= pitch <= 480.0:
            self.concert_pitch_a4 = float(pitch)
        else:
            raise ValueError(f"Fréquence de référence invalide : {pitch} Hz")

    def set_tolerance(self, tolerance_cents: float) -> None:
        """Règle la tolérance en cents pour considérer la note comme parfaitement accordée."""
        self.in_tune_tolerance = max(0.5, float(tolerance_cents))

    def frequency_to_midi(self, freq: float) -> float:
        """
        Calcule le numéro de note MIDI continu (flottant) pour une fréquence donnée.
        
        Formule :
            m = 69 + 12 * log2(f / f_ref)
        """
        if freq <= 0.0:
            return 0.0
        return MIDI_A4_NOTE_NUMBER + 12.0 * np.log2(freq / self.concert_pitch_a4)

    def midi_to_frequency(self, midi_number: float) -> float:
        """
        Calcule la fréquence idéale pour un numéro de note MIDI.
        
        Formule :
            f = f_ref * 2^((m - 69) / 12)
        """
        return self.concert_pitch_a4 * (2.0 ** ((midi_number - MIDI_A4_NOTE_NUMBER) / 12.0))

    def calculate_cents(self, measured_freq: float, target_freq: float) -> float:
        """
        Calcule l'écart en Cents entre la fréquence mesurée et la fréquence cible.
        
        Formule :
            delta_cents = 1200 * log2(f_mesuree / f_cible)
        """
        if measured_freq <= 0.0 or target_freq <= 0.0:
            return 0.0
        return float(1200.0 * np.log2(measured_freq / target_freq))

    def convert_frequency(self, frequency: float) -> Optional[NoteInfo]:
        """
        Convertit une fréquence acoustique mesurée en informations complètes de note musicale.
        
        Args:
            frequency (float): Fréquence mesurée en Hz.
            
        Returns:
            Optional[NoteInfo]: Structure détaillée ou None si fréquence non valide.
        """
        if frequency <= 10.0 or np.isnan(frequency) or np.isinf(frequency):
            return None
            
        # 1. Calcul du numéro MIDI continu
        midi_float = self.frequency_to_midi(frequency)
        
        # 2. Arrondi au demi-ton le plus proche
        midi_nearest = int(round(midi_float))
        
        # 3. Extraction du nom de la note et de l'octave
        # La note 0 en MIDI est C-1. C0 est la note MIDI 12. C4 (Do 4) est la note 60. A4 est 69.
        pitch_class = midi_nearest % 12
        octave = (midi_nearest // 12) - 1
        
        note_en = NOTE_NAMES_ENGLISH[pitch_class]
        note_fr = NOTE_NAMES_FRENCH[pitch_class]
        
        # 4. Calcul de la fréquence cible idéale
        target_frequency = self.midi_to_frequency(midi_nearest)
        
        # 5. Calcul de l'écart en cents (borné entre -50.0 et +50.0 cents)
        cents_deviation = self.calculate_cents(frequency, target_frequency)
        cents_deviation = float(np.clip(cents_deviation, -50.0, 50.0))
        
        # 6. Détermination du statut de justesse
        if abs(cents_deviation) <= self.in_tune_tolerance:
            status = "IN_TUNE"
            label = "Accordé"
        elif cents_deviation < -self.in_tune_tolerance:
            status = "FLAT"
            label = "Trop grave"
        else:
            status = "SHARP"
            label = "Trop aigu"
            
        return NoteInfo(
            note_name_en=note_en,
            note_name_fr=note_fr,
            octave=octave,
            midi_number=midi_nearest,
            measured_freq=float(frequency),
            target_freq=float(target_frequency),
            cents_deviation=cents_deviation,
            tuning_status=status,
            status_label_fr=label
        )

    def note_name_to_frequency(self, note_name: str, octave: int) -> Optional[float]:
        """
        Renvoie la fréquence idéale pour un nom de note (ex: 'A', 4 -> 440.0 Hz).
        Supporte les notations anglaises et françaises.
        """
        clean_name = note_name.strip()
        idx = -1
        
        # Recherche en notation anglaise
        for i, n in enumerate(NOTE_NAMES_ENGLISH):
            if n.lower() == clean_name.lower():
                idx = i
                break
                
        # Recherche en notation française
        if idx == -1:
            for i, n in enumerate(NOTE_NAMES_FRENCH):
                if n.lower() == clean_name.lower():
                    idx = i
                    break
                    
        if idx == -1:
            return None
            
        midi_num = (octave + 1) * 12 + idx
        return self.midi_to_frequency(midi_num)
