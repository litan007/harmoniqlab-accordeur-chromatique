"""
Widget d'affichage graphique du spectre fréquentiel FFT et du signal temporel
basé sur Matplotlib intégré dans PyQt6 avec thème sombre haute visibilité.
"""

import os
import tempfile
# Sécurisation du dossier de cache Matplotlib
os.environ.setdefault('MPLCONFIGDIR', tempfile.gettempdir())

from typing import Optional, List, Tuple
import numpy as np

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QFrame, QButtonGroup
)
from PyQt6.QtCore import Qt

from src.utils.constants import (
    COLOR_BG_PRIMARY,
    COLOR_BG_SECONDARY,
    COLOR_BG_TERTIARY,
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_CYAN,
    COLOR_IN_TUNE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_MUTED,
    COLOR_BORDER,
    COLOR_GRID_LINES,
    COLOR_WARNING_ORANGE
)
from src.audio.audio_processor import AudioAnalysisFrame


class SpectrumWidget(QWidget):
    """
    Composant d'analyse spectrale et temporelle en temps réel.
    Affiche le spectre unilatéral FFT (avec détection de f0 et harmoniques)
    et l'oscilloscope temporel (signal fenêtré par Hamming).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.max_freq_display = 2500.0
        self.scale_mode = "db"  # "db" ou "linear"
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        
        # Barre d'outils et de contrôle du graphique
        controls_frame = QFrame(self)
        controls_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BG_SECONDARY};
                border: 1px solid #362F1E;
                border-radius: 12px;
                padding: 4px;
            }}
        """)
        controls_layout = QHBoxLayout(controls_frame)
        controls_layout.setContentsMargins(12, 6, 12, 6)
        controls_layout.setSpacing(16)
        
        lbl_title = QLabel("ANALYSE SPECTRALE & TEMPORELLE (FFT)", controls_frame)
        lbl_title.setStyleSheet("color: #D4AF37; font-weight: 700; font-size: 13px; letter-spacing: 1.5px;")
        controls_layout.addWidget(lbl_title)
        
        controls_layout.addStretch()
        
        # Sélecteur d'échelle (dB vs Linéaire)
        lbl_scale = QLabel("Échelle :", controls_frame)
        lbl_scale.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 11px;")
        controls_layout.addWidget(lbl_scale)
        
        self.scale_combo = QComboBox(controls_frame)
        self.scale_combo.addItems(["Décibels (dB FS)", "Amplitude Linéaire"])
        self.scale_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLOR_BG_TERTIARY};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid #3D3520;
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 11px;
            }}
            QComboBox:hover {{
                border: 1px solid #D4AF37;
            }}
        """)
        self.scale_combo.currentIndexChanged.connect(self._on_scale_changed)
        controls_layout.addWidget(self.scale_combo)
        
        # Sélecteur de plage fréquentielle max
        lbl_span = QLabel("Plage :", controls_frame)
        lbl_span.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 11px;")
        controls_layout.addWidget(lbl_span)
        
        self.span_combo = QComboBox(controls_frame)
        self.span_combo.addItems(["0 - 1000 Hz (Guitare/Basse)", "0 - 2500 Hz (Standard)", "0 - 5000 Hz (Étendu)"])
        self.span_combo.setCurrentIndex(1)
        self.span_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLOR_BG_TERTIARY};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid #3D3520;
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 11px;
            }}
            QComboBox:hover {{
                border: 1px solid #D4AF37;
            }}
        """)
        self.span_combo.currentIndexChanged.connect(self._on_span_changed)
        controls_layout.addWidget(self.span_combo)
        
        main_layout.addWidget(controls_frame)
        
        # Création de la figure Matplotlib avec style sombre
        self.figure = Figure(figsize=(8, 6), dpi=100, facecolor=COLOR_BG_SECONDARY)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet(f"background-color: {COLOR_BG_SECONDARY}; border: 1px solid #2B2517; border-radius: 12px;")
        main_layout.addWidget(self.canvas)
        
        # Création des deux sous-graphiques (Spectre en haut, Forme d'onde en bas)
        self.ax_spectrum = self.figure.add_subplot(2, 1, 1)
        self.ax_waveform = self.figure.add_subplot(2, 1, 2)
        
        self._setup_axes()

    def _setup_axes(self) -> None:
        """Configure le design sombre et les labels des graphiques."""
        self.figure.subplots_adjust(left=0.08, right=0.96, top=0.93, bottom=0.09, hspace=0.38)
        
        # 1. Graphique du spectre
        ax_s = self.ax_spectrum
        ax_s.set_facecolor(COLOR_BG_PRIMARY)
        ax_s.set_title("Spectre d'Amplitude (DFT / FFT unilatérale pondérée par Hamming)", color=COLOR_TEXT_PRIMARY, fontsize=10, fontweight='bold', pad=8)
        ax_s.set_xlabel("Fréquence (Hz)", color=COLOR_TEXT_MUTED, fontsize=9)
        ax_s.set_ylabel("Amplitude (dB FS)", color=COLOR_TEXT_MUTED, fontsize=9)
        ax_s.set_xlim(0, self.max_freq_display)
        ax_s.set_ylim(-80, 5)
        ax_s.tick_params(colors=COLOR_TEXT_MUTED, labelsize=8)
        ax_s.grid(True, color=COLOR_GRID_LINES, linestyle='--', linewidth=0.7, alpha=0.8)
        for spine in ax_s.spines.values():
            spine.set_color("#383120")
            
        # Ligne de tracé du spectre en or métallisé
        freq_init = np.linspace(0, self.max_freq_display, 512)
        mag_init = np.full_like(freq_init, -80.0)
        self.line_spectrum, = ax_s.plot(freq_init, mag_init, color="#D4AF37", linewidth=1.6, label="Spectre")
        
        # Ligne verticale indiquant la fondamentale f0
        self.line_f0 = ax_s.axvline(x=0, color=COLOR_IN_TUNE, linestyle='--', linewidth=2.0, alpha=0.9, label="Fondamentale f0")
        self.line_f0.set_visible(False)
        
        # Marqueurs pour les pics spectraux (or champagne brillant)
        self.peaks_scatter = ax_s.scatter([], [], color="#F3D578", s=38, zorder=5, label="Pics harmoniques")
        
        # Texte informatif f0
        self.text_f0 = ax_s.text(0.02, 0.88, "", transform=ax_s.transAxes, color=COLOR_IN_TUNE, fontsize=9, fontweight='bold')
        
        # 2. Graphique temporel (Oscilloscope)
        ax_w = self.ax_waveform
        ax_w.set_facecolor(COLOR_BG_PRIMARY)
        ax_w.set_title("Oscilloscope Temporel (Signal brut et enveloppe de Hamming)", color=COLOR_TEXT_PRIMARY, fontsize=10, fontweight='bold', pad=8)
        ax_w.set_xlabel("Temps (ms)", color=COLOR_TEXT_MUTED, fontsize=9)
        ax_w.set_ylabel("Amplitude", color=COLOR_TEXT_MUTED, fontsize=9)
        ax_w.set_ylim(-1.05, 1.05)
        ax_w.tick_params(colors=COLOR_TEXT_MUTED, labelsize=8)
        ax_w.grid(True, color=COLOR_GRID_LINES, linestyle='--', linewidth=0.7, alpha=0.8)
        for spine in ax_w.spines.values():
            spine.set_color("#383120")
            
        t_init = np.linspace(0, 50, 512)
        w_init = np.zeros_like(t_init)
        self.line_wave, = ax_w.plot(t_init, w_init, color="#D4AF37", linewidth=1.3, label="Signal temporel")
        self.line_env, = ax_w.plot(t_init, w_init, color="#8C7335", linestyle=':', linewidth=1.2, alpha=0.8, label="Fenêtre Hamming")
        
        self.canvas.draw()

    def _on_scale_changed(self, index: int) -> None:
        """Bascule entre affichage en décibels (dB) et linéaire."""
        if index == 0:
            self.scale_mode = "db"
            self.ax_spectrum.set_ylabel("Amplitude (dB FS)", color=COLOR_TEXT_MUTED, fontsize=9)
            self.ax_spectrum.set_ylim(-80, 5)
        else:
            self.scale_mode = "linear"
            self.ax_spectrum.set_ylabel("Amplitude Linéaire", color=COLOR_TEXT_MUTED, fontsize=9)
            self.ax_spectrum.set_ylim(0, 1.05)
        self.canvas.draw_idle()

    def _on_span_changed(self, index: int) -> None:
        """Modifie la plage de fréquences visualisées."""
        if index == 0:
            self.max_freq_display = 1000.0
        elif index == 1:
            self.max_freq_display = 2500.0
        else:
            self.max_freq_display = 5000.0
            
        self.ax_spectrum.set_xlim(0, self.max_freq_display)
        self.canvas.draw_idle()

    def update_frame(self, frame: AudioAnalysisFrame) -> None:
        """
        Met à jour les graphiques à partir de la trame d'analyse audio calculée.
        Optimisé pour un rafraîchissement fluide en temps réel.
        """
        if len(frame.frequencies) == 0:
            return
            
        # Filtrer la zone visible
        mask = frame.frequencies <= self.max_freq_display
        freqs_vis = frame.frequencies[mask]
        
        if self.scale_mode == "db":
            mags_vis = frame.magnitudes_db[mask]
        else:
            mags_vis = frame.magnitudes_linear[mask]
            
        # Mise à jour du tracé spectral
        self.line_spectrum.set_data(freqs_vis, mags_vis)
        
        # Mise à jour de la fréquence fondamentale f0
        f0 = frame.pitch_result.frequency
        if frame.pitch_result.is_voiced and 0 < f0 <= self.max_freq_display:
            self.line_f0.set_xdata([f0, f0])
            self.line_f0.set_visible(True)
            
            note_str = frame.note_info.full_name_en if frame.note_info else ""
            cents_str = f" ({frame.note_info.cents_deviation:+.1f} c)" if frame.note_info else ""
            self.text_f0.set_text(f"f0 = {f0:.1f} Hz  [{note_str}{cents_str}]")
        else:
            self.line_f0.set_visible(False)
            self.text_f0.set_text("")
            
        # Mise à jour des pics spectraux
        if frame.peaks:
            peak_f = [p[0] for p in frame.peaks if p[0] <= self.max_freq_display]
            if self.scale_mode == "db":
                peak_m = [20.0 * np.log10(max(p[1], 1e-4)) for p in frame.peaks if p[0] <= self.max_freq_display]
            else:
                peak_m = [p[1] for p in frame.peaks if p[0] <= self.max_freq_display]
                
            pts = np.column_stack((peak_f, peak_m)) if peak_f else np.empty((0, 2))
            self.peaks_scatter.set_offsets(pts)
        else:
            self.peaks_scatter.set_offsets(np.empty((0, 2)))
            
        # Mise à jour de l'oscilloscope temporel (signal récent)
        raw_sig = frame.raw_signal
        N = len(raw_sig)
        if N > 0:
            # Afficher les 1024 derniers échantillons en millisecondes
            chunk_display = min(1024, N)
            sub_sig = raw_sig[-chunk_display:]
            t_ms = (np.arange(chunk_display) / frame.sample_rate) * 1000.0
            
            self.line_wave.set_data(t_ms, sub_sig)
            
            # Enveloppe de Hamming normalisée superposée
            from src.signal.fourier import get_window
            ham_win = get_window('hamming', chunk_display)
            max_val = max(0.1, np.max(np.abs(sub_sig)))
            self.line_env.set_data(t_ms, ham_win * max_val)
            
            self.ax_waveform.set_xlim(0, t_ms[-1])
            
        self.canvas.draw_idle()
