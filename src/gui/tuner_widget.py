"""
Widget graphique PyQt6 pour l'accordeur chromatique visuel haute précision.
Affiche un cadran analogique à aiguille dynamique (-50 à +50 cents),
un indicateur central géant de la note, et des indicateurs de justesse colorés.
"""

import math
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QRadialGradient,
    QLinearGradient, QPainterPath
)

from src.utils.constants import (
    COLOR_BG_PRIMARY,
    COLOR_BG_SECONDARY,
    COLOR_BG_TERTIARY,
    COLOR_IN_TUNE,
    COLOR_FLAT,
    COLOR_SHARP,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_DIMMED,
    COLOR_ACCENT_BLUE,
    COLOR_BORDER
)
from src.signal.note_converter import NoteInfo


class TunerGauge(QWidget):
    """
    Cadran circulaire dessiné avec QPainter représentant la déviation en cents (-50 à +50).
    Comprend une aiguille animée avec amortissement physique pour un mouvement fluide.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.target_cents: float = 0.0
        self.current_cents: float = 0.0
        self.is_active: bool = False
        self.status: str = "WAITING"  # 'IN_TUNE', 'FLAT', 'SHARP', 'WAITING'
        
        # Timer pour animation fluide de l'aiguille (60 FPS)
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._update_needle_physics)
        self._anim_timer.start(16)

    def set_cents(self, cents: float, active: bool = True, status: str = "IN_TUNE") -> None:
        """Met à jour la valeur cible des cents."""
        self.target_cents = float(cents)
        self.is_active = active
        self.status = status

    def _update_needle_physics(self) -> None:
        """Animation avec lissage exponentiel (amortissement doux)."""
        if not self.is_active:
            # Retour progressif au repos
            self.target_cents = 0.0
            
        # Facteur de lissage (interpolation linéaire amortie)
        smoothing = 0.22
        diff = self.target_cents - self.current_cents
        if abs(diff) > 0.01:
            self.current_cents += diff * smoothing
            self.update()
        elif diff != 0:
            self.current_cents = self.target_cents
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        center_x = width / 2.0
        center_y = height * 0.82
        radius = min(width * 0.44, height * 0.72)
        
        # 1. Dessin de l'arc de fond et filets dorés
        arc_rect = QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)
        
        # Angles en degrés : de 145° (gauche, -50 cents) à 35° (droite, +50 cents)
        start_angle_deg = 145.0
        end_angle_deg = 35.0
        span_total = start_angle_deg - end_angle_deg  # 110 degrés au total
        
        # Filet décoratif extérieur doré discret
        outer_deco_rect = QRectF(center_x - (radius + 8), center_y - (radius + 8), (radius + 8) * 2, (radius + 8) * 2)
        deco_pen = QPen(QColor("#38301B"), 1.2, Qt.PenStyle.SolidLine)
        painter.setPen(deco_pen)
        painter.drawArc(outer_deco_rect, int(33 * 16), int(114 * 16))
        
        # Tracé de la piste graduée principale
        track_pen = QPen(QColor(COLOR_BG_TERTIARY), 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(arc_rect, int(35 * 16), int(110 * 16))
        
        # 2. Zone verte centrale ("In-Tune Zone" : -4 à +4 cents)
        tune_center_deg = 90.0
        tune_half_span = (span_total / 100.0) * 4.0
        tune_pen = QPen(QColor(COLOR_IN_TUNE), 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
        painter.setPen(tune_pen)
        painter.drawArc(
            arc_rect,
            int((tune_center_deg - tune_half_span) * 16),
            int(tune_half_span * 2 * 16)
        )
        
        # 3. Graduations (Ticks) et libellés (-50, -40 ... 0 ... +40, +50)
        font_ticks = QFont("Segoe UI", 9, QFont.Weight.Medium)
        painter.setFont(font_ticks)
        
        for cents_val in range(-50, 51, 10):
            # Normalisation entre 0.0 (-50) et 1.0 (+50)
            norm = (cents_val + 50.0) / 100.0
            angle_deg = start_angle_deg - norm * span_total
            angle_rad = math.radians(angle_deg)
            
            # Position du rayon
            is_major = (cents_val % 20 == 0) or (cents_val == 0)
            tick_len = 16 if is_major else 10
            
            r_outer = radius - 8
            r_inner = r_outer - tick_len
            
            p_outer = QPointF(center_x + r_outer * math.cos(angle_rad), center_y - r_outer * math.sin(angle_rad))
            p_inner = QPointF(center_x + r_inner * math.cos(angle_rad), center_y - r_inner * math.sin(angle_rad))
            
            # Couleur du tick
            if cents_val == 0:
                tick_color = QColor(COLOR_IN_TUNE)
                pen_width = 3
            elif cents_val < 0:
                tick_color = QColor(COLOR_FLAT if abs(cents_val) > 4 else COLOR_IN_TUNE)
                pen_width = 2 if is_major else 1
            else:
                tick_color = QColor(COLOR_SHARP if cents_val > 4 else COLOR_IN_TUNE)
                pen_width = 2 if is_major else 1
                
            painter.setPen(QPen(tick_color, pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(p_inner, p_outer)
            
            # Étiquette textuelle pour les graduations majeures
            if is_major:
                r_text = r_inner - 14
                tx = center_x + r_text * math.cos(angle_rad)
                ty = center_y - r_text * math.sin(angle_rad)
                painter.setPen(QColor(COLOR_TEXT_MUTED))
                text_rect = QRectF(tx - 20, ty - 10, 40, 20)
                txt = f"{cents_val:+d}" if cents_val != 0 else "0"
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, txt)
                
        # 4. Aiguille mobile (Needle)
        cents_clamped = max(-50.0, min(50.0, self.current_cents))
        norm_needle = (cents_clamped + 50.0) / 100.0
        needle_angle_deg = start_angle_deg - norm_needle * span_total
        needle_angle_rad = math.radians(needle_angle_deg)
        
        # Couleur dynamique de l'aiguille
        if not self.is_active:
            needle_color = QColor(COLOR_TEXT_DIMMED)
        elif self.status == "IN_TUNE":
            needle_color = QColor(COLOR_IN_TUNE)
        elif self.status == "FLAT":
            needle_color = QColor(COLOR_FLAT)
        else:
            needle_color = QColor(COLOR_SHARP)
            
        needle_length = radius - 12
        needle_tip = QPointF(
            center_x + needle_length * math.cos(needle_angle_rad),
            center_y - needle_length * math.sin(needle_angle_rad)
        )
        
        # Ligne de l'aiguille avec reflet et lueur
        painter.setPen(QPen(needle_color, 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(center_x, center_y), needle_tip)
        
        # 5. Moyeu central (Pivot central métallique doré brossé)
        hub_radius = 12
        hub_gradient = QRadialGradient(center_x, center_y, hub_radius)
        hub_gradient.setColorAt(0.0, QColor("#FFF5D4" if self.is_active else "#635A46"))
        hub_gradient.setColorAt(0.35, QColor("#D4AF37" if self.is_active else "#3D3728"))
        hub_gradient.setColorAt(0.8, QColor("#856C28" if self.is_active else "#1F1B12"))
        hub_gradient.setColorAt(1.0, QColor("#0A0B0E"))
        
        painter.setPen(QPen(QColor("#4A3E20" if self.is_active else "#282315"), 2))
        painter.setBrush(QBrush(hub_gradient))
        painter.drawEllipse(QPointF(center_x, center_y), hub_radius, hub_radius)


class TunerWidget(QWidget):
    """
    Panneau principal d'accordeur chromatique moderne.
    Comprend le cadran à aiguille, le grand affichage de note,
    le badge d'état de justesse et les métriques acoustiques.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)
        
        # Carte centrale d'accordage (Finition Noir Onyx & Liseré Doré)
        self.card = QFrame(self)
        self.card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BG_SECONDARY};
                border: 1px solid #383120;
                border-radius: 18px;
            }}
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(12)
        
        # En-tête : Titre & Statut
        header_layout = QHBoxLayout()
        title_label = QLabel("ACCORDEUR CHROMATIQUE", self.card)
        title_label.setStyleSheet(f"""
            color: #D4AF37;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 2.2px;
        """)
        
        self.status_badge = QLabel("EN ATTENTE...", self.card)
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setStyleSheet(f"""
            background-color: {COLOR_BG_TERTIARY};
            color: {COLOR_TEXT_MUTED};
            border-radius: 12px;
            padding: 4px 14px;
            font-size: 12px;
            font-weight: 600;
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_badge)
        card_layout.addLayout(header_layout)
        
        # Cadran à aiguille
        self.gauge = TunerGauge(self.card)
        card_layout.addWidget(self.gauge)
        
        # Zone centrale géante de la note musicale
        note_container = QHBoxLayout()
        note_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.note_letter_label = QLabel("--", self.card)
        self.note_letter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.note_letter_label.setStyleSheet(f"""
            color: {COLOR_TEXT_PRIMARY};
            font-size: 78px;
            font-weight: 800;
            font-family: 'Segoe UI', Arial, sans-serif;
        """)
        
        self.octave_label = QLabel("", self.card)
        self.octave_label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
        self.octave_label.setStyleSheet(f"""
            color: {COLOR_ACCENT_BLUE};
            font-size: 36px;
            font-weight: 700;
            margin-bottom: 12px;
        """)
        
        note_container.addStretch()
        note_container.addWidget(self.note_letter_label)
        note_container.addWidget(self.octave_label)
        note_container.addStretch()
        card_layout.addLayout(note_container)
        
        # Sous-titre en solfège français
        self.solfege_label = QLabel("En attente d'un signal audio...", self.card)
        self.solfege_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.solfege_label.setStyleSheet(f"""
            color: {COLOR_TEXT_MUTED};
            font-size: 15px;
            font-weight: 500;
        """)
        card_layout.addWidget(self.solfege_label)
        
        # Grille de télémétrie numérique (Fréquences, écarts, confiance)
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)
        
        self.box_freq_measured = self._create_metric_card("FRÉQUENCE MESURÉE", "-- Hz")
        self.box_freq_target = self._create_metric_card("FRÉQUENCE CIBLE", "-- Hz")
        self.box_cents = self._create_metric_card("ÉCART EN CENTS", "0.0 cents")
        self.box_confidence = self._create_metric_card("INDICE CONFIANCE", "-- %")
        
        metrics_layout.addWidget(self.box_freq_measured['frame'])
        metrics_layout.addWidget(self.box_freq_target['frame'])
        metrics_layout.addWidget(self.box_cents['frame'])
        metrics_layout.addWidget(self.box_confidence['frame'])
        
        card_layout.addLayout(metrics_layout)
        main_layout.addWidget(self.card)

    def _create_metric_card(self, title: str, default_val: str):
        """Crée une tuile d'affichage de métrique acoustique."""
        frame = QFrame(self.card)
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: #0A0C10;
                border: 1px solid #2E2616;
                border-radius: 10px;
                padding: 6px;
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        
        lbl_title = QLabel(title, frame)
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet("color: #8E7D5C; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
        
        lbl_val = QLabel(default_val, frame)
        lbl_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_val.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 15px; font-weight: 700;")
        
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_val)
        
        return {'frame': frame, 'value': lbl_val}

    def update_tuner_state(
        self,
        note_info: Optional[NoteInfo],
        confidence: float = 0.0,
        is_active: bool = True
    ) -> None:
        """
        Met à jour l'affichage dynamique avec les données issues du processeur audio.
        """
        if not is_active or note_info is None:
            self.gauge.set_cents(0.0, active=False, status="WAITING")
            self.note_letter_label.setText("--")
            self.note_letter_label.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 78px; font-weight: 800;")
            self.octave_label.setText("")
            self.solfege_label.setText("En attente d'un signal audio...")
            
            self.status_badge.setText("EN ATTENTE DE SIGNAL...")
            self.status_badge.setStyleSheet(f"""
                background-color: {COLOR_BG_TERTIARY};
                color: {COLOR_TEXT_MUTED};
                border-radius: 12px;
                padding: 4px 14px;
                font-size: 12px;
                font-weight: 600;
            """)
            
            self.box_freq_measured['value'].setText("-- Hz")
            self.box_freq_target['value'].setText("-- Hz")
            self.box_cents['value'].setText("0.0 cents")
            self.box_confidence['value'].setText("-- %")
            return

        # Note valide détectée
        self.note_letter_label.setText(note_info.note_name_en)
        self.octave_label.setText(str(note_info.octave))
        self.solfege_label.setText(f"{note_info.note_name_fr} {note_info.octave}  (MIDI {note_info.midi_number})")
        
        cents = note_info.cents_deviation
        status = note_info.tuning_status
        
        # Mise à jour du cadran
        self.gauge.set_cents(cents, active=True, status=status)
        
        # Style selon statut
        if status == "IN_TUNE":
            badge_bg = "rgba(0, 230, 118, 0.20)"
            badge_color = COLOR_IN_TUNE
            badge_text = "PARFAITEMENT ACCORDÉ"
            note_color = COLOR_IN_TUNE
        elif status == "FLAT":
            badge_bg = "rgba(41, 182, 246, 0.20)"
            badge_color = COLOR_FLAT
            badge_text = "TROP GRAVE (BÉMOL)"
            note_color = COLOR_FLAT
        else:
            badge_bg = "rgba(255, 82, 82, 0.20)"
            badge_color = COLOR_SHARP
            badge_text = "TROP AIGU (DIÈSE)"
            note_color = COLOR_SHARP
            
        self.note_letter_label.setStyleSheet(f"color: {note_color}; font-size: 78px; font-weight: 800;")
        
        self.status_badge.setText(badge_text)
        self.status_badge.setStyleSheet(f"""
            background-color: {badge_bg};
            color: {badge_color};
            border: 1px solid {badge_color};
            border-radius: 12px;
            padding: 4px 14px;
            font-size: 12px;
            font-weight: 700;
        """)
        
        # Données numériques
        self.box_freq_measured['value'].setText(f"{note_info.measured_freq:.2f} Hz")
        self.box_freq_target['value'].setText(f"{note_info.target_freq:.2f} Hz")
        
        sign_cents = "+" if cents > 0 else ""
        self.box_cents['value'].setText(f"{sign_cents}{cents:.1f} cents")
        self.box_cents['value'].setStyleSheet(f"color: {badge_color}; font-size: 15px; font-weight: 700;")
        
        conf_pct = int(confidence * 100)
        self.box_confidence['value'].setText(f"{conf_pct} %")
