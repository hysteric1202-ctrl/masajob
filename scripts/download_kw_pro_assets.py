from __future__ import annotations

import concurrent.futures
import json
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFont

OUT = Path("kw_pro_assets")
OUT.mkdir(parents=True, exist_ok=True)

# Limited to assets used in the final cut. The very long Platycerus source was removed:
# a shorter 720p moving stag-beetle shot gives better pacing and avoids oversized downloads.
ASSETS = [
    {"key":"forest","filename":"Mushroom forest video.webm","local":"forest.webm","kind":"video","author":"Treysam","license":"CC BY-SA 4.0","source_page":"https://commons.wikimedia.org/wiki/File:Mushroom_forest_video.webm"},
    {"key":"stag_walk","filename":"Stag Beetle (Lucanus cervus).webm","local":"stag_walk.webm","kind":"video","author":"Leonora Enking","license":"CC BY-SA 2.0","source_page":"https://commons.wikimedia.org/wiki/File:Stag_Beetle_(Lucanus_cervus).webm"},
    {"key":"stag_macro","filename":"Жук Олень.webm","local":"stag_macro.webm","kind":"video","author":"Сергій Ковальов","license":"CC BY-SA 4.0","source_page":"https://commons.wikimedia.org/wiki/File:Жук_Олень.webm"},
    {"key":"stag_fly","filename":"Lucanus cervus (Stag Bettle) Flying at Kew Gardens Railway Station.webm","local":"stag_fly.webm","kind":"video","author":"Rafe Roughton","license":"CC0 1.0","source_page":"https://commons.wikimedia.org/wiki/File:Lucanus_cervus_(Stag_Bettle)_Flying_at_Kew_Gardens_Railway_Station.webm"},
    {"key":"noko_tree","filename":"ミズナラにとまるノコギリクワガタ.JPG","local":"noko_tree.jpg","kind":"image","author":"Kinokoekuwagata","license":"CC BY-SA 4.0","source_page":"https://commons.wikimedia.org/wiki/File:ミズナラにとまるノコギリクワガタ.JPG"},
    {"key":"noko_pair","filename":"ヤナギの樹上のノコギリクワガタつがい.jpg","local":"noko_pair.jpg","kind":"image","author":"K fumishima","license":"CC BY-SA 4.0","source_page":"https://commons.wikimedia.org/wiki/File:ヤナギの樹上のノコギリクワガタつがい.jpg"},
    {"key":"kokuwa","filename":"Dorcus rectus (20806302162).jpg","local":"kokuwa.jpg","kind":"image","author":"harum.koh","license":"CC BY-SA 2.0","source_page":"https://commons.wikimedia.org/wiki/File:Dorcus_rectus_(20806302162).jpg"},
    {"key":"miyama","filename":"Lucanus maculifemoratus in Hiroshima Prefecture 01.jpg","local":"miyama.jpg","kind":"image","author":"ノボホショコロトソ","license":"CC BY 4.0","source_page":"https://commons.wikimedia.org/wiki/File:Lucanus_maculifemoratus_in_Hiroshima_Prefecture_01.jpg"},
    {"key":"hirata","filename":"Dorcus titanus pilifer (Vollenhoven,1861).jpg","local":"hirata.jpg","kind":"image","author":"takato marui","license":"CC BY-SA 2.0","source_page":"https://commons.wikimedia.org/wiki/File:Dorcus_titanus_pilifer_(Vollenhoven,1861).jpg"},
    {"key":"ookuwa","filename":"オオクワガタ.JPG","local":"ookuwa.jpg","kind":"image","author":"Ｋａｔｕｕｙａ","license":"CC BY-SA 3.0","source_page":"https://commons.wikimedia.org/wiki/File:オオクワガタ.JPG"},
]

