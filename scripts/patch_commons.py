from pathlib import Path
import re
import sys

p = Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp/build_kuwagata_dual.py')
s = p.read_text(encoding='utf-8')

replacement = r'''def commons_download(file_name: str, out_path: Path, width: int = 1800) -> dict[str, str]:
    """Download one verified Wikimedia Commons file without using the rate-limited API."""
    from urllib.parse import quote
    import time

    encoded = quote(file_name, safe='')
    source_url = f"https://commons.wikimedia.org/wiki/File:{encoded}"
    candidates = [
        f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{encoded}?width={width}",
        f"https://commons.wikimedia.org/w/thumb.php?f={encoded}&w={width}",
        f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{encoded}",
    ]
    session = requests.Session()
    session.headers.update({
        "User-Agent": "KuwagataEducationVideo/1.0 (https://github.com/hysteric1202-ctrl/masajob; educational use)",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Referer": "https://commons.wikimedia.org/",
    })
    last_error = None
    for candidate in dict.fromkeys(candidates):
        for attempt in range(10):
            try:
                response = session.get(candidate, timeout=150, allow_redirects=True)
                ctype = response.headers.get("content-type", "").lower()
                if response.status_code == 200 and ctype.startswith("image/") and len(response.content) > 1000:
                    out_path.write_bytes(response.content)
                    time.sleep(5)
                    return {
                        "source_url": source_url,
                        "download_url": response.url,
                        "artist": "",
                        "license": "",
                    }
                last_error = RuntimeError(
                    f"HTTP {response.status_code}; type={ctype}; bytes={len(response.content)}; url={candidate}"
                )
                retry_after = response.headers.get("Retry-After")
                wait = int(retry_after) if retry_after and retry_after.isdigit() else min(6 * (attempt + 1), 60)
                time.sleep(wait)
            except Exception as exc:
                last_error = exc
                time.sleep(min(6 * (attempt + 1), 60))
    raise RuntimeError(f"Could not download {file_name}: {last_error}")
'''

pattern = r"def commons_download\(file_name: str, out_path: Path, width: int = 1800\) -> dict\[str, str\]:\n.*?\n\ndef load_assets"
s, count = re.subn(pattern, replacement + "\n\ndef load_assets", s, count=1, flags=re.S)
if count != 1:
    raise SystemExit(f'commons_download function replacement failed: {count}')

if 'RATE = "-8%"' not in s:
    raise SystemExit('RATE assignment not found')
s = s.replace('RATE = "-8%"', 'RATE = "+20%"', 1)

old_tts = '''    run(["edge-tts","--voice",VOICE,"--rate",RATE,"--pitch",PITCH,"--file",str(script_path),"--write-media",str(raw_audio),"--write-subtitles",str(raw_srt)])
'''
new_tts = '''    run(["edge-tts","--voice",VOICE,f"--rate={RATE}",f"--pitch={PITCH}","--file",str(script_path),"--write-media",str(raw_audio),"--write-subtitles",str(raw_srt)])
'''
if old_tts not in s:
    raise SystemExit('edge-tts command block not found')
s = s.replace(old_tts, new_tts, 1)

old_mobile_style = '''        style="FontName=Noto Sans CJK JP,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00131A15,BackColour=&H96000000,BorderStyle=3,Outline=1,Shadow=0,Alignment=2,MarginL=42,MarginR=42,MarginV=48"
'''
new_mobile_style = '''        style="FontName=Noto Sans CJK JP,FontSize=12,PrimaryColour=&H00FFFFFF,OutlineColour=&H00131A15,BackColour=&H70000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginL=46,MarginR=46,MarginV=58"
'''
if old_mobile_style not in s:
    raise SystemExit('mobile subtitle style not found')
s = s.replace(old_mobile_style, new_mobile_style, 1)

p.write_text(s, encoding='utf-8')
print(f'patched {p}')
