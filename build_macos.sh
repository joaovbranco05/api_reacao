#!/bin/bash
# Script para compilar o executável no macOS
# ATENÇÃO: Este script DEVE ser rodado em um computador com macOS, pois o PyInstaller 
# não permite compilar para Mac a partir do Windows.

echo "================================================="
echo "  Compilando API Reação para macOS"
echo "================================================="

# Verifica se o Python está instalado
if ! command -v python3 &> /dev/null
then
    echo "[ERRO] python3 não encontrado. Instale o Python primeiro."
    exit 1
fi

echo "[1/4] Criando ambiente virtual..."
python3 -m venv .venv_mac
source .venv_mac/bin/activate

echo "[2/4] Instalando dependências..."
pip install -r requirements.txt
pip install pyinstaller

echo "[3/4] Compilando com PyInstaller..."
# Remove builds anteriores se existirem
rm -rf build/ dist/

# Usa o mesmo app.spec (ele é multiplataforma)
pyinstaller app.spec --clean --noconfirm

echo "[4/4] Finalizando..."
deactivate

echo "================================================="
echo "  COMPILAÇÃO CONCLUÍDA!"
echo "  O seu executável para macOS está na pasta 'dist'"
echo "  Lembre-se de colocar o arquivo '.env' na mesma"
echo "  pasta do executável gerado antes de executá-lo."
echo "================================================="
