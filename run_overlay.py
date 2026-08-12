"""Runner script that reuses IFC path logic from main.py and calls tools.overlay_svg."""

from pathlib import Path
import os
from tools.overlay_svg import generate_svg_overlay


def main():
    num = "01"
    part = "D"
    year = "26"
    loc = "C:/Users/TIMMC/OneDrive - Danmarks Tekniske Universitet/Skrivebord/36" + year + part + "-A/BIM/"
    file_loc = os.path.join(loc, num, f"{year}-{num}-{part}-ARCH.ifc")

    ifc_path = Path(file_loc)
    if not ifc_path.exists():
        raise FileNotFoundError(f"IFC file not found: {ifc_path}")

    out_dir = Path("svg")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "overlay.svg"

    generate_svg_overlay(str(ifc_path), str(out_path))


if __name__ == '__main__':
    main()
