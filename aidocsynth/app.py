from PySide6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon
import sys

# Wichtig: Importiert die kompilierten Ressourcen (Icons, etc.)
from aidocsynth.ui import qrc_resources

def main():
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setWindowTitle("AIDocSynth stub")
    win.resize(600, 400)
    win.show()

            icon = QIcon(":/app.png")            # Ressource ab Schritt 7
    tray = QSystemTrayIcon(icon, app)
    menu = QMenu(); menu.addAction("Beenden", app.quit)
    tray.setContextMenu(menu); tray.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
