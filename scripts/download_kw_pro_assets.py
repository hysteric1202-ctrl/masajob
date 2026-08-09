from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFont

OUT = Path('kw_pro_assets')
OUT.mkdir(parents=True, exist_ok=True)

ASSETS = [
    {'key':'forest','filename':'Mushroom forest video.webm','local':'forest.webm','author':'Treysam','license':'CC BY-SA 4.0','source_page':'https://commons.wikimedia.org/wiki/File:Mushroom_forest_video.webm'},
    {'key':'stag_walk','filename':'Stag Beetle (Lucanus cervus).webm','local':'stag_walk.webm','author':'Leonora Enking','license':'CC BY-SA 2.0','source_page':'https://commons.wikimedia.org/wiki/File:Stag_Beetle_(Lucanus_cervus).webm'},
    {'key':'stag_macro','filename':'Жук Олень.webm','local':'stag_macro.webm','author':'Сергій Ковальов','license':'CC BY-SA 4.0','source_page':'https://commons.wikimedia.org/wiki/File:Жук_Олень.webm'},
]
HEADERS={
    'User-Agent':'KuwagataTVProject/3.0 (private educational production; contact via GitHub repository)',
    'Accept':'video/webm,video/ogg,application/octet-stream,*/*;q=0.8',
    'Referer':'https://commons.wikimedia.org/',
}

def original_url(filename: str) -> str:
    normalized=filename.replace(' ','_')
    digest=hashlib.md5(normalized.encode('utf-8')).hexdigest()
    encoded=quote(normalized,safe='()_,.-')
    return f'https://upload.wikimedia.org/wikipedia/commons/{digest[0]}/{digest[:2]}/{encoded}'

def download(asset: dict[str,str]) -> dict[str,object]:
    target=OUT/asset['local']; url=original_url(asset['filename']); last=None
    for attempt in range(8):
        try:
            print(f"GET {asset['key']} attempt={attempt+1} {url}",flush=True)
            tmp=target.with_suffix(target.suffix+'.part')
            with requests.get(url,headers=HEADERS,timeout=(30,360),stream=True,allow_redirects=True) as r:
                if r.status_code!=200:
                    raise RuntimeError(f'HTTP {r.status_code} {r.url}')
                ctype=r.headers.get('content-type','').lower()
                if not any(x in ctype for x in ('video','ogg','octet-stream')):
                    raise RuntimeError(f'unexpected content type {ctype}')
                with tmp.open('wb') as fh:
                    for chunk in r.iter_content(1024*1024):
                        if chunk: fh.write(chunk)
            if tmp.stat().st_size<10000: raise RuntimeError(f'download too small {tmp.stat().st_size}')
            tmp.replace(target)
            print('OK',asset['key'],target.stat().st_size,flush=True)
            time.sleep(12)
            return {**asset,'bytes':target.stat().st_size,'url':url}
        except Exception as exc:
            last=exc
            print('RETRY',asset['key'],repr(exc),flush=True)
            time.sleep(min(20+attempt*15,120))
    raise RuntimeError(f"{asset['key']}: {last}")

def validate(asset: dict[str,str]) -> dict[str,object]:
    path=OUT/asset['local']
    cp=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_name,width,height','-of','json',str(path)],text=True,capture_output=True,check=True)
    probe=json.loads(cp.stdout)
    subprocess.run(['ffmpeg','-v','error','-i',str(path),'-t','3','-f','null','-'],check=True)
    return {**asset,'bytes':path.stat().st_size,'probe':probe,'url':original_url(asset['filename'])}

def montage() -> None:
    font=ImageFont.load_default()
    for fp in ['/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']:
        if Path(fp).exists(): font=ImageFont.truetype(fp,28); break
    canvas=Image.new('RGB',(640*3,400),'white'); d=ImageDraw.Draw(canvas)
    for i,a in enumerate(ASSETS):
        jpg=OUT/f"_{a['key']}_preview.jpg"
        subprocess.run(['ffmpeg','-y','-ss','1','-i',str(OUT/a['local']),'-frames:v','1','-vf','scale=620:-2',str(jpg)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
        im=Image.open(jpg).convert('RGB'); im.thumbnail((620,330))
        x=i*640+(640-im.width)//2; canvas.paste(im,(x,0)); d.text((i*640+12,342),a['key'],font=font,fill='black')
    canvas.save(OUT/'video_montage.jpg',quality=92)

rows=[download(a) for a in ASSETS]
report={'downloaded':rows,'validated':[validate(a) for a in ASSETS]}
(OUT/'video_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
montage()
