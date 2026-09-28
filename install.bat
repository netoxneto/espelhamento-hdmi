@echo off
setlocal
cd /d "%~dp0"
echo ========================================
echo   INSTALADOR - ESPELHAMENTO HDMI
echo ========================================
where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 (
    echo ERRO: Python nao encontrado.
    echo Instale Python 3.11 ou 3.12 x64 em https://www.python.org/downloads/windows/
    echo Marque "Add python.exe to PATH" durante a instalacao.
    pause
    exit /b 1
  )
  set "PYTHON=python"
) else (
  set "PYTHON=py -3"
)
%PYTHON% -c "import sys; print('Python encontrado:', sys.version); raise SystemExit(0 if sys.version_info >= (3,11) and sys.version_info < (3,14) else 1)"
if errorlevel 1 (
  echo ERRO: requer Python 3.11, 3.12 ou 3.13 x64.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual...
  %PYTHON% -m venv .venv
  if errorlevel 1 goto :error
)
echo Atualizando pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
echo Instalando dependencias...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo ERRO: falha ao instalar uma ou mais dependencias.
  echo Confira a mensagem acima, sua conexao e a versao do Python.
  echo Algumas versoes de windows-capture podem exigir wheel compativel com Windows x64.
  goto :error
)
echo Verificando imports principais...
".venv\Scripts\python.exe" -c "import PySide6, numpy, cv2, windows_capture; print('[OK] Imports principais')"
if errorlevel 1 goto :error
echo.
echo [OK] Instalacao concluida.
echo Para iniciar, execute run.bat
pause
exit /b 0
:error
echo.
echo [ERRO] Instalacao nao concluida. Nenhum erro foi ocultado.
pause
exit /b 1
