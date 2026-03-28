"""
updater.py — Módulo de Auto-Atualização via GitHub Releases

Verifica se há uma versão mais recente do AUTOMATIZADO publicada
no GitHub Releases e, em caso positivo, baixa o novo .exe,
substitui o atual e reinicia o programa.
"""

import json
import os
import sys
import tempfile
import subprocess
from urllib.request import urlopen, Request
from urllib.error import URLError

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QColor

# ─── Configuração ─────────────────────────────────────────────
GITHUB_OWNER = "RodrigoOrvate"
GITHUB_REPO = "AUTOMATIZADO-RO"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
CURRENT_VERSION = "2.0.0"

# Cores reutilizadas do main.py
COLORS = {
    "bg":           "#0f0f1a",
    "card":         "#1a1a2e",
    "card_border":  "#2d2d4a",
    "accent":       "#ab3d4c",
    "accent_hover": "#c9505f",
    "text":         "#e8e8f0",
    "text_muted":   "#8888aa",
    "success":      "#4caf50",
    "danger":       "#ff4757",
}


def _parse_version(version_str: str) -> tuple:
    """Converte '1.2.3' em (1, 2, 3) para comparação."""
    clean = version_str.strip().lstrip("vV")
    parts = []
    for p in clean.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def is_frozen() -> bool:
    """Verifica se está rodando como executável empacotado."""
    return getattr(sys, 'frozen', False)


# ─── Thread de Download ──────────────────────────────────────

class DownloadThread(QThread):
    """Thread que baixa o novo .exe em background."""
    progress = pyqtSignal(int)        # porcentagem 0-100
    finished = pyqtSignal(str)        # caminho do arquivo baixado
    error = pyqtSignal(str)           # mensagem de erro

    def __init__(self, download_url: str, dest_path: str):
        super().__init__()
        self.download_url = download_url
        self.dest_path = dest_path

    def run(self):
        try:
            req = Request(self.download_url)
            req.add_header("User-Agent", "AUTOMATIZADO-Updater")

            with urlopen(req, timeout=60) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 65536  # 64KB

                with open(self.dest_path, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            pct = int((downloaded / total_size) * 100)
                            self.progress.emit(pct)

            self.finished.emit(self.dest_path)
        except Exception as e:
            self.error.emit(str(e))


# ─── Thread de Verificação ────────────────────────────────────

class CheckUpdateThread(QThread):
    """Thread que verifica se há atualização disponível."""
    update_available = pyqtSignal(str, str, str)  # version, notes, download_url
    no_update = pyqtSignal()
    error = pyqtSignal(str)

    def run(self):
        try:
            req = Request(GITHUB_API_URL)
            req.add_header("User-Agent", "AUTOMATIZADO-Updater")
            req.add_header("Accept", "application/vnd.github.v3+json")

            with urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))

            remote_version = data.get("tag_name", "")
            release_notes = data.get("body", "Sem notas de atualização.")

            # Procurar asset .exe no release
            download_url = ""
            for asset in data.get("assets", []):
                if asset["name"].lower().endswith(".exe"):
                    download_url = asset["browser_download_url"]
                    break

            if not download_url:
                self.error.emit("Nenhum .exe encontrado no release mais recente.")
                return

            local = _parse_version(CURRENT_VERSION)
            remote = _parse_version(remote_version)

            if remote > local:
                self.update_available.emit(remote_version, release_notes, download_url)
            else:
                self.no_update.emit()

        except URLError:
            self.error.emit("Sem conexão com a internet.")
        except Exception as e:
            self.error.emit(str(e))


# ─── Diálogo de Atualização ──────────────────────────────────

