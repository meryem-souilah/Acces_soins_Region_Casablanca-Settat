@echo off
REM Rejoue toute la phase 2 (Séance 4 : nettoyage --dry-run, nettoyage complet, import PostGIS, requêtes EXPLAIN ANALYZE et dump)
cd /d "%~dp0"
set PYTHON_EXE=C:\Users\HP\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYTHON_EXE%" set PYTHON_EXE=python

echo === 1. Mode rapport seul (--dry-run) ===
"%PYTHON_EXE%" scripts\nettoyage.py --dry-run
if errorlevel 1 exit /b 1

echo.
echo === 2. Nettoyage complet et export GeoPackage (EPSG:26191) ===
"%PYTHON_EXE%" scripts\nettoyage.py
if errorlevel 1 exit /b 1

echo.
echo === 3. Creation du schema PostGIS, import ogr2ogr, requetes EXPLAIN ANALYZE et sauvegarde pg_dump ===
"%PYTHON_EXE%" scripts\import_postgis.py
if errorlevel 1 exit /b 1

echo.
echo === Phase 2 (Seance 4) terminee avec succes ! ===
