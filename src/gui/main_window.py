"""
Fenêtre principale moderne de l'application d'accordeur chromatique et traitement de signal.
Architecture modulaire PyQt6 avec barre latérale sombre, vues empilées,
contrôle matériel temps réel et affichage télémétrique.
"""

import sys
from typing import Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QComboBox, QFrame, QSlider,
    QProgressBar, QGroupBox, QGridLayout, QTextBrowser, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QFont, QColor, QPalette

from src.utils.constants import (
    COLOR_BG_PRIMARY,
    COLOR_BG_SECONDARY,
    COLOR_BG_TERTIARY,
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_CYAN,
    COLOR_ACCENT_GOLD,
    COLOR_ACCENT_GOLD_BRIGHT,
    COLOR_IN_TUNE,
    COLOR_FLAT,
    COLOR_SHARP,
    COLOR_WARNING_ORANGE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_DIMMED,
    COLOR_BORDER,
    COLOR_BORDER_GOLD,
    DEFAULT_CONCERT_PITCH_A4
)
from src.audio.audio_processor import AudioProcessor, AudioAnalysisFrame
from src.gui.tuner_widget import TunerWidget
from src.gui.spectrum_widget import SpectrumWidget


class AudioBridge(QObject):
    """Pont de communication thread-safe entre le callback audio et l'interface PyQt6."""
    frame_ready = pyqtSignal(object)


