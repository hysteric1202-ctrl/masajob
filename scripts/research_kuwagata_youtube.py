from __future__ import annotations

import json
import math
import subprocess
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path("research_kuwagata")
ROOT.mkdir(exist_ok=True)

SEARCHES = [
    "クワガタ 子ども",
    "クワガタ 幼児",
    "クワガタ 子供向け 実写",
    "クワガタ 探す 子ども",
    "ノコギリクワガタ 動画",
    "コクワガタ 動画",
    "ミヤマクワガタ 動画",
    "ヒラタクワガタ 動画",
    "オオクワガタ 動画",
]

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("RUN:", " ".join(cmd), flush=True)
    return subprocess.run(cmd, text=True, capture_output=True, check=check)


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def yt_search(query: str, limit: int = 12) -> list[dict[str, Any]]:
    cp = run([
        "yt-dlp",
        f"ytsearch{limit}:{query}",
        "--flat-playlist",
        "--dump-single-json",
        "--no-warnings",
    ])
    data = json.loads(cp.stdout)
    return data.get("entries") or []


def compact_entry(entry: dict[str, Any], query: str) -> dict[str, Any]:
    return {
        "query": query,
        "id": entry.get("id"),
        "title": entry.get("title"),
        "url": entry.get("url") or entry.get("webpage_url"),
        "duration": entry.get("duration"),
        "channel": entry.get("channel") or entry.get("uploader"),
        "channel_id": entry.get("channel_id"),
        "view_count": entry.get("view_count"),
        "thumbnail": entry.get("thumbnail") or (entry.get("thumbnails") or [{}])[-1].get("url"),
    }


def download_reference() -> Path:
    url = "https://www.youtube.com/watch?v=wWYOgTFZ-FY"
    out_tmpl = str(ROOT / "reference.%(ext)s")
    clients = [
        "youtube:player_client=web_safari,web",
        "youtube:player_client=android,web",
        "youtube:player_client=tv,web",
    ]
    last = None
    for extractor_args in clients:
        cp = run([
            "yt-dlp",
            url,
            "--no-playlist",
            "--no-warnings",
            "--extractor-args",
            extractor_args,
            "-f",
            "bv*[height<=720]+ba/b[height<=720]",
            "--merge-output-format",
            "mp4",
            "-o",
            out_tmpl,
        ], check=False)
        if cp.returncode == 0:
            matches = sorted(ROOT.glob("reference.*"))
            videos = [p for p in matches if p.suffix.lower() in {".mp4", ".webm", ".mkv"}]
            if videos:
                return videos[0]
        last = cp.stderr
    raise RuntimeError(f"Reference download failed: {last}")


def ffprobe(path: Path) -> dict[str, Any]:
    cp = run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ])
    return json.loads(cp.stdout)


def make_contact_sheets(video: Path) -> None:
    frames = ROOT / "reference_frames"
    frames.mkdir(exist_ok=True)
    run([
        "ffmpeg", "-y", "-i", str(video), "-vf", "fps=1/4,scale=480:-2", "-q:v", "3",
        str(frames / "frame_%04d.jpg"),
    ])
    images = sorted(frames.glob("*.jpg"))
    if not images:
        return
    font = load_font(24)
    cols, rows = 4, 4
    cell_w, cell_h = 480, 300
    page_size = cols * rows
    for page in range(math.ceil(len(images) / page_size)):
        canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
        draw = ImageDraw.Draw(canvas)
        subset = images[page * page_size:(page + 1) * page_size]
        for i, p in enumerate(subset):
            im = Image.open(p).convert("RGB")
            im.thumbnail((cell_w, cell_h - 34))
            x = (i % cols) * cell_w + (cell_w - im.width) // 2
            y = (i // cols) * cell_h
            canvas.paste(im, (x, y))
            seconds = (page * page_size + i) * 4
            label = f"{seconds // 60:02d}:{seconds % 60:02d}"
            draw.text(((i % cols) * cell_w + 10, y + cell_h - 32), label, font=font, fill="black")
        canvas.save(ROOT / f"reference_contact_{page:02d}.jpg", quality=90)


def detect_scenes(video: Path) -> dict[str, Any]:
    # PySceneDetect is not required; OpenCV-based histogram deltas are enough for pacing estimates.
    import cv2
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    sample_step = max(1, round(fps / 2))  # 2 samples/sec
    previous = None
    cuts: list[float] = []
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % sample_step:
            idx += 1
            continue
        small = cv2.resize(frame, (160, 90))
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        if previous is not None:
            corr = cv2.compareHist(previous, hist, cv2.HISTCMP_CORREL)
            if corr < 0.55:
                cuts.append(idx / fps)
        previous = hist
        idx += 1
    cap.release()
    duration = total / fps if total else 0
    intervals = []
    points = [0.0] + cuts + ([duration] if duration else [])
    for a, b in zip(points, points[1:]):
        if b > a:
            intervals.append(b - a)
    return {
        "duration": duration,
        "estimated_scene_changes": len(cuts),
        "average_shot_seconds": (sum(intervals) / len(intervals)) if intervals else None,
        "median_shot_seconds": sorted(intervals)[len(intervals)//2] if intervals else None,
        "cuts_seconds": cuts,
    }


def make_search_montage(entries: list[dict[str, Any]]) -> None:
    import requests
    items = entries[:40]
    font_title = load_font(25)
    font_meta = load_font(18)
    cols = 4
    cell_w, cell_h = 480, 360
    rows = math.ceil(len(items) / cols)
    canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    for i, item in enumerate(items):
        x0 = (i % cols) * cell_w
        y0 = (i // cols) * cell_h
        thumb_url = item.get("thumbnail")
        if thumb_url:
            try:
                r = requests.get(thumb_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()
                tmp = ROOT / f"thumb_{i:03d}.jpg"
                tmp.write_bytes(r.content)
                im = Image.open(tmp).convert("RGB")
                im.thumbnail((cell_w, 250))
                canvas.paste(im, (x0 + (cell_w - im.width)//2, y0))
            except Exception as exc:
                draw.rectangle((x0, y0, x0 + cell_w, y0 + 250), outline="gray", width=2)
                draw.text((x0 + 10, y0 + 100), f"thumbnail error\n{exc}", font=font_meta, fill="black")
        title = textwrap.shorten(str(item.get("title") or ""), width=34, placeholder="…")
        meta = f"{item.get('channel') or ''} / {item.get('duration') or '?'}s"
        draw.text((x0 + 8, y0 + 258), title, font=font_title, fill="black")
        draw.text((x0 + 8, y0 + 310), meta, font=font_meta, fill="dimgray")
    canvas.save(ROOT / "search_montage.jpg", quality=90)


def main() -> None:
    all_entries: list[dict[str, Any]] = []
    for query in SEARCHES:
        try:
            results = yt_search(query)
            compact = [compact_entry(e, query) for e in results]
            all_entries.extend(compact)
            (ROOT / f"search_{SEARCHES.index(query):02d}.json").write_text(
                json.dumps(compact, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            print(f"Search failed for {query}: {exc}")
    # de-duplicate by video ID
    dedup: dict[str, dict[str, Any]] = {}
    for item in all_entries:
        key = str(item.get("id") or item.get("url") or len(dedup))
        dedup.setdefault(key, item)
    entries = list(dedup.values())
    (ROOT / "search_all.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    make_search_montage(entries)

    video = download_reference()
    info = ffprobe(video)
    (ROOT / "reference_ffprobe.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    make_contact_sheets(video)
    pacing = detect_scenes(video)
    (ROOT / "reference_pacing.json").write_text(json.dumps(pacing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(pacing, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
