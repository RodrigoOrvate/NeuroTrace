@echo off
echo ============================================
echo   Criando executavel AUTOMATIZADO...
echo ============================================
echo.

python -m PyInstaller main.spec --clean --noconfirm

if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Falha ao criar o executavel.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Executavel criado com sucesso!
echo   Local: dist\AUTOMATIZADO.exe
echo ============================================
echo.
pause