class UpdateDialog(QDialog):
    """Diálogo premium de download de atualização."""

    def __init__(self, version: str, notes: str, download_url: str, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.version = version
        self.download_thread = None
        self._setup_ui(version, notes)

    def _setup_ui(self, version: str, notes: str):
        self.setWindowTitle("Atualização Disponível")
        self.setFixedSize(480, 320)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['bg']};
            }}
            QLabel {{
                color: {COLORS['text']};
                background: transparent;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)

        # Ícone + Título
        title = QLabel(f"🚀  Nova versão disponível!")
        title.setStyleSheet(f"""
            font-size: 18px; font-weight: 800;
            color: {COLORS['accent']}; letter-spacing: 1px;
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Versão
        ver_label = QLabel(f"v{CURRENT_VERSION}  →  {version}")
        ver_label.setAlignment(Qt.AlignCenter)
        ver_label.setStyleSheet(f"""
            font-size: 14px; color: {COLORS['text_muted']};
            padding: 4px 0;
        """)
        layout.addWidget(ver_label)

        # Notas
        notes_label = QLabel(notes[:300] + ("..." if len(notes) > 300 else ""))
        notes_label.setWordWrap(True)
        notes_label.setStyleSheet(f"""
            font-size: 12px; color: {COLORS['text_muted']};
            background-color: {COLORS['card']};
            border: 1px solid {COLORS['card_border']};
            border-radius: 8px; padding: 12px;
        """)
        layout.addWidget(notes_label)

        # Barra de progresso (oculta inicialmente)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS['card']};
                border: 1px solid {COLORS['card_border']};
                border-radius: 6px;
                text-align: center;
                color: {COLORS['text']};
                font-size: 10px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['accent']}, stop:1 {COLORS['accent_hover']});
                border-radius: 5px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # Botões
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.skip_btn = QPushButton("  Pular  ")
        self.skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                border: 1.5px solid {COLORS['card_border']};
                font-weight: 600; font-size: 13px;
                padding: 10px 22px; border-radius: 8px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['text_muted']};
                color: {COLORS['text']};
            }}
        """)
        self.skip_btn.setCursor(Qt.PointingHandCursor)
        self.skip_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.skip_btn)

        self.update_btn = QPushButton("  ⬇  Atualizar  ")
        self.update_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['accent']}, stop:1 #8a2e3b);
                color: #ffffff; font-weight: 700; font-size: 13px;
                padding: 10px 28px; border-radius: 8px; border: none;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['accent_hover']}, stop:1 {COLORS['accent']});
            }}
            QPushButton:disabled {{
                background: {COLORS['card_border']};
                color: {COLORS['text_muted']};
            }}
        """)
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.clicked.connect(self._start_download)
        btn_layout.addWidget(self.update_btn)

        layout.addLayout(btn_layout)

    def _start_download(self):
        """Inicia o download do novo executável."""
        self.update_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Baixando atualização...")

        # Caminho temporário para o download
        exe_dir = os.path.dirname(sys.executable) if is_frozen() else os.path.dirname(os.path.abspath(__file__))
        self.temp_path = os.path.join(exe_dir, "AUTOMATIZADO_update.exe")

        self.download_thread = DownloadThread(self.download_url, self.temp_path)
        self.download_thread.progress.connect(self._on_progress)
        self.download_thread.finished.connect(self._on_download_finished)
        self.download_thread.error.connect(self._on_download_error)
        self.download_thread.start()

    def _on_progress(self, pct: int):
        self.progress_bar.setValue(pct)
        self.status_label.setText(f"Baixando... {pct}%")

    def _on_download_finished(self, path: str):
        self.status_label.setText("✅  Download concluído! Reiniciando...")
        self.progress_bar.setValue(100)
        QTimer.singleShot(1000, lambda: self._apply_update(path))

    def _on_download_error(self, msg: str):
        self.status_label.setText(f"❌  Erro: {msg}")
        self.status_label.setStyleSheet(f"font-size: 12px; color: {COLORS['danger']};")
        self.update_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)

    def _apply_update(self, new_exe_path: str):
        """Aplica a atualização substituindo o .exe atual."""
        if not is_frozen():
            # Modo dev: apenas avisa
            QMessageBox.information(
                self, "Dev Mode",
                f"Em modo dev, o update foi baixado em:\n{new_exe_path}\n\n"
                "A substituição automática só funciona no .exe empacotado."
            )
            self.accept()
            return

        current_exe = sys.executable
        backup_exe = current_exe + ".bak"

        # Script batch que:
        # 1. Espera o processo atual fechar
        # 2. Remove o backup antigo
        # 3. Renomeia o .exe atual para .bak
        # 4. Renomeia o novo para o nome original
        # 5. Inicia o novo .exe
        # 6. Remove o .bak
        bat_path = os.path.join(os.path.dirname(current_exe), "_update.bat")
        bat_content = f"""@echo off
title Atualizando AUTOMATIZADO...
echo Aguardando o programa fechar...
timeout /t 2 /nobreak >nul

:wait_loop
tasklist /FI "PID eq %1" 2>nul | find /i "AUTOMATIZADO" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)

echo Aplicando atualizacao...
if exist "{backup_exe}" del /f "{backup_exe}"
move /y "{current_exe}" "{backup_exe}"
move /y "{new_exe_path}" "{current_exe}"

echo Iniciando nova versao...
start "" "{current_exe}"

timeout /t 3 /nobreak >nul
if exist "{backup_exe}" del /f "{backup_exe}"
del /f "%~f0"
"""
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)

        # Executa o batch passando o PID atual
        pid = os.getpid()
        subprocess.Popen(
            ["cmd.exe", "/c", bat_path, str(pid)],
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        # Fecha o app
        from PyQt5.QtWidgets import QApplication
        QApplication.quit()


# ─── Função Pública ───────────────────────────────────────────

def check_for_updates(parent=None, silent: bool = True):
    """
    Verifica se há atualizações disponíveis no GitHub.

    Args:
        parent: Widget pai para os diálogos.
        silent: Se True, não mostra nada se já estiver atualizado.
                Se False, mostra mensagem "já está atualizado".
    """
    checker = CheckUpdateThread()

    def on_update(version, notes, url):
        dialog = UpdateDialog(version, notes, url, parent)
        dialog.exec_()

    def on_no_update():
        if not silent:
            msg = QMessageBox(parent)
            msg.setWindowTitle("Atualização")
            msg.setText("✅  Você já está na versão mais recente!")
            msg.setStyleSheet(f"""
                QMessageBox {{ background-color: {COLORS['card']}; }}
                QMessageBox QLabel {{ color: {COLORS['text']}; font-size: 14px; padding: 12px; }}
                QPushButton {{
                    background: {COLORS['accent']}; color: white;
                    font-weight: 700; padding: 8px 28px;
                    border-radius: 6px; font-size: 13px; border: none;
                }}
            """)
            msg.exec_()

    def on_error(msg):
        if not silent:
            err = QMessageBox(parent)
            err.setWindowTitle("Erro de Atualização")
            err.setIcon(QMessageBox.Warning)
            err.setText(f"Não foi possível verificar atualizações:\n{msg}")
            err.setStyleSheet(f"""
                QMessageBox {{ background-color: {COLORS['card']}; }}
                QMessageBox QLabel {{ color: {COLORS['text']}; font-size: 13px; padding: 10px; }}
                QPushButton {{
                    background: {COLORS['danger']}; color: white;
                    font-weight: 700; padding: 8px 28px;
                    border-radius: 6px; font-size: 13px; border: none;
                }}
            """)
            err.exec_()

    checker.update_available.connect(on_update)
    checker.no_update.connect(on_no_update)
    checker.error.connect(on_error)

    # Manter referência para não ser coletado pelo GC
    if parent:
        parent._update_checker = checker
    checker.start()
