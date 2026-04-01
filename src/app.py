"""Compatibility entrypoint for the Streamlit app and parser helpers.

This module keeps historical ``streamlit run src/app.py`` usage working while
avoiding a second, divergent copy of the application logic.
"""

from __future__ import annotations

from pathlib import Path
import runpy

from utils.parser import convert_df_to_m3u, filter_channels, parse_m3u_lines


ROOT_APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


def main() -> None:
    """Execute the canonical Streamlit entrypoint from the project root."""
    runpy.run_path(str(ROOT_APP_PATH), run_name="__main__")


if __name__ == "__main__":
    main()
