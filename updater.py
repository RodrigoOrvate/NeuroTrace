"""
updater.py — Módulo de Auto-Atualização via GitHub Releases

Verifica se há uma versão mais recente do NeuroTrace publicada
no GitHub Releases e, em caso positivo, baixa o novo instalador,
substitui o atual e reinicia o programa.

Suporta Windows (.exe / Setup .exe) e macOS (.dmg / .app.zip).

Também exibe "O que há de novo" na primeira abertura após uma atualização.
"""

import json
import os
import sys
import platform
import tempfile
import subprocess
import shutil
from urllib.request import urlopen, Request
from urllib.error import URLError
from qt_compat import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QMessageBox, QSizePolicy,
    Qt, QThread, pyqtSignal, QTimer,
    QColor, QApplication,
)

# ─── Configuração ─────────────────────────────────────────────
GITHUB_OWNER = "RodrigoOrvate"
GITHUB_REPO  = "NeuroTrace"
GITHUB_API_URL  = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
GITHUB_REPO_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
CURRENT_VERSION = "2.0.1"

IS_WINDOWS = sys.platform == "win32"
IS_MACOS   = sys.platform == "darwin"

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

# ─── Utilitários ──────────────────────────────────────────────

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


def _get_version_file_path() -> str:
    """Retorna o caminho do arquivo que guarda a última versão vista.
    Usa o diretório de dados do usuário para garantir permissão de escrita."""
    if IS_WINDOWS:
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "NeuroTrace")
    elif IS_MACOS:
        base = os.path.expanduser("~/Library/Application Support/NeuroTrace")
    else:
        base = os.path.expanduser("~/.config/NeuroTrace")

    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "last_seen_version.txt")


def _read_last_seen_version() -> str:
    """Lê a última versão que o usuário já viu o 'O que há de novo'."""
    path = _get_version_file_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _write_last_seen_version(version: str):
    """Salva a versão atual como 'já vista'."""
    path = _get_version_file_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(version.strip())
    except Exception:
        pass


def check_internet() -> bool:
    """Verifica rapidamente se há conexão com a internet."""
    try:
        req = Request("https://api.github.com")
        req.add_header("User-Agent", "NeuroTrace-Updater")
        with urlopen(req, timeout=5):
            return True
    except Exception:
        return False


# ─── Thread de Download ──────────────────────────────────────

class DownloadThread(QThread):
    """Thread que baixa o novo instalador em background."""
    progress = pyqtSignal(int)   # porcentagem 0-100
    finished = pyqtSignal(str)   # caminho do arquivo baixado
    error    = pyqtSignal(str)   # mensagem de erro

    def __init__(self, download_url: str, dest_path: str):
        super().__init__()
        self.download_url = download_url
        self.dest_path    = dest_path

    def run(self):
        try:
            req = Request(self.download_url)
            req.add_header("User-Agent", "NeuroTrace-Updater")
            with urlopen(req, timeout=60) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded  = 0
                chunk_size  = 65536  # 64KB
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

                if total_size > 0 and downloaded < total_size:
                    raise Exception(f"Download incompleto: a conexão pode ter caído ({downloaded}/{total_size} bytes).")

            self.finished.emit(self.dest_path)
        except Exception as e:
            self.error.emit(str(e))


# ─── Thread de Verificação ────────────────────────────────────

