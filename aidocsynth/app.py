from PySide6.QtWidgets import QApplication, QMainWindow
import sys

def main():
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setWindowTitle("AIDocSynth stub")
    win.resize(600, 400)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
