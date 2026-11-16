import os
import sys
from pathlib import Path
from streamlit.web import cli as stcli

base_dir = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
os.chdir(base_dir)
sys.argv = [
    "streamlit",
    "run",
    str(base_dir / "main.py"),
    "--global.developmentMode=false",
    "--server.headless=false",
]
sys.exit(stcli.main())