class CheckUpdateThread(QThread):
    """Thread que verifica se há atualização disponível."""
    update_available = pyqtSignal(str, str, str)  # version, notes, download_data
    no_update        = pyqtSignal()
    error            = pyqtSignal(str)

    def run(self):
        try:
            req = Request(GITHUB_API_URL)
            req.add_header("User-Agent",  "NeuroTrace-Updater")
            req.add_header("Accept", "application/vnd.github.v3+json")
            with urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))

            remote_version = data.get("tag_name", "")
            release_notes  = data.get("body", "Sem notas de atualização.")
            download_url, asset_type = self._find_asset(data.get("assets", []))

            if not download_url and asset_type != "win_choice":
                plat = "macOS" if IS_MACOS else "Windows"
                self.error.emit(f"Nenhum arquivo para {plat} encontrado no release.")
                return

            local  = _parse_version(CURRENT_VERSION)
            remote = _parse_version(remote_version)

            if remote > local:
                asset_url, asset_type = self._find_asset(data.get("assets", []))
                if not asset_url:
                    plat = "macOS" if IS_MACOS else "Windows"
                    self.error.emit(f"Nenhum arquivo para {plat} encontrado no release.")
                    return
                self.update_available.emit(
                    remote_version, release_notes,
                    f"{asset_url}||{asset_type}"
                )
            else:
                self.no_update.emit()

        except URLError:
            self.error.emit("Sem conexão com a internet.")
        except Exception as e:
            self.error.emit(str(e))

    def _find_asset(self, assets: list) -> tuple:
        win_installer  = ""
        win_standalone = ""
        mac_dmg        = ""
        mac_zip        = ""

        for asset in assets:
            name = asset["name"].lower()
            url  = asset["browser_download_url"]
            if name.endswith(".dmg"):
                mac_dmg = url
            elif name.endswith(".zip") and ("macos" in name or "mac" in name):
                mac_zip = url
            elif name.endswith(".exe"):
                if "setup" in name:
                    win_installer = url
                else:
                    win_standalone = url

        if IS_MACOS:
            if mac_dmg: return mac_dmg, "mac_dmg"
            if mac_zip: return mac_zip, "mac_zip"
            return "", ""
        else:
            # Separa com marcador inequívoco para não confundir com URLs
            if win_installer and win_standalone:
                combined = f"{win_installer}|||{win_standalone}"
                return combined, "win_choice"
            if win_installer:  return win_installer,  "win_installer"
            if win_standalone: return win_standalone, "win_standalone"
            return "", ""


# ─── Thread para buscar notas da versão atual ────────────────

class FetchReleaseNotesThread(QThread):
    """Busca as notas da release da versão atual instalada."""
    finished = pyqtSignal(str)   # notas da release
    error    = pyqtSignal(str)

    def run(self):
        try:
            tag = f"v{CURRENT_VERSION}"
            url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/tags/{tag}"
            req = Request(url)
            req.add_header("User-Agent", "NeuroTrace-Updater")
            req.add_header("Accept", "application/vnd.github.v3+json")
            with urlopen(req, timeout=15) as response:
                data  = json.loads(response.read().decode("utf-8"))
                notes = data.get("body", "").strip()
                self.finished.emit(notes if notes else "Sem notas de atualização para esta versão.")
        except URLError:
            self.error.emit("Sem conexão com a internet.")
        except Exception as e:
            self.error.emit(str(e))


# ─── Diálogo "O que há de novo" ──────────────────────────────

class WhatsNewDialog(QDialog):
    """Diálogo exibido na primeira abertura após uma atualização."""

    def __init__(self, notes: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("O que há de novo")
        # Remove o botão ? do canto da janela
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setFixedSize(520, 400)
        self.setStyleSheet(f"QDialog {{ background-color: {COLORS['bg']}; }}")
        self._setup_ui(notes)

    def _setup_ui(self, notes: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)

        # Título
        title = QLabel(f"✨ Novidades da v{CURRENT_VERSION}")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            font-size: 18px; font-weight: 800;
            color: {COLORS['accent']}; letter-spacing: 1px;
        """)
        layout.addWidget(title)

        # Linha separadora
        from qt_compat import QFrame
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {COLORS['card_border']}; max-height: 1px;")
        layout.addWidget(sep)

        # Notas em scroll
        from qt_compat import QScrollArea, QWidget as _QWidget
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {COLORS['card_border']};
                border-radius: 8px;
                background: {COLORS['card']};
            }}
            QScrollBar:vertical {{
                background: {COLORS['card']};
                width: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['card_border']};
                min-height: 20px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {COLORS['accent']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        notes_widget = _QWidget()
        notes_widget.setStyleSheet(f"background: {COLORS['card']};")
        notes_layout = QVBoxLayout(notes_widget)
        notes_layout.setContentsMargins(14, 12, 14, 12)

        notes_label = QLabel(notes)
        notes_label.setWordWrap(True)
        notes_label.setStyleSheet(f"""
            font-size: 13px; color: {COLORS['text']};
            line-height: 1.6;
        """)
        notes_label.setTextFormat(Qt.MarkdownText)
        notes_label.setOpenExternalLinks(True)
        notes_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        notes_layout.addWidget(notes_label)
        scroll.setWidget(notes_widget)
        layout.addWidget(scroll, stretch=1)

        # Botões
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        # Botão GitHub com ícone Unicode
        github_btn = QPushButton("   Ver no GitHub")
        github_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                border: 1.5px solid {COLORS['card_border']};
                font-weight: 600; font-size: 13px;
                padding: 10px 18px; border-radius: 8px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['text_muted']};
                color: {COLORS['text']};
            }}
        """)
        github_btn.setCursor(Qt.PointingHandCursor)
        github_btn.clicked.connect(self._open_github)
        btn_row.addWidget(github_btn)

        btn_row.addStretch()

        ok_btn = QPushButton("  Entendido! ")
        ok_btn.setStyleSheet(f"""
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
        """)
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

    def _open_github(self):
        _open_url(GITHUB_REPO_URL)


