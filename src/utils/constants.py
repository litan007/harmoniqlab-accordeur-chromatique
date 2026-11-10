"""
Constantes globales et paramètres de configuration pour le système d'accordeur chromatique
et d'analyse audio temps réel.
"""

from typing import Final, List, Dict

# ==============================================================================
# PARAMÈTRES AUDIO ET ÉCHANTILLONNAGE
# ==============================================================================
DEFAULT_SAMPLE_RATE: Final[int] = 44100  # Fréquence d'échantillonnage standard (Hz)
SUPPORTED_SAMPLE_RATES: Final[List[int]] = [22050, 44100, 48000, 96000]

DEFAULT_BUFFER_SIZE: Final[int] = 4096   # Taille de la fenêtre d'analyse (échantillons)
FFT_ZERO_PADDING_FACTOR: Final[int] = 2  # Facteur de sur-échantillonnage fréquentiel

# Plage de fréquences musicales audibles pour instruments usuels (guitare, basse, piano, voix)
MIN_AUDIO_FREQ: Final[float] = 27.5      # La0 (A0) - note la plus basse d'un piano standard
MAX_AUDIO_FREQ: Final[float] = 4200.0    # Do8 (C8) - note la plus haute d'un piano standard

# Seuil de silence (en amplitude RMS normalisée et dB)
DEFAULT_SILENCE_THRESHOLD_DB: Final[float] = -50.0  # en dB FS
DEFAULT_RMS_GATE: Final[float] = 0.005              # Seuil linéaire de niveau de signal

# ==============================================================================
# SYSTÈME DE TEMPÉRAMENT ÉGAL ET FRÉQUENCES DE RÉFÉRENCE
# ==============================================================================
DEFAULT_CONCERT_PITCH_A4: Final[float] = 440.0      # Fréquence de référence du La 4 (Hz)
MIN_CONCERT_PITCH: Final[float] = 430.0             # Plage ajustable minimale
MAX_CONCERT_PITCH: Final[float] = 450.0             # Plage ajustable maximale

# Noms des 12 notes chromatiques (Notation anglo-saxonne et solfège français)
NOTE_NAMES_ENGLISH: Final[List[str]] = [
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"
]

NOTE_NAMES_FRENCH: Final[List[str]] = [
    "Do", "Do#", "Ré", "Ré#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"
]

# Équivalents bémols usuels
NOTE_NAMES_FLAT_ENGLISH: Final[List[str]] = [
    "C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"
]

NOTE_NAMES_FLAT_FRENCH: Final[List[str]] = [
    "Do", "Réb", "Ré", "Mib", "Mi", "Fa", "Solb", "Sol", "Lab", "La", "Sib", "Si"
]

# Correspondance MIDI : La 4 = Note MIDI 69
MIDI_A4_NOTE_NUMBER: Final[int] = 69

# Tolérances pour l'accordage (en Cents, sachant que 1 demi-ton = 100 cents)
IN_TUNE_TOLERANCE_CENTS: Final[float] = 4.0   # En dessous de 4 cents = parfaitement accordé
CLOSE_TOLERANCE_CENTS: Final[float] = 12.0    # Entre 4 et 12 cents = acceptable mais perfectible

# ==============================================================================
# PALETTE DE COULEURS - THEME ONYX & OR (DESIGN STUDIO AUDIO PREMIUM)
# ==============================================================================
COLOR_BG_PRIMARY: Final[str] = "#0A0B0E"       # Noir onyx profond
COLOR_BG_SECONDARY: Final[str] = "#12141A"     # Surface charbon studio
COLOR_BG_TERTIARY: Final[str] = "#1A1D24"      # Éléments surélevés et cartes

# Accents Dorés & Champagne
COLOR_ACCENT_GOLD: Final[str] = "#D4AF37"      # Or métallique classique
COLOR_ACCENT_GOLD_BRIGHT: Final[str] = "#F3D578" # Or champagne éclatant
COLOR_ACCENT_GOLD_MUTED: Final[str] = "#8C7335" # Bronze doré subtil
COLOR_BORDER_GOLD: Final[str] = "#3D341C"       # Filets et bordures dorées discrètes

COLOR_ACCENT_BLUE: Final[str] = "#D4AF37"      # Accent principal or
COLOR_ACCENT_CYAN: Final[str] = "#E5C158"      # Champagne lumineux
COLOR_ACCENT_PURPLE: Final[str] = "#B38F44"    # Or patiné

# États de justesse (Tuner status)
COLOR_IN_TUNE: Final[str] = "#00E676"          # Vert émeraude haute visibilité
COLOR_FLAT: Final[str] = "#389BDE"             # Bleu saphir sobre
COLOR_SHARP: Final[str] = "#E84A4A"            # Rouge rubis sobre
COLOR_WARNING_ORANGE: Final[str] = "#D4AF37"   # Ambre doré

# Typographie et contrastes
COLOR_TEXT_PRIMARY: Final[str] = "#FAF8F2"     # Blanc ivoire luxueux
COLOR_TEXT_MUTED: Final[str] = "#A8A295"       # Champagne métallisé
COLOR_TEXT_DIMMED: Final[str] = "#615A4C"      # Bronze discret

COLOR_BORDER: Final[str] = "#2A251B"           # Bordure fine or/anthracite
COLOR_GRID_LINES: Final[str] = "#1B1914"       # Lignes de grille graphiques chaudes
