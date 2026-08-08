from pathlib import Path
import sys

p = Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp/build_kuwagata_dual.py')
s = p.read_text(encoding='utf-8')
old = '''    url = info.get("thumburl") or info["url"]
    img = requests.get(url, headers=headers, timeout=60)
    img.raise_for_status()
    out_path.write_bytes(img.content)
'''
new = '''    url = info.get("thumburl") or info["url"]
    from urllib.parse import quote
    import time
    clean_thumb = url.split("?", 1)[0]
    clean_original = info["url"].split("?", 1)[0]
    candidates = [
        clean_thumb,
        f"https://commons.wikimedia.org/w/thumb.php?f={quote(file_name, safe='')}&w={width}",
        f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{quote(file_name, safe='')}?width={width}",
    ]
    if not file_name.lower().endswith(".svg"):
        candidates.append(clean_original)
    session = requests.Session()
    session.headers.update({
        "User-Agent": "KuwagataEducationVideo/1.0 (https://github.com/hysteric1202-ctrl/masajob; educational use)",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Referer": "https://commons.wikimedia.org/",
    })
    last_error = None
    downloaded = False
    for candidate in dict.fromkeys(candidates):
        for attempt in range(7):
            try:
                img = session.get(candidate, timeout=120, allow_redirects=True)
                ctype = img.headers.get("content-type", "").lower()
                if img.status_code == 200 and ctype.startswith("image/") and len(img.content) > 1000:
                    out_path.write_bytes(img.content)
                    url = candidate
                    downloaded = True
                    break
                last_error = RuntimeError(
                    f"HTTP {img.status_code}; type={ctype}; bytes={len(img.content)}; url={candidate}"
                )
                retry_after = img.headers.get("Retry-After")
                wait = int(retry_after) if retry_after and retry_after.isdigit() else min(4 * (attempt + 1), 24)
                time.sleep(wait)
            except Exception as exc:
                last_error = exc
                time.sleep(min(4 * (attempt + 1), 24))
        if downloaded:
            break
    if not downloaded:
        raise RuntimeError(f"Could not download {file_name}: {last_error}")
    time.sleep(2)
'''
if old not in s:
    raise SystemExit('download block not found')
p.write_text(s.replace(old, new, 1), encoding='utf-8')
print(f'patched {p}')
