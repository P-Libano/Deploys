"""Streamlit Cloud entry point for the macroeconomic calculator.

Keeps the cloud main module at repo root so dependency discovery does not have
to parse a folder name with spaces or accents.
"""
from pathlib import Path
import runpy
import sys


APP_DIR = Path(__file__).parent / "Calculadora Macroeconômica"
sys.path.insert(0, str(APP_DIR))

runpy.run_path(str(APP_DIR / "app.py"), run_name="__main__")
