"""LabClaw CLI — main entry point."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""

    if cmd == "serve":
        from labclaw.daemon import main as daemon_main
        sys.argv = sys.argv[1:]  # shift so argparse sees daemon args
        daemon_main()
    elif cmd == "--dashboard":
        app_path = Path(__file__).parent / "dashboard" / "app.py"
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])
    elif cmd == "--api":
        import uvicorn

        from labclaw.api.app import app
        if len(sys.argv) > 2:
            try:
                port = int(sys.argv[2])
            except ValueError:
                print(f"Error: invalid port number '{sys.argv[2]}'", file=sys.stderr)
                sys.exit(1)
        else:
            port = 18800
        uvicorn.run(app, host="127.0.0.1", port=port)
    else:
        print("Usage: labclaw <command>")
        print()
        print("Commands:")
        print("  serve          Start the full 24/7 LabClaw daemon")
        print("  --dashboard    Launch Streamlit dashboard only")
        print("  --api [PORT]   Launch FastAPI server only")
        print()
        print("Serve options (pass after 'serve'):")
        print("  --data-dir PATH        Directory to watch (default: /opt/labclaw/data)")
        print("  --memory-root PATH     Memory directory (default: /opt/labclaw/memory)")
        print("  --port PORT            API port (default: 18800)")
        print("  --dashboard-port PORT  Dashboard port (default: 18801)")


if __name__ == "__main__":
    main()
