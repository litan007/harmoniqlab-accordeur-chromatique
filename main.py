"""
Point d'entrée principal pour l'application HarmoniqLab :
Accordeur Chromatique et Analyseur de Signal Numérique en Temps Réel.
"""

import sys
import os
import tempfile

# Configuration de variables d'environnement indispensables
os.environ.setdefault('MPLCONFIGDIR', tempfile.gettempdir())

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from src.gui.main_window import MainWindow


def main():
    """Fonction principale de démarrage de l'application PyQt6."""
    # Active la prise en charge des écrans haute résolution (High DPI)
    app = QApplication(sys.argv)
    app.setApplicationName("HarmoniqLab")
    app.setApplicationDisplayName("HarmoniqLab - Accordeur Chromatique DSP")
    app.setOrganizationName("DSP Engineering Group")
    
    # Création et affichage de la fenêtre principale
    window = MainWindow()
    
    # Vérification d'un argument éventuel pour démarrage direct
    if "--synthetic" in sys.argv:
        window.audio_processor.start_synthetic_generator(440.0, 'harmonics')
        window.btn_synth_toggle.setText("ARRÊTER LE GÉNÉRATEUR SYNTHÉTIQUE")
        
    window.show()
    
    # Exécution de la boucle d'événements
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
