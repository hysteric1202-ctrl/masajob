from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFont

OUT=Path('kw_image_assets'); OUT.mkdir(exist_ok=True)
ASSETS=[
 {'key':'noko_tree','filename':'ミズナラにとまるノコギリクワガタ.JPG','local':'noko_tree.jpg'},
 {'key':'noko_pair','filename':'ヤナギの樹上のノコギリクワガタつがい.jpg','local':'noko_pair.jpg'},
 {'key':'kokuwa','filename':'Dorcus rectus (20806302162).jpg','local':'kokuwa.jpg'},
 {'key':'miyama','filename':'Lucanus maculifemoratus in Hiroshima Prefecture 01.jpg','local':'miyama.jpg'},
 {'key':'hirata','filename':'Dorcus titanus pilifer (Vollenhoven,1861).jpg','local':'hirata.jpg'},
 {'key':'ookuwa','filename':'オオクワガタ.JPG','local':'ookuwa.jpg'},
]
HEADERS={'User-Agent':'KuwagataTVProject/2.3','Referer':'https://commons.wikimedia.org/','Accept':'image/*,*/*;q=0.8'}


def original_url(filename: str) -> str:
    normalized=filename.replace(' ','_')
    digest=hashlib.md5(normalized.encode('utf-8')).hexdigest()
    encoded=quote(normalized,safe='()_,.-')
    return f'https://upload.wikimedia.org/wikipedia/commons/{digest[0]}/{digest[:2]}/{encoded}'


def get_one(a):
    url=original_url(a['filename']); target=OUT/a['local']; last=None
    for attempt in range(5):
        try:
            r=requests.get(url,headers=HEADERS,timeout=(20,180),allow_redirects=True)
            if r.status_code!=200 or 'image' not in r.headers.get('content-type','').lower() or len(r.content)<1000:
                raise RuntimeError(f'{r.status_code} {r.headers.get("content-type")} {len(r.content)} {r.url}')
            target.write_bytes(r.content)
            with Image.open(target) as im: im.load(); size=im.size
            print('OK',a['key'],target.stat().st_size,size,flush=True)
            time.sleep(1.2)
            return {**a,'bytes':target.stat().st_size,'size':size,'url':r.url}
        except Exception as e:
            last=e; print('RETRY',a['key'],repr(e),flush=True); time.sleep(5+attempt*5)
    raise RuntimeError(f'{a["key"]}: {last}')


def montage(rows):
    font=ImageFont.load_default()
    for fp in ['/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']:
        if Path(fp).exists(): font=ImageFont.truetype(fp,30); break
    cell=(640,430); cols=2; rcount=(len(rows)+1)//2
    canvas=Image.new('RGB',(cell[0]*cols,cell[1]*rcount),'white'); d=ImageDraw.Draw(canvas)
    for i,a in enumerate(rows):
        im=Image.open(OUT/a['local']).convert('RGB'); im.thumbnail((620,360))
        x=(i%cols)*cell[0]+(cell[0]-im.width)//2; y=(i//cols)*cell[1]
        canvas.paste(im,(x,y)); d.text(((i%cols)*cell[0]+10,y+370),a['key'],font=font,fill='black')
    canvas.save(OUT/'image_montage.jpg',quality=93)

rows=[get_one(a) for a in ASSETS]
(OUT/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
montage(rows)
