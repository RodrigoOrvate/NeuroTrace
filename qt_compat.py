"""
qt_compat.py — Camada de compatibilidade Qt

Tenta importar PySide6 primeiro (macOS ARM), e faz fallback para PyQt5 (Windows).
Isso permite que o mesmo código funcione em ambas as plataformas.
"""

try:
    # PySide6 — funciona em macOS ARM + Windows + Linux
    from PySide6.QtWidgets import (  # noqa: F401
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QLineEdit, QScrollArea, QFrame, QFileDialog,
        QMessageBox, QGraphicsDropShadowEffect, QSpinBox, QSizePolicy,
        QGroupBox, QGridLayout, QSpacerItem,
        QDialog, QProgressBar,
    )
    from PySide6.QtCore import (  # noqa: F401
        Qt, QPropertyAnimation, QEasingCurve, QSize, Signal, QTimer, QThread,
    )
    from PySide6.QtGui import (  # noqa: F401
        QFont, QIcon, QColor, QPalette, QFontDatabase, QPixmap,
    )

    # Alias de compatibilidade: pyqtSignal → Signal
    pyqtSignal = Signal

    QT_BACKEND = "PySide6"

except ImportError:
    # PyQt5 — fallback (Windows com PyQt5 instalado)
    from PyQt5.QtWidgets import (  # noqa: F401
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QLineEdit, QScrollArea, QFrame, QFileDialog,
        QMessageBox, QGraphicsDropShadowEffect, QSpinBox, QSizePolicy,
        QGroupBox, QGridLayout, QSpacerItem,
        QDialog, QProgressBar,
    )
    from PyQt5.QtCore import (  # noqa: F401
        Qt, QPropertyAnimation, QEasingCurve, QSize, pyqtSignal, QTimer, QThread,
    )
    from PyQt5.QtGui import (  # noqa: F401
        QFont, QIcon, QColor, QPalette, QFontDatabase, QPixmap,
    )

    QT_BACKEND = "PyQt5"
