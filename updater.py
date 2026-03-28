"""
updater.py — Módulo de Auto-Atualização via GitHub Releases

Verifica se há uma versão mais recente do NeuroTrace publicada
no GitHub Releases e, em caso positivo, baixa o novo instalador,
substitui o atual e reinicia o programa.

Suporta Windows (.exe / Setup .exe) e macOS (.dmg / .app.zip).
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
GITHUB_REPO = "NeuroTrace"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
CURRENT_VERSION = "2.0.0"

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"

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


def _get_platform_suffix() -> str:
    """Retorna sufixo esperado nos assets para a plataforma atual."""
    if IS_MACOS:
        return "macos"
    return "windows"


# ─── Thread de Download ──────────────────────────────────────

class DownloadThread(QThread):
    """Thread que baixa o novo instalador em background."""
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
            req.add_header("User-Agent", "NeuroTrace-Updater")

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
    update_available = pyqtSignal(str, str, str)  # version, notes, download_data
    no_update = pyqtSignal()
    error = pyqtSignal(str)

    def run(self):
        try:
            req = Request(GITHUB_API_URL)
            req.add_header("User-Agent", "NeuroTrace-Updater")
            req.add_header("Accept", "application/vnd.github.v3+json")

            with urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))

            remote_version = data.get("tag_name", "")
            release_notes = data.get("body", "Sem notas de atualização.")

            download_url, asset_type = self._find_asset(data.get("assets", []))

            if not download_url:
                plat = "macOS" if IS_MACOS else "Windows"
                self.error.emit(f"Nenhum arquivo para {plat} encontrado no release.")
                return

            local = _parse_version(CURRENT_VERSION)
            remote = _parse_version(remote_version)

            if remote > local:
                # Codifica url|tipo no sinal
                self.update_available.emit(
                    remote_version, release_notes,
                    f"{download_url}|{asset_type}"
                )
            else:
                self.no_update.emit()

        except URLError:
            self.error.emit("Sem conexão com a internet.")
        except Exception as e:
            self.error.emit(str(e))

    def _find_asset(self, assets: list) -> tuple:
        """
        Encontra o asset correto para a plataforma.

        Retorna (url, tipo) onde tipo é:
          - 'win_installer'  → Setup .exe do Windows
          - 'win_standalone' → .exe standalone do Windows
          - 'mac_dmg'        → .dmg do macOS
          - 'mac_zip'        → .app.zip do macOS
          - ''               → não encontrado
        """
        # Classificar todos os assets
        win_installer = ""
        win_standalone = ""
        mac_dmg = ""
        mac_zip = ""

        for asset in assets:
            name = asset["name"].lower()
            url = asset["browser_download_url"]

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
            if mac_dmg:
                return mac_dmg, "mac_dmg"
            if mac_zip:
                return mac_zip, "mac_zip"
            return "", ""
        else:
            # Windows: prioriza instalador
            if win_installer:
                return win_installer, "win_installer"
            if win_standalone:
                return win_standalone, "win_standalone"
            return "", ""


# ─── Diálogo de Atualização ──────────────────────────────────

class UpdateDialog(QDialog):
    """Diálogo premium de download de atualização."""

    def __init__(self, version: str, notes: str, download_data: str, parent=None):
        super().__init__(parent)
        # download_data vem como "url|tipo"
        parts = download_data.rsplit("|", 1)
        self.download_url = parts[0]
        self.asset_type = parts[1] if len(parts) > 1 else ""
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
        """Inicia o download do novo instalador/app."""
        self.update_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Baixando atualização...")

        # Definir caminho de destino baseado no tipo de asset
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
            # win_standalone fallback
            exe_dir = os.path.dirname(sys.executable) if is_frozen() else os.path.dirname(os.path.abspath(__file__))
            self.temp_path = os.path.join(exe_dir, "NeuroTrace_update.exe")

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

    def _apply_update(self, new_path: str):
        """Aplica a atualização de acordo com a plataforma e tipo de asset."""
        if not is_frozen():
            # Modo dev: apenas avisa
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
        """Executa o instalador baixado e fecha o app."""
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
        """Aplica atualização substituindo o .exe atual (modo legacy)."""
        current_exe = sys.executable
        backup_exe = current_exe + ".bak"

        bat_path = os.path.join(os.path.dirname(current_exe), "_update.bat")
        bat_content = f"""@echo off
