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
    "User-Agent": "Mozilla/5.0 (compatible; KuwagataExpeditionVideo/3.0; personal educational use)",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,video/webm,video/ogg,*/*;q=0.8",
    "Referer": "https://commons.wikimedia.org/",
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

REMOTE: dict[str, dict[str, Any]] = {
    "miyama_male.jpg": {
        "kind": "image",
        "urls": [
            "https://inaturalist-open-data.s3.amazonaws.com/photos/443897246/original.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/Lucanus_maculifemoratus_01.jpg/1280px-Lucanus_maculifemoratus_01.jpg",
            "https://commons.wikimedia.org/wiki/Special:Redirect/file/Lucanus%20maculifemoratus%2001.jpg?width=1280",
        ],
        "author": "Lee Junyoung (primary) / Σ64 (fallback)",
        "license": "CC BY-NC (primary) / CC BY 3.0 (fallback)",
        "source": "https://www.inaturalist.org/taxa/357786-Lucanus-maculifemoratus",
    },
    "hirata_dorsal.jpg": {
        "kind": "image",
        "urls": [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Dorcus_titanus.jpg/1280px-Dorcus_titanus.jpg",
            "https://commons.wikimedia.org/wiki/Special:Redirect/file/Dorcus%20titanus.jpg?width=1280",
            "https://upload.wikimedia.org/wikipedia/commons/3/3e/Dorcus_titanus.jpg",
        ],
        "author": "曾祥宇",
        "license": "CC BY-SA 4.0",
        "source": "https://commons.wikimedia.org/wiki/File:Dorcus_titanus.jpg",
    },
    "explorer.jpg": {
        "kind": "image",
        "urls": [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Boy_watching_with_binoculars.jpg/1280px-Boy_watching_with_binoculars.jpg",
            "https://commons.wikimedia.org/wiki/Special:Redirect/file/Boy%20watching%20with%20binoculars.jpg?width=1280",
            "https://upload.wikimedia.org/wikipedia/commons/a/ab/Boy_watching_with_binoculars.jpg",
        ],
        "author": "U.S. Fish and Wildlife Service",
        "license": "Public Domain",
        "source": "https://commons.wikimedia.org/wiki/File:Boy_watching_with_binoculars.jpg",
    },
    "japan_map.png": {
        "kind": "image",
        "urls": [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Regions_and_Prefectures_of_Japan_-_blank.svg/1200px-Regions_and_Prefectures_of_Japan_-_blank.svg.png",
            "https://commons.wikimedia.org/wiki/Special:Redirect/file/Regions%20and%20Prefectures%20of%20Japan%20-%20blank.svg?width=1200",
        ],
        "author": "Bigmorr",
        "license": "Public Domain",
        "source": "https://commons.wikimedia.org/wiki/File:Regions_and_Prefectures_of_Japan_-_blank.svg",
    },
}

FOREST_H_VIDEO_URLS = [
    "https://upload.wikimedia.org/wikipedia/commons/transcoded/c/c4/Cosumnes_River_Preserve_%2828137244773%29.webm/Cosumnes_River_Preserve_%2828137244773%29.webm.720p.vp9.webm?download=",
    "https://upload.wikimedia.org/wikipedia/commons/c/c4/Cosumnes_River_Preserve_%2828137244773%29.webm",
    "https://www.flickr.com/video_download.gne?id=28137244773",
]
FOREST_H_STILL_URLS = [
    "https://commons.wikimedia.org/wiki/Special:Redirect/file/Cosumnes%20River%20Preserve%20%2828137244773%29.jpg?width=1920",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c4/Cosumnes_River_Preserve_%2828137244773%29.webm/1280px--Cosumnes_River_Preserve_%2828137244773%29.webm.jpg",
]
FOREST_V_VIDEO_URLS = [
    "https://upload.wikimedia.org/wikipedia/commons/transcoded/2/2a/Walking_along_Rokuwatari_Path_at_the_foot_of_Mt_Nijozan_Osaka_Japan_June2025.webm/Walking_along_Rokuwatari_Path_at_the_foot_of_Mt_Nijozan_Osaka_Japan_June2025.webm.720p.vp9.webm?download=",
    "https://upload.wikimedia.org/wikipedia/commons/2/2a/Walking_along_Rokuwatari_Path_at_the_foot_of_Mt_Nijozan_Osaka_Japan_June2025.webm",
    "https://commons.wikimedia.org/wiki/Special:Redirect/file/Walking%20along%20Rokuwatari%20Path%20at%20the%20foot%20of%20Mt%20Nijozan%20Osaka%20Japan%20June2025.webm",
]


def run(cmd: list[str], *, capture: bool = False) -> str:
    print("RUN:", " ".join(str(x) for x in cmd), flush=True)
    cp = subprocess.run(cmd, check=True, text=True, capture_output=capture)
    return cp.stdout if capture else ""


def find_file(root: Path, name: str) -> Path:
    matches = list(root.rglob(name))
    if not matches:
        raise FileNotFoundError(f"Could not locate {name} under {root}")
    return matches[0]


def validate_image(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        image.load()
        return image.size


def validate_video(path: Path) -> dict[str, Any]:
    probe = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_name,width,height",
        "-of", "json", str(path),
    ], capture=True)
    data = json.loads(probe)
    run(["ffmpeg", "-v", "error", "-i", str(path), "-t", "2", "-f", "null", "-"])
    return data


def download(urls: list[str], target: Path, kind: str, attempts: int = 4) -> tuple[str, str]:
    session = requests.Session()
    session.headers.update(HEADERS)
    errors: list[str] = []
    for source_index, url in enumerate(urls, 1):
        for attempt in range(1, attempts + 1):
            tmp = target.with_suffix(target.suffix + ".part")
            try:
                print(f"GET {target.name} source={source_index} attempt={attempt}: {url}", flush=True)
                with session.get(url, timeout=(20, 240), stream=True, allow_redirects=True) as response:
                    if response.status_code != 200:
                        raise RuntimeError(f"HTTP {response.status_code} {response.url}")
                    with tmp.open("wb") as fh:
                        for chunk in response.iter_content(1024 * 1024):
                            if chunk:
                                fh.write(chunk)
                    if tmp.stat().st_size < 1000:
                        raise RuntimeError(f"file too small: {tmp.stat().st_size}")
                    tmp.replace(target)
                    if kind == "image":
                        validate_image(target)
                    else:
                        validate_video(target)
                    print("OK", target, target.stat().st_size, flush=True)
                    return response.url, response.headers.get("content-type", "")
            except Exception as exc:
                errors.append(f"{url}: {exc!r}")
                print("RETRY", target.name, repr(exc), flush=True)
                try:
                    tmp.unlink(missing_ok=True)
                except Exception:
                    pass
                time.sleep(4 + attempt * 5)
    raise RuntimeError(f"All sources failed for {target.name}: {errors[-8:]}")


def copy_validated(images_dir: Path, pro_dir: Path, out_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_name, target_name in COPIES.items():
        source = find_file(images_dir, source_name)
        target = out_dir / target_name
        shutil.copy2(source, target)
        width, height = validate_image(target)
        rows.append({"name": target_name, "kind": "image", "bytes": target.stat().st_size, "width": width, "height": height, "source_artifact": str(source)})
    for source_name, target_name in VIDEO_COPIES.items():
        source = find_file(pro_dir, source_name)
        target = out_dir / target_name
        shutil.copy2(source, target)
        rows.append({"name": target_name, "kind": "video", "bytes": target.stat().st_size, "probe": validate_video(target), "source_artifact": str(source)})
    return rows


def still_to_forest_video(still: Path, target: Path, vertical: bool) -> None:
    if vertical:
        vf = "scale=-2:1280,crop=720:1280:(iw-720)/2:0,zoompan=z='min(zoom+0.00045,1.08)':d=576:s=720x1280:fps=24"
    else:
        vf = "scale=1280:-2,crop=1280:720:0:(ih-720)/2,zoompan=z='min(zoom+0.00045,1.08)':d=576:s=1280x720:fps=24"
    run([
        "ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(still), "-t", "24",
        "-vf", vf, "-an", "-c:v", "libvpx-vp9", "-crf", "34", "-b:v", "0", str(target),
    ])
    validate_video(target)


def derive_vertical(horizontal: Path, target: Path) -> None:
    run([
        "ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(horizontal), "-t", "24",
        "-vf", "scale=-2:1280,crop=720:1280:(iw-720)/2:0", "-an",
        "-c:v", "libvpx-vp9", "-crf", "34", "-b:v", "0", str(target),
    ])
    validate_video(target)


def prepare_forests(out_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    horizontal = out_dir / "forest_h.webm"
    try:
        resolved, content_type = download(FOREST_H_VIDEO_URLS, horizontal, "video", attempts=3)
        method = "downloaded video"
    except Exception as exc:
        print("Horizontal forest video unavailable; using public forest still with motion:", repr(exc), flush=True)
        still = out_dir / "forest_h_still.jpg"
        resolved, content_type = download(FOREST_H_STILL_URLS, still, "image", attempts=4)
        still_to_forest_video(still, horizontal, False)
        method = "animated public still"
    rows.append({
        "name": horizontal.name, "kind": "video", "bytes": horizontal.stat().st_size,
        "probe": validate_video(horizontal), "resolved_url": resolved, "content_type": content_type,
        "method": method, "author": "Bob Wick / Bureau of Land Management", "license": "Public Domain",
        "source": "https://commons.wikimedia.org/wiki/File:Cosumnes_River_Preserve_(28137244773).webm",
    })

    vertical = out_dir / "forest_v.webm"
    try:
        resolved_v, content_type_v = download(FOREST_V_VIDEO_URLS, vertical, "video", attempts=3)
        method_v = "downloaded Osaka forest video"
    except Exception as exc:
        print("Vertical forest video unavailable; deriving vertical motion from horizontal forest:", repr(exc), flush=True)
        derive_vertical(horizontal, vertical)
        resolved_v, content_type_v = str(horizontal), "derived/video"
        method_v = "vertical crop of public forest footage"
    rows.append({
        "name": vertical.name, "kind": "video", "bytes": vertical.stat().st_size,
        "probe": validate_video(vertical), "resolved_url": resolved_v, "content_type": content_type_v,
        "method": method_v, "author": "Shironsilentpond when downloaded; otherwise Bob Wick / BLM crop",
        "license": "CC BY 4.0 when downloaded; otherwise Public Domain",
        "source": "https://commons.wikimedia.org/wiki/File:Walking_along_Rokuwatari_Path_at_the_foot_of_Mt_Nijozan_Osaka_Japan_June2025.webm",
    })
    return rows


def fetch_remote(out_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, spec in REMOTE.items():
        target = out_dir / name
        resolved, content_type = download(spec["urls"], target, spec["kind"], attempts=4)
        width, height = validate_image(target)
        rows.append({
            "name": name, "kind": "image", "bytes": target.stat().st_size,
            "width": width, "height": height, "resolved_url": resolved, "content_type": content_type,
            "author": spec["author"], "license": spec["license"], "source": spec["source"],
        })
        time.sleep(2)
    return rows


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
    cols, cell_w, cell_h = 3, 640, 390
    rows = (len(cells) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    for idx, (name, image) in enumerate(cells):
        x0, y0 = (idx % cols) * cell_w, (idx // cols) * cell_h
        canvas.paste(image, (x0 + (cell_w - image.width) // 2, y0 + 5))
        draw.text((x0 + 12, y0 + 342), name, font=fnt, fill="black")
    canvas.save(out_dir / "revision_asset_montage.jpg", quality=92)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--pro-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rows = copy_validated(args.images_dir, args.pro_dir, args.out)
    rows.extend(prepare_forests(args.out))
    rows.extend(fetch_remote(args.out))
    montage(args.out)
    (args.out / "revision_asset_manifest.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
