from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

VIDEO_ID = sys.argv[1] if len(sys.argv) > 1 else "wWYOgTFZ-FY"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "piped_fetch")
OUT.mkdir(parents=True, exist_ok=True)

INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.tokhmi.xyz",
    "https://pipedapi.moomoo.me",
    "https://pipedapi.syncpundit.io",
    "https://api-piped.mha.fi",
    "https://piped-api.garudalinux.org",
    "https://pipedapi.aeong.one",
    "https://watchapi.whatever.social",
    "https://pipedapi.leptons.xyz",
    "https://piped-api.lunar.icu",
    "https://api.piped.projectsegfau.lt",
    "https://api.piped.privacydev.net",
]

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
}

errors = []
info = None
base = None
for instance in INSTANCES:
    url = f"{instance}/streams/{VIDEO_ID}"
    try:
        print("TRY", url, flush=True)
        r = requests.get(url, headers=headers, timeout=30)
        print("STATUS", r.status_code, r.headers.get("content-type"), len(r.content), flush=True)
        if r.status_code == 200 and "json" in r.headers.get("content-type", "").lower():
            candidate = r.json()
            if candidate.get("videoStreams") or candidate.get("hls"):
                info = candidate
                base = instance
                break
        errors.append({"instance": instance, "status": r.status_code, "body": r.text[:300]})
    except Exception as exc:
        errors.append({"instance": instance, "error": repr(exc)})

(OUT / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
if info is None:
    raise SystemExit("No working Piped instance")

(OUT / "streams.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
summary = {
    "instance": base,
    "title": info.get("title"),
    "duration": info.get("duration"),
    "uploader": info.get("uploader"),
    "video_stream_count": len(info.get("videoStreams") or []),
    "audio_stream_count": len(info.get("audioStreams") or []),
    "hls": bool(info.get("hls")),
}
(OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))

# Download a modest progressive stream when available. Otherwise use the highest <=720p video-only stream.
streams = info.get("videoStreams") or []
progressive = [s for s in streams if not s.get("videoOnly") and (s.get("format") or "").lower() in {"mpeg_4", "mp4"}]
if progressive:
    progressive.sort(key=lambda s: (s.get("height") or 0, s.get("bitrate") or 0), reverse=True)
    chosen = next((s for s in progressive if (s.get("height") or 0) <= 720), progressive[-1])
else:
    video_only = [s for s in streams if (s.get("videoOnly") or False)]
    video_only.sort(key=lambda s: (s.get("height") or 0, s.get("bitrate") or 0), reverse=True)
    chosen = next((s for s in video_only if (s.get("height") or 0) <= 720), video_only[-1] if video_only else None)

if chosen and chosen.get("url"):
    stream_url = chosen["url"]
    ext = ".mp4" if "mp4" in (chosen.get("mimeType") or chosen.get("format") or "").lower() else ".webm"
    target = OUT / f"video{ext}"
    with requests.get(stream_url, headers=headers, timeout=120, stream=True) as r:
        r.raise_for_status()
        with target.open("wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
    print("DOWNLOADED", target, target.stat().st_size)
else:
    print("No downloadable stream selected")
