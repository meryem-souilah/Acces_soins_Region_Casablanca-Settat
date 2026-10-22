@echo off
REM Rejoue toute la phase 1 (collecte + controle) en une commande.
REM Fonctionne depuis Anaconda Prompt comme depuis l invite de commandes Windows.
cd /d "%~dp0"
where conda >nul 2>nul
if errorlevel 1 (
    call "%USERPROFILE%\anaconda3-pbe\Scripts\activate.bat" geodata-sante
) else (
    call conda activate geodata-sante
)
python scripts\collecte.py %*
python scripts\controle_collecte.py
