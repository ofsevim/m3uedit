"""Installed CLI and repository launcher use the same Streamlit entrypoint."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def app_path() -> Path:
    return Path(__file__).resolve().parent.parent / "app.py"


def main(argv=None):
    parser = argparse.ArgumentParser(description="M3U Editör Pro")
    parser.add_argument(
        "--check", action="store_true", help="Check setup without starting the server"
    )
    options, extra = parser.parse_known_args(argv)
    from utils import config

    path = app_path()
    if options.check:
        import pandas
        import streamlit

        print(
            f"Hazır: M3U Editör {config.APP_VERSION}; Streamlit {streamlit.__version__}; pandas {pandas.__version__}"
        )
        if not path.is_file() or not (path.parent / "static" / "styles.css").is_file():
            raise RuntimeError("Uygulama veya stil dosyası eksik.")
        return 0
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(path),
        "--server.address",
        os.environ.get("SERVER_HOST", "127.0.0.1"),
        "--server.port",
        os.environ.get("SERVER_PORT", "8501"),
        "--server.maxUploadSize",
        str(config.MAX_FILE_SIZE_MB),
        *extra,
    ]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
