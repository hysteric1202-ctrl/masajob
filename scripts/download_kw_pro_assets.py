from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFont

OUT = Path("kw_pro_assets")
OUT.mkdir(parents=True, exist_ok=True)

ASSETS = [
    {
        "key": "forest",
        "filename": "Mushroom forest video.webm",
        "local": "forest.webm",
        "kind": "video",
        "author": "Treysam",
        "license": "CC BY-SA 4.0",
        "source_page": "https://commons.wikimedia.org/wiki/File:Mushroom_forest_video.webm",
    },
    {
        "key": "stag_walk",
        "filename": "Stag Beetle (Lucanus cervus).webm",
        "local": "stag_walk.webm",
        "kind": "video",
        "author": "Leonora Enking",
        "license": "CC BY-SA 2.0",
        "source_page": "https://commons.wikimedia.org/wiki/File:Stag_Beetle_(Lucanus_cervus).webm",
    },
    {
        "key": "stag_macro",
        "filename": "Жук Олень.webm",
        "local": "stag_macro.webm",
        "kind": "video",
        "author": "Сергій Ковальов",
        "license": "CC BY-SA 4.0",
        "source_page": "https://commons.wikimedia.org/wiki/File:Жук_Олень.webm",
    },
    {
        "key": "stag_fly",
        "filename": "Lucanus cervus (Stag Bettle) Flying at Kew Gardens Railway Station.webm",
        "local": "stag_fly.webm",
        "kind": "video",
        "author": "Rafe Roughton",
        "license": "CC0 1.0",
        "source_page": "https://commons.wikimedia.org/wiki/File:Lucanus_cervus_(Stag_Bettle)_Flying_at_Kew_Gardens_Railway_Station.webm",
    },
    {
        "key": "platycerus",
        "filename": "Platycerus caraboides - 2012-05-08.ogv",
        "local": "platycerus.ogv",
        "kind": "video",
        "author": "Pristurus",
        "license": "CC BY-SA 3.0",
        "source_page": "https://commons.wikimedia.org/wiki/File:Platycerus_caraboides_-_2012-05-08.ogv",
    },
    {
        "key": "noko_tree",
        "filename": "ミズナラにとまるノコギリクワガタ.JPG",
        "local": "noko_tree.jpg",
        "kind": "image",
        "author": "Kinokoekuwagata",
        "license": "CC BY-SA 4.0",
        "source_page": "https://commons.wikimedia.org/wiki/File:ミズナラにとまるノコギリクワガタ.JPG",
    },
    {
        "key": "noko_pair",
        "filename": "ヤナギの樹上のノコギリクワガタつがい.jpg",
        "local": "noko_pair.jpg",
        "kind": "image",
        "author": "K fumishima",
        "license": "CC BY-SA 4.0",
        "source_page": "https://commons.wikimedia.org/wiki/File:ヤナギの樹上のノコギリクワガタつがい.jpg",
    },
    {
        "key": "kokuwa",
        "filename": "Dorcus rectus (20806302162).jpg",
        "local": "kokuwa.jpg",
        "kind": "image",
        "author": "harum.koh",
        "license": "CC BY-SA 2.0",
        "source_page": "https://commons.wikimedia.org/wiki/File:Dorcus_rectus_(20806302162).jpg",
    },
    {
        "key": "miyama",
        "filename": "Lucanus maculifemoratus in Hiroshima Prefecture 01.jpg",
        "local": "miyama.jpg",
        "kind": "image",
        "author": "ノボホショコロトソ",
        "license": "CC BY 4.0",
        "source_page": "https://commons.wikimedia.org/wiki/File:Lucanus_maculifemoratus_in_Hiroshima_Prefecture_01.jpg",
    },
    {
        "key": "hirata",
        "filename": "Dorcus titanus pilifer (Vollenhoven,1861).jpg",
        "local": "hirata.jpg",
        "kind": "image",
        "author": "takato marui",
        "license": "CC BY-SA 2.0",
        "source_page": "https://commons.wikimedia.org/wiki/File:Dorcus_titanus_pilifer_(Vollenhoven,1861).jpg",
    },
    {
        "key": "ookuwa",
        "filename": "オオクワガタ.JPG",
        "local": "ookuwa.jpg",
        "kind": "image",
        "author": "Ｋａｔｕｕｙａ",
        "license": "CC BY-SA 3.0",
        "source_page": "https://commons.wikimedia.org/wiki/File:オオクワガタ.JPG",
    },
]