title Atualizando NeuroTrace...
echo Aguardando o programa fechar...
timeout /t 2 /nobreak >nul

:wait_loop
tasklist /FI "PID eq %1" 2>nul | find /i "NeuroTrace" >nul
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

        pid = os.getpid()
        subprocess.Popen(
            ["cmd.exe", "/c", bat_path, str(pid)],
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        QApplication.quit()

    # ─── macOS: .dmg ─────────────────────────────────────────

    def _apply_mac_dmg(self, dmg_path: str):
        """
        Monta o .dmg, copia o .app para /Applications
        e reinicia o programa.
        """
        app_name = "NeuroTrace.app"
        dest = f"/Applications/{app_name}"

        # Shell script que:
        # 1. Espera o app fechar
        # 2. Monta o .dmg
        # 3. Copia o .app para /Applications
        # 4. Desmonta o .dmg
        # 5. Reinicia o app
        script_path = os.path.join(tempfile.gettempdir(), "_update_mac.sh")
        script_content = f"""#!/bin/bash
# Aguardar o app fechar
sleep 2
while pgrep -x "NeuroTrace" > /dev/null 2>&1; do
    sleep 1
done

# Montar o .dmg
MOUNT_POINT=$(hdiutil attach "{dmg_path}" -nobrowse -noverify | grep "/Volumes/" | awk '{{print $NF}}')

if [ -z "$MOUNT_POINT" ]; then
    echo "Erro ao montar o .dmg"
    exit 1
fi

# Remover o .app antigo e copiar o novo
if [ -d "{dest}" ]; then
    rm -rf "{dest}"
fi
cp -R "$MOUNT_POINT/{app_name}" "/Applications/"

# Desmontar
hdiutil detach "$MOUNT_POINT" -quiet

# Limpar
rm -f "{dmg_path}"

# Reiniciar
sleep 1
open "/Applications/{app_name}"

# Auto-remover o script
rm -f "$0"
"""
        with open(script_path, "w") as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)

        subprocess.Popen(["bash", script_path])

        QApplication.quit()

    # ─── macOS: .zip contendo .app ───────────────────────────

    def _apply_mac_zip(self, zip_path: str):
        """
        Extrai o .zip, copia o .app para /Applications
        e reinicia o programa.
        """
        app_name = "NeuroTrace.app"
        dest = f"/Applications/{app_name}"
        extract_dir = os.path.join(tempfile.gettempdir(), "neurotrace_update")

        script_path = os.path.join(tempfile.gettempdir(), "_update_mac.sh")
        script_content = f"""#!/bin/bash
# Aguardar o app fechar
sleep 2
while pgrep -x "NeuroTrace" > /dev/null 2>&1; do
    sleep 1
done

# Extrair o .zip
rm -rf "{extract_dir}"
mkdir -p "{extract_dir}"
unzip -o "{zip_path}" -d "{extract_dir}"

# Encontrar o .app dentro do diretório extraído
APP_PATH=$(find "{extract_dir}" -maxdepth 2 -name "*.app" -type d | head -1)

if [ -z "$APP_PATH" ]; then
    echo "Erro: .app não encontrado no .zip"
    exit 1
fi

# Remover o .app antigo e copiar o novo
if [ -d "{dest}" ]; then
    rm -rf "{dest}"
fi
cp -R "$APP_PATH" "/Applications/"

# Limpar
rm -rf "{extract_dir}"
rm -f "{zip_path}"

# Reiniciar
sleep 1
open "/Applications/{app_name}"

# Auto-remover o script
rm -f "$0"
"""
        with open(script_path, "w") as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)

        subprocess.Popen(["bash", script_path])

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
