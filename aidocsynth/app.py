from PySide6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMenu, QFrame, QSplashScreen, QLabel
from PySide6.QtGui import QIcon, QPixmap, QMovie
from PySide6.QtCore import Qt
from PySide6.QtUiTools import QUiLoader
import sys

# Wichtig: Importiert die kompilierten Ressourcen (Icons, etc.)
from .ui import qrc_resources
from .ui.drop_area import DropArea
from .controllers.main_controller import MainController
from .utils.worker import Worker
from .services.ocr_service import initialize_ocr

def main():
    app = QApplication(sys.argv)

    # Splash-Screen anzeigen
    # QSplashScreen unterstützt keine Animationen (QMovie), daher wird QLabel verwendet.
    splash = QLabel()
    splash.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint)
    movie = QMovie(":/aidocsynth/ui/resources/spinner.gif")
    splash.setMovie(movie)
    movie.start()
    splash.show()
    # Die Nachricht "Initialisiere OCR…" kann mit QLabel nicht direkt angezeigt werden,
    # aber der animierte Spinner zeigt an, dass die Anwendung lädt.
    
    loader = QUiLoader()
    win = loader.load("aidocsynth/ui/main_window.ui", None)
    
    # Ersetze den QFrame durch die DropArea
    frame = win.findChild(QFrame, "dropFrame")
    if frame:
        drop_area = DropArea()
        frame.layout().addWidget(drop_area)
    
        win.show()

    # Splash-Screen schließen, nachdem das OCR-Modell initialisiert wurde
    worker = Worker(initialize_ocr)
    def hide_splash(_): splash.finish(win)
    worker.sig.finished.connect(hide_splash)
    
    ctrl = MainController()
    if 'drop_area' in locals():
        drop_area.filesDropped.connect(ctrl.handle_drop)

    # Tray Icon
    icon = QIcon(":/app.png")
    tray = QSystemTrayIcon(icon, app)
    menu = QMenu()
    menu.addAction("Beenden", app.quit)
    tray.setContextMenu(menu)
    tray.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
