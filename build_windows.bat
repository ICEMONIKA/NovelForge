@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
py -m pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --name NovelForge --add-data "assets;assets" main.py
pause
