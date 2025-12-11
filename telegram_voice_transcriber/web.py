"""Web UI launcher."""
import subprocess
import sys
from pathlib import Path


def run():
    """Launch the Streamlit web UI."""
    app_path = Path(__file__).parent.parent / "app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])
