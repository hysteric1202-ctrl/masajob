#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont

HEADERS = {
    "User-Agent": "KuwagataExpeditionVideo/2.0 (personal educational video; contact via GitHub)",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,video/webm,video/ogg,*/*;q=0.8",
}

DOWNLOADS: dict[str, dict[str, Any]] = {
    "forest_h.webm": {
        "kind": "video",
        "urls": [
            "https://upload.wikimedia.org/wikipedia/commons/c/c4/Cosumnes_River_Preserve_%2828137244773%29.webm",
            "https://commons.wikimedia.org/wiki/Special:Redirect/file/Cosumnes%20River%20Preserve%20%2828137244773%29.webm",
        ],
        "author": "Bob Wick / Bureau of Land Management",
        "license": "Public-domain U.S. government footage (as hosted by Wikimedia Commons)",
        "source": "https://commons.wikimedia.org/wiki/File:Cosumnes_River_Preserve_(28137244773).webm",
    },
    "forest_v.webm": {
        "kind": "video",
        "urls": [
            "https://upload.wikimedia.org/wikipedia/commons/2/2a/Walking_along_Rokuwatari_Path_at_the_foot_of_Mt_Nijozan_Osaka_Japan_June2025.webm",
            "https://commons.wikimedia.org/wiki/Special:Redirect/file/Walking%20along%20Rokuwatari%20Path%20at%20the%20foot%20of%20Mt%20Nijozan%20Osaka%20Japan%20June2025.webm",
        ],
        "author": "Shironsilentpond",
        "license": "CC BY 4.0",
        "source": "https://commons.wikimedia.org/wiki/File:Walking_along_Rokuwatari_Path_at_the_foot_of_Mt_Nijozan_Osaka_Japan_June2025.webm",
    },
    "miyama_male.jpg": {
        "kind": "image",
        "urls": [
            "https://inaturalist-open-data.s3.amazonaws.com/photos/443897246/original.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/a/a8/Lucanus_maculifemoratus_01.jpg",
        ],
        "author": "Lee Junyoung (primary) / Σ64 (fallback)",
        "license": "CC BY-NC (primary) / CC BY 3.0 (fallback)",
        "source": "https://www.inaturalist.org/taxa/357786-Lucanus-maculifemoratus",
    },
    "hirata_dorsal.jpg": {
        "kind": "image",
        "urls": [
            "https://upload.wikimedia.org/wikipedia/commons/3/3e/Dorcus_titanus.jpg",
            "https://commons.wikimedia.org/wiki/Special:Redirect/file/Dorcus%20titanus.jpg",
        ],
        "author": "曾祥宇",
        "license": "CC BY-SA 4.0",
        "source": "https://commons.wikimedia.org/wiki/File:Dorcus_titanus.jpg",
    },
    "explorer.jpg": {
        "kind": "image",
        "urls": [
            "https://upload.wikimedia.org/wikipedia/commons/a/ab/Boy_watching_with_binoculars.jpg",
            "https://commons.wikimedia.org/wiki/Special:Redirect/file/Boy%20watching%20with%20binoculars.jpg",
        ],
        "author": "U.S. Fish and Wildlife Service",
        "license": "Public Domain",
        "source": "https://commons.wikimedia.org/wiki/File:Boy_watching_with_binoculars.jpg",
    },
    "japan_map.svg": {
        "kind": "svg",
        "urls": [
            "https://upload.wikimedia.org/wikipedia/commons/3/31/Regions_and_Prefectures_of_Japan_-_blank.svg",
            "https://commons.wikimedia.org/wiki/Special:Redirect/file/Regions%20and%20Prefectures%20of%20Japan%20-%20blank.svg",
        ],
        "author": "Bigmorr",
        "license": "Public Domain",
        "source": "https://commons.wikimedia.org/wiki/File:Regions_and_Prefectures_of_Japan_-_blank.svg",
    },
}

COPIES = {
    "noko_tree.jpg": "noko_tree.jpg",
    "noko_pair.jpg": "noko_pair.jpg",
    "kokuwa.jpg": "kokuwa.jpg",
    "ookuwa.jpg": "ookuwa.jpg",
}
VIDEO_COPIES = {
    "stag_walk.webm": "stag_walk.webm",
    "stag_macro.webm": "stag_macro.webm",
}


def run(cmd: list[str], *, capture: bool = False) -> str:
    print("RUN:", " ".join(str(x) for x in cmd), flush=True)
    cp = subprocess.run(cmd, check=True, text=True, capture_output=capture)
    return cp.stdout if capture else ""


def download_one(name: str, spec: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    target = out_dir / name
    session = requests.Session()
    session.headers.update(HEADERS)
    last_error: Exception | None = None
    for url_index, url in enumerate(spec["urls"]):
        for attempt in range(8):
            try:
                print(f"GET {name} source={url_index + 1} attempt={attempt + 1} {url}", flush=True)
                with session.get(url, stream=True, timeout=(25, 360), allow_redirects=True) as response:
                    if response.status_code != 200:
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            time.sleep(min(120, max(3, int(float(retry_after)))))
                        raise RuntimeError(f"HTTP {response.status_code} {response.url}")
                    ctype = response.headers.get("content-type", "").lower()
                    tmp = target.with_suffix(target.suffix + ".part")
                    with tmp.open("wb") as fh:
                        for chunk in response.iter_content(1024 * 1024):
                            if chunk:
                                fh.write(chunk)
                    if tmp.stat().st_size < 1000:
                        raise RuntimeError(f"too small: {tmp.stat().st_size}")
                    tmp.replace(target)
                    row = {
                        "name": name,
                        "kind": spec["kind"],
                        "bytes": target.stat().st_size,
                        "resolved_url": response.url,
                        "content_type": ctype,
                        "author": spec["author"],
                        "license": spec["license"],
                        "source": spec["source"],
                    }
                    validate_one(target, spec["kind"], row)
                    print("OK", name, target.stat().st_size, flush=True)
                    time.sleep(4)
                    return row
            except Exception as exc:
                last_error = exc
                print("RETRY", name, repr(exc), flush=True)
                time.sleep(min(8 + attempt * 12, 90))
    raise RuntimeError(f"Failed to download {name}: {last_error}")


def validate_one(path: Path, kind: str, row: dict[str, Any]) -> None:
    if kind == "image":
        with Image.open(path) as image:
            image.load()
            row["width"], row["height"] = image.size
    elif kind == "svg":
        if b"<svg" not in path.read_bytes()[:4096].lower():
            raise RuntimeError(f"Invalid SVG: {path}")
    else:
        probe = run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_name,width,height",
            "-of", "json", str(path),
        ], capture=True)
        row["probe"] = json.loads(probe)
        run(["ffmpeg", "-v", "error", "-i", str(path), "-t", "2", "-f", "null", "-"])


def find_file(root: Path, name: str) -> Path:
    matches = list(root.rglob(name))
    if not matches:
        raise FileNotFoundError(f"Could not locate {name} under {root}")
    return matches[0]


def copy_assets(images_dir: Path, pro_dir: Path, out_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for src_name, dst_name in COPIES.items():
        src = find_file(images_dir, src_name)
        dst = out_dir / dst_name
        shutil.copy2(src, dst)
        row: dict[str, Any] = {"name": dst_name, "kind": "image", "bytes": dst.stat().st_size, "source_artifact": str(src)}
        validate_one(dst, "image", row)
        rows.append(row)
    for src_name, dst_name in VIDEO_COPIES.items():
        src = find_file(pro_dir, src_name)
        dst = out_dir / dst_name
        shutil.copy2(src, dst)
        row = {"name": dst_name, "kind": "video", "bytes": dst.stat().st_size, "source_artifact": str(src)}
        validate_one(dst, "video", row)
        rows.append(row)
    return rows


def render_map(out_dir: Path) -> dict[str, Any]:
    source = out_dir / "japan_map.svg"
    target = out_dir / "japan_map.png"
    run(["rsvg-convert", "-w", "1200", "-h", "1600", "-o", str(target), str(source)])
    row: dict[str, Any] = {"name": target.name, "kind": "image", "bytes": target.stat().st_size, "derived_from": source.name}
    validate_one(target, "image", row)
    return row


def montage(out_dir: Path) -> None:
    font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
    fnt = ImageFont.truetype(font_path, 28) if Path(font_path).exists() else ImageFont.load_default()
    names = [
        "noko_tree.jpg", "noko_pair.jpg", "kokuwa.jpg", "ookuwa.jpg",
        "miyama_male.jpg", "hirata_dorsal.jpg", "explorer.jpg", "japan_map.png",
        "forest_h.webm", "forest_v.webm", "stag_walk.webm", "stag_macro.webm",
    ]
    cells: list[tuple[str, Image.Image]] = []
    for name in names:
        path = out_dir / name
        if path.suffix.lower() in {".webm", ".mp4", ".ogv", ".mkv"}:
            preview = out_dir / f"_{path.stem}_preview.jpg"
            run(["ffmpeg", "-y", "-v", "error", "-ss", "1", "-i", str(path), "-frames:v", "1", "-vf", "scale=620:-2", str(preview)])
            image = Image.open(preview).convert("RGB")
        else:
            image = Image.open(path).convert("RGB")
        image.thumbnail((600, 330), Image.Resampling.LANCZOS)
        cells.append((name, image.copy()))
    cols = 3
    cell_w, cell_h = 640, 390
    rows = (len(cells) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    for idx, (name, image) in enumerate(cells):
        x0 = (idx % cols) * cell_w
        y0 = (idx // cols) * cell_h
        x = x0 + (cell_w - image.width) // 2
        y = y0 + 5
        canvas.paste(image, (x, y))
        draw.text((x0 + 12, y0 + 342), name, font=fnt, fill="black")
    canvas.save(out_dir / "revision_asset_montage.jpg", quality=92)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--pro-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rows = copy_assets(args.images_dir, args.pro_dir, args.out)
    for name, spec in DOWNLOADS.items():
        rows.append(download_one(name, spec, args.out))
    rows.append(render_map(args.out))
    montage(args.out)
    (args.out / "revision_asset_manifest.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