class MainWindow(QMainWindow):
    """
    Fenêtre principale professionnelle intégrant l'ensemble des modules :
    - Navigation par barre latérale.
    - Vue accordeur chromatique analogique/numérique.
    - Vue spectrogramme et oscilloscope temporel.
    - Vue générateur synthétique pour tests de laboratoire.
    - Vue théorique et télémétrie DSP.
    - Vue des paramètres et étalonnage de référence.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HarmoniqLab — Accordeur Chromatique & Analyseur DSP Temps Réel")
        self.resize(1180, 780)
        self.setMinimumSize(960, 640)
        
        # Initialisation du processeur audio central
        self.audio_processor = AudioProcessor(
            sample_rate=44100,
            buffer_size=4096,
            concert_pitch=DEFAULT_CONCERT_PITCH_A4,
            pitch_method="yin"
        )
        
        # Pont de signaux PyQt thread-safe
        self.bridge = AudioBridge()
        self.bridge.frame_ready.connect(self._on_audio_frame_received)
        self.audio_processor.register_callback(lambda frame: self.bridge.frame_ready.emit(frame))
        
        self._init_styles()
        self._init_ui()
        self._populate_audio_devices()

    def _init_styles(self) -> None:
        """Applique la feuille de style globale Onyx & Or (Design Studio Audio Premium)."""
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLOR_BG_PRIMARY};
            }}
            QWidget {{
                background-color: {COLOR_BG_PRIMARY};
                color: {COLOR_TEXT_PRIMARY};
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            }}
            QScrollBar:vertical {{
                background: {COLOR_BG_PRIMARY};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLOR_BG_TERTIARY};
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #D4AF37;
            }}
            QSlider::groove:horizontal {{
                border: 1px solid #2B2517;
                height: 6px;
                background: #0A0B0E;
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: #D4AF37;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: #F3D578;
                border: 1px solid #70591E;
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}
        """)

    def _init_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        
        # 1. Barre latérale de navigation (Sidebar)
        self.sidebar = self._create_sidebar()
        root_layout.addWidget(self.sidebar)
        
        # 2. Zone de contenu principale (En-tête + Vues empilées)
        content_area = QWidget(self)
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Barre d'état et de contrôle supérieure
        self.header_bar = self._create_header_bar()
        content_layout.addWidget(self.header_bar)
        
        # Pages empilées (QStackedWidget)
        self.pages_stack = QStackedWidget(content_area)
        
        # Page 0 : Accordeur
        self.tuner_view = TunerWidget(self.pages_stack)
        self.pages_stack.addWidget(self.tuner_view)
        
        # Page 1 : Analyse spectrale & temporelle
        self.spectrum_view = SpectrumWidget(self.pages_stack)
        self.pages_stack.addWidget(self.spectrum_view)
        
        # Page 2 : Générateur de signaux synthétiques
        self.synth_view = self._create_synthetic_generator_page()
        self.pages_stack.addWidget(self.synth_view)
        
        # Page 3 : Théorie & Formules DSP
        self.theory_view = self._create_theory_page()
        self.pages_stack.addWidget(self.theory_view)
        
        # Page 4 : Paramètres & Calibrage
        self.settings_view = self._create_settings_page()
        self.pages_stack.addWidget(self.settings_view)
        
        content_layout.addWidget(self.pages_stack)
        root_layout.addWidget(content_area)

    def _create_sidebar(self) -> QWidget:
        """Construit la barre latérale de navigation sombre avec liserés dorés."""
        sidebar = QFrame(self)
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BG_SECONDARY};
                border-right: 1px solid #2B2517;
            }}
        """)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 24, 16, 20)
        layout.setSpacing(8)
        
        # Logo & Titre
        brand_layout = QVBoxLayout()
        brand_layout.setSpacing(4)
        
        title = QLabel("HARMONIQLAB", sidebar)
        title.setStyleSheet("""
            color: #FAF8F2;
            font-size: 17px;
            font-weight: 800;
            letter-spacing: 2.5px;
        """)
        
        subtitle = QLabel("DSP CHROMATIC TUNER", sidebar)
        subtitle.setStyleSheet("""
            color: #D4AF37;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 2px;
        """)
        
        brand_layout.addWidget(title)
        brand_layout.addWidget(subtitle)
        layout.addLayout(brand_layout)
        
        layout.addSpacing(24)
        
        # Boutons de navigation
        self.nav_buttons = []
        nav_items = [
            ("ACCORDEUR", 0),
            ("SPECTRE & FFT", 1),
            ("GÉNÉRATEUR TEST", 2),
            ("THÉORIE & MATHS", 3),
            ("PARAMÈTRES", 4)
        ]
        
        for text, index in nav_items:
            btn = QPushButton(text, sidebar)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setFixedHeight(44)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            # Style du bouton de navigation (Onyx & Or)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #A8A295;
                    border: none;
                    border-radius: 8px;
                    padding-left: 16px;
                    text-align: left;
                    font-size: 12px;
                    font-weight: 600;
                    letter-spacing: 1px;
                }
                QPushButton:hover {
                    background-color: #191B22;
                    color: #FAF8F2;
                    border-left: 2px solid #8C7335;
                }
                QPushButton:checked {
                    background-color: rgba(212, 175, 55, 0.12);
                    color: #D4AF37;
                    border-left: 3px solid #D4AF37;
                    font-weight: 700;
                }
            """)
            btn.clicked.connect(lambda checked, idx=index: self._navigate_to_page(idx))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)
            
        self.nav_buttons[0].setChecked(True)
        
        layout.addStretch()
        
        # Badge de version et métadonnées
        footer_label = QLabel("Projet DSP • Python 3.11\nNumPy • SciPy • PyQt6", sidebar)
        footer_label.setStyleSheet("color: #615A4C; font-size: 10px; line-height: 14px;")
        layout.addWidget(footer_label)
        
        return sidebar

    def _create_header_bar(self) -> QWidget:
        """Construit la barre supérieure avec sélection du micro, vu-mètre et bouton d'action."""
        header = QFrame(self)
        header.setFixedHeight(72)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BG_SECONDARY};
                border-bottom: 1px solid #2B2517;
            }}
        """)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(20)
        
        # Sélection du périphérique audio
        device_box = QVBoxLayout()
        device_box.setSpacing(2)
        lbl_device = QLabel("PÉRIPHÉRIQUE MICROPHONE", header)
        lbl_device.setStyleSheet("color: #8C7F64; font-size: 10px; font-weight: 700; letter-spacing: 0.8px;")
        
        self.device_combo = QComboBox(header)
        self.device_combo.setFixedWidth(240)
        self.device_combo.setStyleSheet("""
            QComboBox {
                background-color: #0A0B0E;
                color: #FAF8F2;
                border: 1px solid #383120;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
            }
            QComboBox:hover {
                border: 1px solid #D4AF37;
            }
            QComboBox QAbstractItemView {
                background-color: #12141A;
                color: #FAF8F2;
                selection-background-color: #383120;
            }
        """)
        device_box.addWidget(lbl_device)
        device_box.addWidget(self.device_combo)
        layout.addLayout(device_box)
        
        # VU-mètre de niveau d'entrée (RMS dB FS)
        vu_box = QVBoxLayout()
        vu_box.setSpacing(2)
        
        vu_header = QHBoxLayout()
        lbl_vu = QLabel("NIVEAU AUDIO", header)
        lbl_vu.setStyleSheet("color: #8C7F64; font-size: 10px; font-weight: 700; letter-spacing: 0.8px;")
        self.lbl_vu_db = QLabel("-∞ dB", header)
        self.lbl_vu_db.setStyleSheet("color: #A8A295; font-size: 10px; font-weight: 600;")
        vu_header.addWidget(lbl_vu)
        vu_header.addStretch()
        vu_header.addWidget(self.lbl_vu_db)
        
        self.vu_progress = QProgressBar(header)
        self.vu_progress.setFixedWidth(180)
        self.vu_progress.setFixedHeight(8)
        self.vu_progress.setTextVisible(False)
        self.vu_progress.setRange(-60, 0)
        self.vu_progress.setValue(-60)
        self.vu_progress.setStyleSheet("""
            QProgressBar {
                background-color: #0A0B0E;
                border: 1px solid #2B2517;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8C7335, stop:0.65 #00E676, stop:0.92 #E84A4A);
                border-radius: 3px;
            }
        """)
        vu_box.addLayout(vu_header)
        vu_box.addWidget(self.vu_progress)
        layout.addLayout(vu_box)
        
        layout.addStretch()
        
        # Bouton principal DÉMARRER / ARRÊTER
        self.btn_toggle_mic = QPushButton("DÉMARRER LE MICRO", header)
        self.btn_toggle_mic.setFixedSize(190, 42)
        self.btn_toggle_mic.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_mic.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #E5C158, stop:1 #B88E28);
                color: #0A0B0E;
                border: 1px solid #F5D77F;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 1.2px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F3D578, stop:1 #CCA338);
            }
        """)
        self.btn_toggle_mic.clicked.connect(self._toggle_microphone)
        layout.addWidget(self.btn_toggle_mic)
        
        return header

    def _create_synthetic_generator_page(self) -> QWidget:
        """Construit le panneau interactif du générateur audio de laboratoire."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        card = QFrame(page)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BG_SECONDARY};
                border: 1px solid {COLOR_BORDER_GOLD};
                border-radius: 16px;
                padding: 20px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        
        lbl_head = QLabel("GÉNÉRATEUR DE SIGNAUX SYNTHÉTIQUES DE TEST", card)
        lbl_head.setStyleSheet(f"color: {COLOR_ACCENT_GOLD}; font-size: 15px; font-weight: 700; letter-spacing: 1px;")
        card_layout.addWidget(lbl_head)
        
        desc = QLabel(
            "Ce module génère des signaux acoustiques mathématiques (sinusoïde, harmoniques riches, "
            "fondamentale atténuée ou bruitée) pour tester l'accordeur et valider les algorithmes sans microphone.",
            card
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 12px;")
        card_layout.addWidget(desc)
        
        # Sélecteur de forme d'onde
        wave_box = QHBoxLayout()
        lbl_wave = QLabel("Forme d'onde :", card)
        lbl_wave.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-weight: 600;")
        self.synth_wave_combo = QComboBox(card)
        self.synth_wave_combo.addItems([
            "Harmoniques d'instrument (Corde vibrante)",
            "Sinusoïde pure",
            "Fondamentale atténuée (f0 atténuée, 2f0 et 3f0 prédominantes)",
            "Signal avec bruit blanc"
        ])
        self.synth_wave_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLOR_BG_TERTIARY};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER_GOLD};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QComboBox:hover {{
                border: 1px solid {COLOR_ACCENT_GOLD};
            }}
        """)
        self.synth_wave_combo.currentIndexChanged.connect(self._update_synthetic_params)
        wave_box.addWidget(lbl_wave)
        wave_box.addWidget(self.synth_wave_combo)
        card_layout.addLayout(wave_box)
        
        # Curseur de fréquence
        freq_box = QVBoxLayout()
        freq_header = QHBoxLayout()
        lbl_f = QLabel("Fréquence fondamentale :", card)
        lbl_f.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-weight: 600;")
        self.lbl_synth_freq_val = QLabel("440.0 Hz (La 4)", card)
        self.lbl_synth_freq_val.setStyleSheet(f"color: {COLOR_ACCENT_GOLD}; font-weight: 700; font-size: 14px;")
        freq_header.addWidget(lbl_f)
        freq_header.addStretch()
        freq_header.addWidget(self.lbl_synth_freq_val)
        
        self.slider_synth_freq = QSlider(Qt.Orientation.Horizontal, card)
        self.slider_synth_freq.setRange(55, 1200)
        self.slider_synth_freq.setValue(440)
        self.slider_synth_freq.valueChanged.connect(self._on_synth_slider_changed)
        
        freq_box.addLayout(freq_header)
        freq_box.addWidget(self.slider_synth_freq)
        card_layout.addLayout(freq_box)
        
        # Boutons de présélection de notes courantes
        presets_label = QLabel("Présélections rapides (Notes standard) :", card)
        presets_label.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 12px;")
        card_layout.addWidget(presets_label)
        
        presets_grid = QHBoxLayout()
        presets_grid.setSpacing(8)
        
        presets = [
            ("Mi 2 (82.4 Hz)", 82.41),
            ("La 2 (110 Hz)", 110.0),
            ("Ré 3 (146.8 Hz)", 146.83),
            ("Sol 3 (196 Hz)", 196.0),
            ("Si 3 (246.9 Hz)", 246.94),
            ("Mi 4 (329.6 Hz)", 329.63),
            ("La 4 (440 Hz)", 440.0),
            ("La 4 désaccordé (+15c)", 443.83)
        ]
        
        for name, f_val in presets:
            btn = QPushButton(name, card)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_BG_TERTIARY};
                    color: {COLOR_TEXT_PRIMARY};
                    border: 1px solid {COLOR_BORDER_GOLD};
                    border-radius: 6px;
                    padding: 6px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: #242017;
                    border: 1px solid {COLOR_ACCENT_GOLD};
                    color: {COLOR_ACCENT_GOLD_BRIGHT};
                }}
            """)
            btn.clicked.connect(lambda _, val=f_val: self._set_synth_preset(val))
            presets_grid.addWidget(btn)
            
        card_layout.addLayout(presets_grid)
        
        # Bouton d'activation du synthétiseur
        self.btn_synth_toggle = QPushButton("DÉMARRER LE GÉNÉRATEUR SYNTHÉTIQUE", card)
        self.btn_synth_toggle.setFixedHeight(46)
        self.btn_synth_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_synth_toggle.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #E5C158, stop:1 #B88E28);
                color: #0A0B0E;
                border: 1px solid #F5D77F;
                border-radius: 8px;
                font-weight: 800;
                font-size: 13px;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F3D578, stop:1 #CCA338);
            }
        """)
        self.btn_synth_toggle.clicked.connect(self._toggle_synthetic_generator)
        card_layout.addWidget(self.btn_synth_toggle)
        
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _create_theory_page(self) -> QWidget:
        """Construit la page récapitulant les formules mathématiques et la théorie DSP."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        
        browser = QTextBrowser(page)
        browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {COLOR_BG_SECONDARY};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER_GOLD};
                border-radius: 16px;
                padding: 24px;
                font-size: 13px;
                line-height: 1.6;
            }}
        """)
        
        content = f"""
        <h2 style="color: {COLOR_ACCENT_GOLD}; margin-top: 0; font-size: 18px; letter-spacing: 0.8px;">Fondements Théoriques du Traitement Numérique du Signal</h2>
        <p>Ce système implémente une chaîne complète d'acquisition, de transformation fréquentielle et d'estimation robuste de hauteur musicale :</p>
        
        <h3 style="color: {COLOR_ACCENT_GOLD_BRIGHT}; font-size: 14px; margin-top: 18px;">1. Échantillonnage & Théorème de Shannon-Nyquist</h3>
        <p>Le signal acoustique continu <i>x(t)</i> est discrétisé à la fréquence d'échantillonnage <b>f<sub>s</sub> = 44100 Hz</b>. 
        Selon le critère de Nyquist, la fréquence maximale représentable sans repliement (aliasing) est <b>f<sub>max</sub> = f<sub>s</sub> / 2 = 22050 Hz</b>, 
        couvrant l'intégralité du spectre audible humain (20 Hz - 20000 Hz).</p>
        
        <h3 style="color: {COLOR_ACCENT_GOLD_BRIGHT}; font-size: 14px; margin-top: 18px;">2. Fenêtrage Temporel de Hamming</h3>
        <p>Pour limiter la fuite spectrale (spectral leakage) due à la troncature d'une trame de taille <i>N = 4096</i>, 
        la fenêtre de Hamming est appliquée :</p>
        <pre style="background: {COLOR_BG_PRIMARY}; border: 1px solid {COLOR_BORDER_GOLD}; padding: 10px 14px; border-radius: 6px; color: {COLOR_ACCENT_GOLD_BRIGHT}; font-family: monospace;">w[n] = 0.54 - 0.46 * cos(2 * pi * n / (N - 1)),  0 &le; n &lt; N</pre>
        <p>Elle offre une réjection des lobes secondaires de <b>-43 dB</b>, évitant l'apparition de fausses harmoniques spectrales.</p>
        
        <h3 style="color: {COLOR_ACCENT_GOLD_BRIGHT}; font-size: 14px; margin-top: 18px;">3. Transformée de Fourier Discrète (DFT / FFT)</h3>
        <p>La projection fréquentielle discrète est définie par :</p>
        <pre style="background: {COLOR_BG_PRIMARY}; border: 1px solid {COLOR_BORDER_GOLD}; padding: 10px 14px; border-radius: 6px; color: {COLOR_ACCENT_GOLD_BRIGHT}; font-family: monospace;">X[k] = &Sigma; x[n] * w[n] * exp(-j * 2 * pi * k * n / N)</pre>
        <p>L'algorithme FFT de Cooley-Tukey calcule cette transformation en complexité <b>O(N log N)</b> au lieu de <b>O(N<sup>2</sup>)</b>.</p>
        
        <h3 style="color: {COLOR_ACCENT_GOLD_BRIGHT}; font-size: 14px; margin-top: 18px;">4. Extraction de Fondamentale : Algorithme YIN & HPS</h3>
        <p>Face au problème de la fondamentale manquante (où les harmoniques sont plus puissantes que f<sub>0</sub>), 
        l'algorithme YIN utilise la fonction de différence cumulée normalisée :</p>
        <pre style="background: {COLOR_BG_PRIMARY}; border: 1px solid {COLOR_BORDER_GOLD}; padding: 10px 14px; border-radius: 6px; color: {COLOR_ACCENT_GOLD_BRIGHT}; font-family: monospace;">d'(tau) = d(tau) / [ (1/tau) * &Sigma; d(j) ]</pre>
        <p>Associée à une <b>interpolation parabolique quadratique</b>, la résolution fréquentielle atteint une précision inférieure au centime de demi-ton (sub-cent).</p>
        
        <h3 style="color: {COLOR_ACCENT_GOLD_BRIGHT}; font-size: 14px; margin-top: 18px;">5. Tempérament Égal & Calcul des Cents</h3>
        <p>La conversion en note chromatique (avec La4 = 440 Hz) suit la loi logarithmique :</p>
        <pre style="background: {COLOR_BG_PRIMARY}; border: 1px solid {COLOR_BORDER_GOLD}; padding: 10px 14px; border-radius: 6px; color: {COLOR_ACCENT_GOLD_BRIGHT}; font-family: monospace;">m = 69 + 12 * log2(f / 440.0)
&Delta;c = 1200 * log2(f / f_cible)</pre>
        <p>Un demi-ton correspond à 100 cents. La zone d'accordage parfaite est définie pour <b>|&Delta;c| &le; 4 cents</b>.</p>
        """
        browser.setHtml(content)
        layout.addWidget(browser)
        return page

    def _create_settings_page(self) -> QWidget:
        """Construit la page des paramètres de configuration et d'étalonnage."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        card = QFrame(page)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BG_SECONDARY};
                border: 1px solid {COLOR_BORDER_GOLD};
                border-radius: 16px;
                padding: 20px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        
        lbl_head = QLabel("PARAMÈTRES DU MOTEUR DSP & ÉTALONNAGE", card)
        lbl_head.setStyleSheet(f"color: {COLOR_ACCENT_GOLD}; font-size: 15px; font-weight: 700; letter-spacing: 1px;")
        card_layout.addWidget(lbl_head)
        
        grid = QGridLayout()
        grid.setSpacing(16)
        
        # 1. Diapason de référence La 4
        lbl_pitch = QLabel("Diapason de référence (La 4) :", card)
        self.lbl_pitch_val = QLabel("440.0 Hz", card)
        self.lbl_pitch_val.setStyleSheet(f"color: {COLOR_ACCENT_GOLD}; font-weight: 700;")
        
        self.slider_pitch = QSlider(Qt.Orientation.Horizontal, card)
        self.slider_pitch.setRange(430, 450)
        self.slider_pitch.setValue(440)
        self.slider_pitch.valueChanged.connect(self._on_pitch_slider_changed)
        
        grid.addWidget(lbl_pitch, 0, 0)
        grid.addWidget(self.lbl_pitch_val, 0, 1)
        grid.addWidget(self.slider_pitch, 0, 2)
        
        # 2. Méthode d'estimation de pitch
        lbl_algo = QLabel("Algorithme de détection F0 :", card)
        self.combo_algo = QComboBox(card)
        self.combo_algo.addItems([
            "YIN (Recommandé - De Cheveigné & Kawahara)",
            "HPS (Harmonic Product Spectrum)",
            "Autocorrélation Normalisée (ACF)",
            "Pic FFT Interpolé Parabolique",
            "Hybride (YIN + HPS)"
        ])
        self.combo_algo.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLOR_BG_TERTIARY};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER_GOLD};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QComboBox:hover {{
                border: 1px solid {COLOR_ACCENT_GOLD};
            }}
        """)
        self.combo_algo.currentIndexChanged.connect(self._on_algo_changed)
        
        grid.addWidget(lbl_algo, 1, 0)
        grid.addWidget(self.combo_algo, 1, 2)
        
        # 3. Type de fenêtre temporelle
        lbl_win = QLabel("Fenêtre de pondération spectrale :", card)
        self.combo_win = QComboBox(card)
        self.combo_win.addItems([
            "Hamming (Standard recommandé)",
            "Hann",
            "Blackman (Haute réjection)",
            "Rectangulaire (Sans fenêtre)"
        ])
        self.combo_win.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLOR_BG_TERTIARY};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER_GOLD};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QComboBox:hover {{
                border: 1px solid {COLOR_ACCENT_GOLD};
            }}
        """)
        self.combo_win.currentIndexChanged.connect(self._on_window_changed)
        
        grid.addWidget(lbl_win, 2, 0)
        grid.addWidget(self.combo_win, 2, 2)
        
        card_layout.addLayout(grid)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _navigate_to_page(self, index: int) -> None:
        """Bascule la vue active du QStackedWidget."""
        self.pages_stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

    def _populate_audio_devices(self) -> None:
        """Remplit la liste des périphériques audio disponibles."""
        self.device_combo.clear()
        devices = self.audio_processor.capture_device.get_available_devices()
        
        if not devices:
            self.device_combo.addItem("Aucun périphérique micro détecté", -1)
            return
            
        selected_idx = 0
        for i, dev in enumerate(devices):
            display_name = f"{dev['name'][:30]}"
            self.device_combo.addItem(display_name, dev['index'])
            if dev['is_default']:
                selected_idx = i
                
        self.device_combo.setCurrentIndex(selected_idx)

    def _toggle_microphone(self) -> None:
        """Démarre ou arrête la capture audio du microphone."""
        if self.audio_processor.capture_device.is_running and not self.audio_processor.capture_device.is_synthetic_mode:
            self.audio_processor.stop_listening()
            self.btn_toggle_mic.setText("DÉMARRER LE MICRO")
            self.btn_toggle_mic.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #E5C158, stop:1 #B88E28);
                    color: #0A0B0E;
                    border: 1px solid #F5D77F;
                    border-radius: 8px;
                    font-size: 12px;
                    font-weight: 800;
                    letter-spacing: 1.2px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F3D578, stop:1 #CCA338);
                }
            """)
            self.tuner_view.update_tuner_state(None, 0.0, is_active=False)
        else:
            dev_idx = self.device_combo.currentData()
            if dev_idx is None or dev_idx < 0:
                QMessageBox.warning(self, "Erreur Microphone", "Aucun microphone disponible sélectionné.")
                return
                
            success = self.audio_processor.start_listening(device_index=dev_idx)
            if success:
                self.btn_toggle_mic.setText("ARRÊTER L'ÉCOUTE")
                self.btn_toggle_mic.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #B83A3A, stop:1 #801C1C);
                        color: #FAF8F2;
                        border: 1px solid #E05858;
                        border-radius: 8px;
                        font-size: 12px;
                        font-weight: 800;
                        letter-spacing: 1.2px;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #CC4444, stop:1 #962525);
                    }
                """)
            else:
                err = self.audio_processor.capture_device.error_message
                QMessageBox.critical(self, "Erreur d'acquisition audio", f"Échec de l'accès au microphone :\n{err}")

    def _toggle_synthetic_generator(self) -> None:
        """Active ou désactive le générateur de test synthétique."""
        if self.audio_processor.capture_device.is_synthetic_mode:
            self.audio_processor.stop_listening()
            self.btn_synth_toggle.setText("DÉMARRER LE GÉNÉRATEUR SYNTHÉTIQUE")
            self.btn_synth_toggle.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #E5C158, stop:1 #B88E28);
                    color: #0A0B0E;
                    border: 1px solid #F5D77F;
                    border-radius: 8px;
                    font-weight: 800;
                    font-size: 13px;
                    letter-spacing: 1px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F3D578, stop:1 #CCA338);
                }
            """)
            self.tuner_view.update_tuner_state(None, 0.0, is_active=False)
        else:
            freq = float(self.slider_synth_freq.value())
            waveforms = ['harmonics', 'sine', 'missing_fundamental', 'noisy']
            wave = waveforms[self.synth_wave_combo.currentIndex()]
            
            self.audio_processor.start_synthetic_generator(frequency=freq, waveform=wave)
            self.btn_synth_toggle.setText("ARRÊTER LE GÉNÉRATEUR SYNTHÉTIQUE")
            self.btn_synth_toggle.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #B83A3A, stop:1 #801C1C);
                    color: #FAF8F2;
                    border: 1px solid #E05858;
                    border-radius: 8px;
                    font-weight: 800;
                    font-size: 13px;
                    letter-spacing: 1px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #CC4444, stop:1 #962525);
                }
            """)

    def _on_synth_slider_changed(self, value: int) -> None:
        """Met à jour la fréquence synthétisée."""
        f = float(value)
        self.lbl_synth_freq_val.setText(f"{f:.1f} Hz")
        if self.audio_processor.capture_device.is_synthetic_mode:
            self.audio_processor.update_synthetic_generator(frequency=f)

    def _set_synth_preset(self, freq: float) -> None:
        """Applique une fréquence de note prédéterminée."""
        self.slider_synth_freq.setValue(int(freq))
        self.lbl_synth_freq_val.setText(f"{freq:.1f} Hz")
        if self.audio_processor.capture_device.is_synthetic_mode:
            self.audio_processor.update_synthetic_generator(frequency=freq)

    def _update_synthetic_params(self) -> None:
        """Met à jour le type d'onde synthétisé."""
        waveforms = ['harmonics', 'sine', 'missing_fundamental', 'noisy']
        wave = waveforms[self.synth_wave_combo.currentIndex()]
        if self.audio_processor.capture_device.is_synthetic_mode:
            self.audio_processor.update_synthetic_generator(waveform=wave)

    def _on_pitch_slider_changed(self, value: int) -> None:
        """Met à jour le diapason La4 de référence."""
        pitch = float(value)
        self.lbl_pitch_val.setText(f"{pitch:.1f} Hz")
        self.audio_processor.set_concert_pitch(pitch)

    def _on_algo_changed(self, index: int) -> None:
        """Change la méthode d'estimation F0."""
        methods = ["yin", "hps", "autocorr", "fft_peak", "hybrid"]
        self.audio_processor.set_pitch_method(methods[index])

    def _on_window_changed(self, index: int) -> None:
        """Change la fenêtre de pondération."""
        windows = ["hamming", "hann", "blackman", "rectangular"]
        self.audio_processor.set_window_type(windows[index])

    def _on_audio_frame_received(self, frame: AudioAnalysisFrame) -> None:
        """
        Slot exécuté dans le thread principal GUI à chaque trame d'analyse audio :
        Mise à jour du VU-mètre, de l'accordeur et du spectrogramme.
        """
        # 1. Mise à jour du VU-mètre
        db_level = max(-60, int(frame.pitch_result.rms_db))
        self.vu_progress.setValue(db_level)
        self.lbl_vu_db.setText(f"{frame.pitch_result.rms_db:.1f} dB")
        
        # 2. Mise à jour de l'accordeur chromatique
        is_active = (
            self.audio_processor.capture_device.is_running and 
            frame.pitch_result.is_voiced and 
            frame.note_info is not None
        )
        self.tuner_view.update_tuner_state(
            note_info=frame.note_info if is_active else None,
            confidence=frame.pitch_result.confidence,
            is_active=is_active
        )
        
        # 3. Mise à jour de la vue spectrale
        self.spectrum_view.update_frame(frame)

    def closeEvent(self, event) -> None:
        """Arrêt propre des threads audio lors de la fermeture."""
        self.audio_processor.stop_listening()
        event.accept()
