@echo off
chcp 65001 >nul 2>&1
title API Reacao - iScholar
color 0A

echo ============================================
echo    API Reacao - Sistema de Notas iScholar
echo ============================================
echo.

:: Navega para o diretorio do script
cd /d "%~dp0"

:: -------------------------------------------------------
:: Detecta Python
:: -------------------------------------------------------
set "PYTHON_CMD="

python --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto python_ok
)

py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
    goto python_ok
)

echo [ERRO] Python nao foi encontrado!
echo Instale o Python 3.10+ em https://www.python.org/downloads/
echo Marque a opcao "Add Python to PATH" durante a instalacao.
echo.
pause
exit /b 1

:python_ok
echo [OK] Python encontrado: %PYTHON_CMD%

:: -------------------------------------------------------
:: Verifica .env
:: -------------------------------------------------------
if not exist ".env" (
    echo [ERRO] Arquivo .env nao encontrado!
    echo Crie o arquivo .env com o seguinte conteudo:
    echo   ISCHOLAR_CODIGO_ESCOLA=SUA_ESCOLA
    echo   ISCHOLAR_TOKEN_ACESSO=SEU_TOKEN
    echo   PROFESSOR_LOGINS=123:senha1,456:senha2
    echo.
    pause
    exit /b 1
)
echo [OK] Arquivo .env encontrado.

:: -------------------------------------------------------
:: Ambiente virtual
:: -------------------------------------------------------
if exist ".venv\Scripts\activate.bat" goto venv_ready

if exist ".venv" (
    echo [INFO] Removendo ambiente virtual incompleto...
    rmdir /s /q ".venv" 2>nul
    timeout /t 2 /nobreak >nul
)

echo [INFO] Criando ambiente virtual...
%PYTHON_CMD% -m venv .venv
if errorlevel 1 (
    echo [ERRO] Falha ao criar ambiente virtual.
    pause
    exit /b 1
)
echo [OK] Ambiente virtual criado.

:venv_ready
call ".venv\Scripts\activate.bat"
echo [OK] Ambiente virtual ativado.

:: -------------------------------------------------------
:: Dependencias
:: -------------------------------------------------------
echo.
echo [INFO] Instalando dependencias...
".venv\Scripts\pip.exe" install --no-cache-dir -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.

:: -------------------------------------------------------
:: Inicia o servidor
:: -------------------------------------------------------
echo.
echo ============================================
echo   Iniciando o servidor...
echo   Acesse: http://localhost:8000
echo   Para parar: Ctrl+C ou feche esta janela.
echo ============================================
echo.

start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:8000"

".venv\Scripts\python.exe" main.py

echo.
echo [INFO] Servidor encerrado.
pause