HEADERS = {
    "User-Agent": "KuwagataTVProject/2.1 (private educational production; contact via GitHub repository)",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,video/webm,video/ogg,*/*;q=0.8",
    "Referer": "https://commons.wikimedia.org/",
}


def candidate_urls(asset: dict[str,str]) -> list[str]:
    encoded = quote(asset["filename"], safe="")
    base = f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{encoded}"
    return [base + "?width=1920", base] if asset["kind"] == "image" else [base]


def download_one(asset: dict[str,str]) -> dict[str,object]:
    target = OUT / asset["local"]
    if target.exists() and target.stat().st_size > 1000:
        return {"key":asset["key"],"status":"cached","bytes":target.stat().st_size}
    session = requests.Session()
    session.headers.update(HEADERS)
    last: Exception | None = None
    for candidate in candidate_urls(asset):
        for attempt in range(4):
            try:
                print(f"GET {asset['key']} attempt={attempt+1} {candidate}", flush=True)
                tmp = target.with_suffix(target.suffix + ".part")
                with session.get(candidate, timeout=(30,240), stream=True, allow_redirects=True) as response:
                    if response.status_code != 200:
                        raise RuntimeError(f"HTTP {response.status_code} {response.url}")
                    ctype = response.headers.get("content-type", "").lower()
                    if asset["kind"] == "image" and "image" not in ctype:
                        raise RuntimeError(f"unexpected content type {ctype}")
                    if asset["kind"] == "video" and not any(t in ctype for t in ("video", "octet-stream", "ogg")):
                        raise RuntimeError(f"unexpected content type {ctype}")
                    with tmp.open("wb") as fh:
                        for chunk in response.iter_content(1024*1024):
                            if chunk:
                                fh.write(chunk)
                if tmp.stat().st_size < 1000:
                    raise RuntimeError(f"download too small {tmp.stat().st_size}")
                tmp.replace(target)
                print("OK", asset["key"], target.stat().st_size, flush=True)
                return {"key":asset["key"],"status":"downloaded","bytes":target.stat().st_size,"download_url":candidate}
            except Exception as exc:
                last = exc
                print("RETRY", asset["key"], repr(exc), flush=True)
                time.sleep(2 + attempt*3)
    return {"key":asset["key"],"status":"failed","error":repr(last)}


def validate_asset(asset: dict[str,str]) -> dict[str,object]:
    path = OUT / asset["local"]
    row: dict[str,object] = {**asset,"bytes":path.stat().st_size}
    if asset["kind"] == "image":
        with Image.open(path) as im:
            im.load()
            row["width"], row["height"] = im.size
    else:
        cp = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration:stream=codec_name,width,height","-of","json",str(path)],text=True,capture_output=True,check=True)
        row["probe"] = json.loads(cp.stdout)
        subprocess.run(["ffmpeg","-v","error","-i",str(path),"-t","2","-f","null","-"],check=True)
    return row


def make_montage() -> None:
    fnt = ImageFont.load_default()
    for fp in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc","/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]:
        if Path(fp).exists():
            fnt = ImageFont.truetype(fp,28); break
    thumbs: list[tuple[str,Image.Image]]=[]
    for asset in ASSETS:
        path=OUT/asset["local"]
        if asset["kind"]=="image":
            im=Image.open(path).convert("RGB")
        else:
            jpg=OUT/f"_{asset['key']}_preview.jpg"
            subprocess.run(["ffmpeg","-y","-ss","1","-i",str(path),"-frames:v","1","-vf","scale=640:-2",str(jpg)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
            im=Image.open(jpg).convert("RGB")
        im.thumbnail((600,320)); thumbs.append((asset["key"],im.copy()))
    cols=3; cell_w=640; cell_h=380; rows=(len(thumbs)+cols-1)//cols
    canvas=Image.new("RGB",(cols*cell_w,rows*cell_h),"white"); draw=ImageDraw.Draw(canvas)
    for i,(label,im) in enumerate(thumbs):
        x=(i%cols)*cell_w+(cell_w-im.width)//2; y=(i//cols)*cell_h
        canvas.paste(im,(x,y)); draw.text(((i%cols)*cell_w+15,y+330),label,font=fnt,fill="black")
    canvas.save(OUT/"asset_montage.jpg",quality=92)


def main() -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(download_one,ASSETS))
    (OUT/"download_results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    failures=[r for r in results if r.get("status")=="failed"]
    if failures:
        raise RuntimeError(f"Asset downloads failed: {failures}")
    report={"assets":[validate_asset(a) for a in ASSETS]}
    (OUT/"asset_manifest.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    make_montage()

if __name__=="__main__":
    main()