# ─── Diálogo de Atualização ──────────────────────────────────

class UpdateDialog(QDialog):
    """Diálogo premium de download de atualização."""

    def __init__(self, version: str, notes: str, download_data: str, parent=None):
        super().__init__(parent)
        # Formato: "<url_ou_urls>||<asset_type>"
        sep_idx = download_data.rfind("||")
        if sep_idx >= 0:
            url_part       = download_data[:sep_idx]
            self.asset_type = download_data[sep_idx+2:]
        else:
            url_part       = download_data
            self.asset_type = ""

        if self.asset_type == "win_choice":
            # url_part = "<setup_url>|||<portable_url>"
            parts = url_part.split("|||")
            self.download_url_setup = parts[0] if len(parts) > 0 else ""
            self.download_url_port  = parts[1] if len(parts) > 1 else ""
            self.download_url = ""
        else:
            self.download_url       = url_part
            self.download_url_setup = ""
            self.download_url_port  = ""
        self.version         = version
        self.download_thread = None
        self._setup_ui(version, notes)

    def _setup_ui(self, version: str, notes: str):
        self.setWindowTitle("Atualização Disponível")
        # Remove o botão ? do canto da janela
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumSize(500, 420)
        self.resize(500, 460)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {COLORS['bg']}; }}
            QLabel  {{ color: {COLORS['text']}; background: transparent; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)

        title = QLabel("🚀 Nova versão disponível!")
        title.setStyleSheet(f"""
            font-size: 18px; font-weight: 800;
            color: {COLORS['accent']}; letter-spacing: 1px;
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        ver_label = QLabel(f"v{CURRENT_VERSION} → {version}")
        ver_label.setAlignment(Qt.AlignCenter)
        ver_label.setStyleSheet(f"font-size: 14px; color: {COLORS['text_muted']}; padding: 4px 0;")
        layout.addWidget(ver_label)

        # Notas com Scroll
        from qt_compat import QScrollArea, QWidget as _QWidget
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {COLORS['card_border']};
                border-radius: 8px; background: {COLORS['card']};
            }}
            QScrollBar:vertical {{
                background: {COLORS['card']}; width: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['card_border']}; min-height: 20px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {COLORS['accent']}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        
        notes_widget = _QWidget()
        notes_widget.setStyleSheet(f"background: transparent;")
        notes_layout = QVBoxLayout(notes_widget)
        notes_layout.setContentsMargins(12, 12, 12, 12)

        notes_label = QLabel(notes)
        notes_label.setWordWrap(True)
        notes_label.setStyleSheet(f"font-size: 13px; color: {COLORS['text']}; line-height: 1.6;")
        notes_label.setTextFormat(Qt.MarkdownText)
        notes_label.setOpenExternalLinks(True)
        notes_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        
        notes_layout.addWidget(notes_label)
        scroll.setWidget(notes_widget)
        layout.addWidget(scroll, stretch=1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS['card']};
                border: 1px solid {COLORS['card_border']};
                border-radius: 6px; text-align: center;
                color: {COLORS['text']}; font-size: 10px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['accent']}, stop:1 {COLORS['accent_hover']});
                border-radius: 5px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        layout.addWidget(self.status_label)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.skip_btn = QPushButton("Pular")
        self.skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {COLORS['text_muted']};
                border: 1.5px solid {COLORS['card_border']};
                font-weight: 600; font-size: 13px;
                padding: 10px 0; border-radius: 8px;
                min-width: 100px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['text_muted']}; color: {COLORS['text']};
            }}
        """)
        self.skip_btn.setCursor(Qt.PointingHandCursor)
        self.skip_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.skip_btn)

        self.update_btn = QPushButton("⬇  Atualizar")
        self.update_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['accent']}, stop:1 #8a2e3b);
                color: #ffffff; font-weight: 700; font-size: 13px;
                padding: 10px 0; border-radius: 8px; border: none;
                min-width: 140px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['accent_hover']}, stop:1 {COLORS['accent']});
            }}
            QPushButton:disabled {{
                background: {COLORS['card_border']}; color: {COLORS['text_muted']};
            }}
        """)
        self.update_btn.setCursor(Qt.PointingHandCursor)

        if self.asset_type == "win_choice":
            self.update_btn.setText("⬇  Setup (Completo)")
            self.update_btn.clicked.connect(lambda: self._start_download_choice("win_installer"))

            self.port_btn = QPushButton("⬇  Portátil (.exe)")
            self.port_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['card']}; color: {COLORS['text']};
                    border: 1.5px solid {COLORS['accent']};
                    font-weight: 600; font-size: 13px;
                    padding: 10px 0; border-radius: 8px;
                    min-width: 130px;
                }}
                QPushButton:hover {{
                    background: {COLORS['accent']}; color: #ffffff;
                }}
                QPushButton:disabled {{
                    background: {COLORS['card_border']}; color: {COLORS['text_muted']}; border: none;
                }}
            """)
            self.port_btn.setCursor(Qt.PointingHandCursor)
            self.port_btn.clicked.connect(lambda: self._start_download_choice("win_standalone"))
            btn_layout.addWidget(self.port_btn)
        else:
            self.update_btn.clicked.connect(self._start_download)

        btn_layout.addWidget(self.update_btn)
        layout.addLayout(btn_layout)

    def _start_download_choice(self, chosen_type):
        if chosen_type == "win_installer":
            self.download_url = self.download_url_setup
        else:
            self.download_url = self.download_url_port
        self.asset_type = chosen_type
        if hasattr(self, 'port_btn'):
            self.port_btn.setEnabled(False)
        self._start_download()

    def _start_download(self):
        self.update_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Baixando atualização...")

        if self.asset_type == "win_installer":
            self.temp_path = os.path.join(
                tempfile.gettempdir(),
                f"NeuroTrace_Setup_v{self.version}.exe"
            )
        elif self.asset_type == "mac_dmg":
            self.temp_path = os.path.join(
                tempfile.gettempdir(),
                f"NeuroTrace_macOS_v{self.version}.dmg"
            )
        elif self.asset_type == "mac_zip":
            self.temp_path = os.path.join(
                tempfile.gettempdir(),
                f"NeuroTrace_macOS_v{self.version}.zip"
            )
        else:
            self.temp_path = os.path.join(
                tempfile.gettempdir(),
                f"NeuroTrace_Update_v{self.version}.exe"
            )

        self.download_thread = DownloadThread(self.download_url, self.temp_path)
        self.download_thread.progress.connect(self._on_progress)
        self.download_thread.finished.connect(self._on_download_finished)
        self.download_thread.error.connect(self._on_download_error)
        self.download_thread.start()

    def _on_progress(self, pct: int):
        self.progress_bar.setValue(pct)
        self.status_label.setText(f"Baixando... {pct}%")

    def _on_download_finished(self, path: str):
        self.status_label.setText("✅ Download concluído! Reiniciando...")
        self.progress_bar.setValue(100)
        QTimer.singleShot(1000, lambda: self._apply_update(path))

    def _on_download_error(self, msg: str):
        self.status_label.setText(f"❌ Erro: {msg}")
        self.status_label.setStyleSheet(f"font-size: 12px; color: {COLORS['danger']};")
        self.update_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)

    def _apply_update(self, new_path: str):
        if not is_frozen():
            QMessageBox.information(
                self, "Dev Mode",
                f"Em modo dev, o update foi baixado em:\n{new_path}\n\n"
                "A substituição automática só funciona no app empacotado."
            )
            self.accept()
            return

        if self.asset_type == "win_installer":
            self._apply_win_installer(new_path)
        elif self.asset_type == "win_standalone":
            self._apply_win_standalone(new_path)
        elif self.asset_type == "mac_dmg":
            self._apply_mac_dmg(new_path)
        elif self.asset_type == "mac_zip":
            self._apply_mac_zip(new_path)
        else:
            QMessageBox.warning(self, "Erro", "Tipo de atualização desconhecido.")
            self.accept()

    # ─── Windows: Instalador Inno Setup ──────────────────────
    def _apply_win_installer(self, installer_path: str):
        try:
            subprocess.Popen(
                [installer_path, "/SILENT", "/CLOSEAPPLICATIONS"],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception:
            subprocess.Popen([installer_path])
        QApplication.quit()

    # ─── Windows: Standalone .exe ────────────────────────────
    def _apply_win_standalone(self, new_exe_path: str):
        current_exe = sys.executable
        bat_path    = os.path.join(tempfile.gettempdir(), "_nt_update.bat")

        bat_content = f"""@echo off
title Atualizando NeuroTrace...
:retry_move
move /y "{new_exe_path}" "{current_exe}" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto retry_move
)
start "" "{current_exe}"
del /f "%~f0"
"""
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)

        subprocess.Popen(
            ["cmd.exe", "/c", bat_path],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        QApplication.quit()

    # ─── macOS: .dmg ─────────────────────────────────────────
    def _apply_mac_dmg(self, dmg_path: str):
        app_name    = "NeuroTrace.app"
        dest        = f"/Applications/{app_name}"
        script_path = os.path.join(tempfile.gettempdir(), "_update_mac.sh")

        script_content = f"""#!/bin/bash
sleep 2
while pgrep -x "NeuroTrace" > /dev/null 2>&1; do sleep 1; done
MOUNT_POINT=$(hdiutil attach "{dmg_path}" -nobrowse -noverify | grep "/Volumes/" | awk '{{print $NF}}')
if [ -z "$MOUNT_POINT" ]; then echo "Erro ao montar o .dmg"; exit 1; fi
if [ -d "{dest}" ]; then rm -rf "{dest}"; fi
cp -R "$MOUNT_POINT/{app_name}" "/Applications/"
hdiutil detach "$MOUNT_POINT" -quiet
rm -f "{dmg_path}"
sleep 1
open "/Applications/{app_name}"
rm -f "$0"
"""
        with open(script_path, "w") as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
        subprocess.Popen(["bash", script_path])
        QApplication.quit()

    # ─── macOS: .zip contendo .app ───────────────────────────
    def _apply_mac_zip(self, zip_path: str):
        app_name    = "NeuroTrace.app"
        dest        = f"/Applications/{app_name}"
        extract_dir = os.path.join(tempfile.gettempdir(), "neurotrace_update")
        script_path = os.path.join(tempfile.gettempdir(), "_update_mac.sh")

        script_content = f"""#!/bin/bash
sleep 2
while pgrep -x "NeuroTrace" > /dev/null 2>&1; do sleep 1; done
rm -rf "{extract_dir}"
mkdir -p "{extract_dir}"
unzip -o "{zip_path}" -d "{extract_dir}"
APP_PATH=$(find "{extract_dir}" -maxdepth 2 -name "*.app" -type d | head -1)
if [ -z "$APP_PATH" ]; then echo "Erro: .app não encontrado no .zip"; exit 1; fi
if [ -d "{dest}" ]; then rm -rf "{dest}"; fi
cp -R "$APP_PATH" "/Applications/"
rm -rf "{extract_dir}"
rm -f "{zip_path}"
sleep 1
open "/Applications/{app_name}"
rm -f "$0"
"""
        with open(script_path, "w") as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
        subprocess.Popen(["bash", script_path])
        QApplication.quit()


# ─── Helpers ─────────────────────────────────────────────────

def _open_url(url: str):
    """Abre uma URL no navegador padrão do sistema."""
    try:
        if sys.platform == "win32":
            os.startfile(url)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", url])
        else:
            subprocess.Popen(["xdg-open", url])
    except Exception:
        pass


# ─── Funções Públicas ─────────────────────────────────────────

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
            msg.setText("✅ Você já está na versão mais recente!")
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

    if parent:
        parent._update_checker = checker

    checker.start()


def check_whats_new(parent=None):
    """
    Verifica se o programa foi atualizado desde a última vez que o usuário
    viu o 'O que há de novo'. Se sim, busca as notas da release atual e exibe
    o diálogo. Completamente tolerante a falta de internet — se não houver
    conexão, não mostra nada e não bloqueia o programa.
    """
    last_seen = _read_last_seen_version()

    # Se já viu esta versão, não faz nada
    if _parse_version(last_seen) >= _parse_version(CURRENT_VERSION):
        return

    # Marca como vista imediatamente para não tentar de novo em caso de erro
    _write_last_seen_version(CURRENT_VERSION)

    fetcher = FetchReleaseNotesThread()

    def on_notes(notes: str):
        dialog = WhatsNewDialog(notes, parent)
        dialog.exec_()

    def on_error(msg: str):
        # Sem internet ou erro: não mostra nada, falha silenciosamente
        pass

    fetcher.finished.connect(on_notes)
    fetcher.error.connect(on_error)

    if parent:
        parent._whats_new_fetcher = fetcher

    fetcher.start()
