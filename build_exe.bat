@echo off
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name ChestnyZnakAPI3 chestny_znak_api3.py
pause