HEADERS = {
    "User-Agent": "KuwagataTVProject/2.0 (educational private-use prototype)",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,video/webm,video/ogg,*/*;q=0.8",
    "Referer": "https://commons.wikimedia.org/",
}


def download(asset: dict[str, str]) -> None:
    filename = asset["filename"]
    target = OUT / asset["local"]
    encoded = quote(filename, safe="")
    candidates = [
        f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{encoded}",
        f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{encoded}?width=1920",
    ]
    session = requests.Session()
    session.headers.update(HEADERS)
    last: Exception | None = None
    for candidate in candidates:
        for attempt in range(8):
            try:
                print("GET", candidate, "attempt", attempt + 1, flush=True)
                with session.get(candidate, timeout=180, stream=True, allow_redirects=True) as response:
                    if response.status_code != 200:
                        raise RuntimeError(f"HTTP {response.status_code} {response.url}")
                    with target.open("wb") as fh:
                        for chunk in response.iter_content(1024 * 1024):
                            if chunk:
                                fh.write(chunk)
                if target.stat().st_size < 1000:
                    raise RuntimeError(f"Downloaded file too small: {target.stat().st_size}")
                print("OK", target, target.stat().st_size, flush=True)
                return
            except Exception as exc:
                last = exc
                time.sleep(min(4 * (attempt + 1), 30))
    raise RuntimeError(f"Could not download {filename}: {last}")


def validate() -> dict[str, object]:
    report: dict[str, object] = {"assets": []}
    rows = report["assets"]
    assert isinstance(rows, list)
    for asset in ASSETS:
        path = OUT / asset["local"]
        item: dict[str, object] = {**asset, "bytes": path.stat().st_size}
        if asset["kind"] == "image":
            with Image.open(path) as im:
                im.verify()
            with Image.open(path) as im:
                item["width"], item["height"] = im.size
        else:
            cp = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_name,width,height", "-of", "json", str(path)],
                text=True,
                capture_output=True,
                check=True,
            )
            item["probe"] = json.loads(cp.stdout)
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-t", "3", "-f", "null", "-"], check=True)
        rows.append(item)
    return report


def make_montage() -> None:
    font = None
    for fp in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]:
        if Path(fp).exists():
            font = ImageFont.truetype(fp, 28)
            break
    font = font or ImageFont.load_default()
    thumbs: list[tuple[str, Image.Image]] = []
    for asset in ASSETS:
        path = OUT / asset["local"]
        if asset["kind"] == "image":
            im = Image.open(path).convert("RGB")
        else:
            jpg = OUT / f"_{asset['key']}_preview.jpg"
            subprocess.run(["ffmpeg", "-y", "-ss", "1", "-i", str(path), "-frames:v", "1", "-vf", "scale=640:-2", str(jpg)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            im = Image.open(jpg).convert("RGB")
        im.thumbnail((600, 320))
        thumbs.append((asset["key"], im.copy()))
    cols = 3
    cell_w, cell_h = 640, 380
    rows = (len(thumbs) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    for i, (label, im) in enumerate(thumbs):
        x = (i % cols) * cell_w + (cell_w - im.width) // 2
        y = (i // cols) * cell_h
        canvas.paste(im, (x, y))
        draw.text(((i % cols) * cell_w + 15, y + 330), label, font=font, fill="black")
    canvas.save(OUT / "asset_montage.jpg", quality=92)


def main() -> None:
    for asset in ASSETS:
        download(asset)
    report = validate()
    (OUT / "asset_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    make_montage()


if __name__ == "__main__":
    main()
