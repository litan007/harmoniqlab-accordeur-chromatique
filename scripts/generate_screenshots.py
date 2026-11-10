"""
Script d'automatisation pour la capture d'écrans réels de l'application
dans différents états acoustiques pour le rapport universitaire et le README.
"""

import sys
import os
import time
import tempfile
import numpy as np

# Ajouter la racine du projet au sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault('MPLCONFIGDIR', tempfile.gettempdir())

from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def generate_harmonic_signal(freq: float, sample_rate: int = 44100, length: int = 4096) -> np.ndarray:
    """Génère une trame audio réaliste d'instrument avec fondamentale et harmoniques."""
    t = np.arange(length) / sample_rate
    # Timbre riche type instrument à corde
    sig = (
        0.70 * np.sin(2.0 * np.pi * freq * t) +
        0.35 * np.sin(2.0 * np.pi * 2 * freq * t) +
        0.18 * np.sin(2.0 * np.pi * 3 * freq * t) +
        0.08 * np.sin(2.0 * np.pi * 4 * freq * t) +
        np.random.normal(0, 0.01, length)
    )
    return np.clip(sig, -1.0, 1.0).astype(np.float32)


def capture_all():
    app = QApplication.instance() or QApplication(sys.argv)
    
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "captures"))
    os.makedirs(output_dir, exist_ok=True)
    
    window = MainWindow()
    window.resize(1180, 780)
    window.show()
    app.processEvents()
    
    print("Génération des captures réelles de l'application...")
    
    # 1. Interface principale en attente
    window._navigate_to_page(0)
    window.tuner_view.update_tuner_state(None, 0.0, is_active=False)
    app.processEvents()
    p1 = os.path.join(output_dir, "01_interface_principale.png")
    window.grab().save(p1)
    print(f"Sauvegardé : {p1}")
    
    # 2. Détection d'une note parfaitement accordée (La 4 = 440.0 Hz)
    sig_in_tune = generate_harmonic_signal(440.0)
    window.audio_processor.capture_device.is_running = True
    frame_in_tune = window.audio_processor.process_frame(sig_in_tune)
    window._on_audio_frame_received(frame_in_tune)
    # Laisse l'aiguille se stabiliser
    for _ in range(25):
        window.tuner_view.gauge._update_needle_physics()
        app.processEvents()
        time.sleep(0.01)
    p2 = os.path.join(output_dir, "02_detection_note_accorde.png")
    window.grab().save(p2)
    print(f"Sauvegardé : {p2}")
    
    # 3. Note trop grave (La 4 à 435.0 Hz -> -19.8 cents)
    sig_flat = generate_harmonic_signal(435.0)
    frame_flat = window.audio_processor.process_frame(sig_flat)
    window._on_audio_frame_received(frame_flat)
    for _ in range(25):
        window.tuner_view.gauge._update_needle_physics()
        app.processEvents()
        time.sleep(0.01)
    p3 = os.path.join(output_dir, "03_note_trop_grave.png")
    window.grab().save(p3)
    print(f"Sauvegardé : {p3}")
    
    # 4. Note trop aiguë (La 4 à 445.0 Hz -> +19.6 cents)
    sig_sharp = generate_harmonic_signal(445.0)
    frame_sharp = window.audio_processor.process_frame(sig_sharp)
    window._on_audio_frame_received(frame_sharp)
    for _ in range(25):
        window.tuner_view.gauge._update_needle_physics()
        app.processEvents()
        time.sleep(0.01)
    p4 = os.path.join(output_dir, "04_note_trop_aigue.png")
    window.grab().save(p4)
    print(f"Sauvegardé : {p4}")
    
    # 5. Vue Spectre Fréquentiel FFT et Oscilloscope
    window._navigate_to_page(1)
    frame_spec = window.audio_processor.process_frame(sig_in_tune)
    window._on_audio_frame_received(frame_spec)
    app.processEvents()
    time.sleep(0.1)
    p5 = os.path.join(output_dir, "05_spectre_frequentiel_fft.png")
    window.grab().save(p5)
    print(f"Sauvegardé : {p5}")
    
    # 6. Vue Générateur Synthétique
    window._navigate_to_page(2)
    app.processEvents()
    p6 = os.path.join(output_dir, "06_generateur_synthetique.png")
    window.grab().save(p6)
    print(f"Sauvegardé : {p6}")
    
    # 7. Vue Théorie & Maths
    window._navigate_to_page(3)
    app.processEvents()
    p7 = os.path.join(output_dir, "07_theorie_dsp.png")
    window.grab().save(p7)
    print(f"Sauvegardé : {p7}")
    
    # Nettoyage
    window.audio_processor.capture_device.is_running = False
    window.close()
    
    # Supprimer fichier test temporaire si présent
    if os.path.exists("test.png"):
        os.remove("test.png")
        
    print("Toutes les captures d'écran réelles ont été générées avec succès !")


if __name__ == "__main__":
    capture_all()
