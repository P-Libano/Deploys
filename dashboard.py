from pathlib import Path
import runpy
import sys

APP_DIR = Path(__file__).parent / "Calculadora WACC Regulatório"
sys.path.insert(0, str(APP_DIR))

runpy.run_path(str(APP_DIR / "dashboard.py"), run_name="__main__")
