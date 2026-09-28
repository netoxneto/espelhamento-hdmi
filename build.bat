@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pyinstaller.exe" (
  echo PyInstaller nao encontrado. Execute install.bat primeiro.
  pause
  exit /b 1
)
".venv\Scripts\pyinstaller.exe" --noconfirm --clean --name EspelhamentoHDMI --console --collect-all windows_capture --collect-all PySide6 app\main.py
if errorlevel 1 (
  echo Falha ao gerar executavel. Consulte os erros acima.
  pause
  exit /b 1
)
echo Executavel gerado em dist\EspelhamentoHDMI.exe (confira o nome na pasta dist).
pause
