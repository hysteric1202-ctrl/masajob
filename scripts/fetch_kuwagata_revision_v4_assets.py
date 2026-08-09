#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("RUN:", " ".join(str(x) for x in cmd), flush=True)
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--pro-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    base_script = Path(__file__).with_name("fetch_kuwagata_revision_v3_assets.py")
    run([
        sys.executable,
        str(base_script),
        "--images-dir", str(args.images_dir),
        "--pro-dir", str(args.pro_dir),
        "--out", str(args.out),
    ])

    # The prior horizontal fallback showed a wetland with birds. That is not a
    # credible stag-beetle forest. Replace it with a slow, high-resolution move
    # across a real Japanese saw-stag-beetle photograph in leafy woodland.
    source = args.out / "noko_pair.jpg"
    target = args.out / "forest_h.webm"
    preview = args.out / "_forest_h_preview.jpg"
    run([
        "ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(source),
        "-t", "24", "-vf",
        "scale=1400:-2,crop=1280:720:(iw-1280)/2:(ih-720)/2,"
        "zoompan=z='min(zoom+0.00035,1.075)':x='iw/2-(iw/zoom/2)+sin(on/55)*18':"
        "y='ih/2-(ih/zoom/2)+cos(on/70)*12':d=576:s=1280x720:fps=24",
        "-an", "-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", str(target),
    ])
    run([
        "ffmpeg", "-y", "-v", "error", "-ss", "4", "-i", str(target),
        "-frames:v", "1", "-vf", "scale=620:-2", str(preview),
    ])

    manifest_path = args.out / "revision_asset_manifest.json"
    rows = json.loads(manifest_path.read_text(encoding="utf-8"))
    for row in rows:
        if row.get("name") == "forest_h.webm":
            row.update({
                "bytes": target.stat().st_size,
                "method": "animated real saw-stag-beetle woodland photograph",
                "author": "K fumishima",
                "license": "CC BY-SA 4.0",
                "source": "https://commons.wikimedia.org/wiki/File:ヤナギの樹上のノコギリクワガタつがい.jpg",
                "content_type": "video/webm (derived from licensed photograph)",
            })
            break
    manifest_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    # Rebuild the montage so visual QA shows the corrected woodland background.
    sys.path.insert(0, str(base_script.parent))
    import fetch_kuwagata_revision_v3_assets as base  # type: ignore
    base.montage(args.out)


if __name__ == "__main__":
    main()
