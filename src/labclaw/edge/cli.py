"""LabClaw Edge CLI — edge node entry point."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--dashboard":
        app_path = Path(__file__).parent.parent / "dashboard" / "app.py"
        subprocess.run(["streamlit", "run", str(app_path)])
    else:
        print("labclaw-edge: Not yet implemented. Use --dashboard to launch the UI.")


if __name__ == "__main__":
    main()
