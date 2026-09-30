"""Create/reuse a repository virtual environment and launch the app."""

import argparse
import subprocess
import sys
import venv
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="M3U Editör kurulum ve başlatma")
    parser.add_argument("--check", action="store_true")
    options, extra = parser.parse_known_args(argv)
    if sys.version_info < (3, 11):
        parser.error("Python 3.11 veya üstü gerekli.")
    root = Path(__file__).resolve().parent
    environment = next(
        (root / name for name in (".venv", "venv") if (root / name).is_dir()), root / ".venv"
    )
    python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not python.is_file():
        if options.check:
            print("Sanal ortam bulunamadı. Kurulum için run.bat veya run.sh çalıştırın.")
            return 1
        venv.EnvBuilder(with_pip=True).create(environment)
    check = subprocess.run(
        [
            str(python),
            "-c",
            "from importlib.metadata import version; from packaging.specifiers import SpecifierSet; "
            "assert version('streamlit') in SpecifierSet('>=1.52,<2'); "
            "assert version('pandas') in SpecifierSet('>=2,<3')",
        ],
        capture_output=True,
        cwd=root,
    )
    if check.returncode:
        if options.check:
            print("Bağımlılıklar eksik veya uyumsuz. run.bat / run.sh ile kurulumu tamamlayın.")
            return 1
        pip = subprocess.run([str(python), "-m", "pip", "--version"], capture_output=True)
        if pip.returncode:
            subprocess.run([str(python), "-m", "ensurepip", "--upgrade"], check=True)
        subprocess.run(
            [str(python), "-m", "pip", "install", "-r", str(root / "requirements.txt")], check=True
        )
    return subprocess.call(
        [str(python), "-m", "utils.launcher", *(["--check"] if options.check else []), *extra],
        cwd=root,
    )


if __name__ == "__main__":
    raise SystemExit(main())
