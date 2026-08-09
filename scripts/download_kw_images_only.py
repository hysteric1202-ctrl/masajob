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
 {'key':'noko_tree','filename':'ミズナラにとまるノコギリクワガタ.JPG','local':'noko_tree.jpg','author':'Kinokoekuwagata','license':'CC BY-SA 4.0','source_page':'https://commons.wikimedia.org/wiki/File:ミズナラにとまるノコギリクワガタ.JPG'},
 {'key':'noko_pair','filename':'ヤナギの樹上のノコギリクワガタつがい.jpg','local':'noko_pair.jpg','author':'K fumishima','license':'CC BY-SA 4.0','source_page':'https://commons.wikimedia.org/wiki/File:ヤナギの樹上のノコギリクワガタつがい.jpg'},
 {'key':'kokuwa','filename':'Dorcus rectus.jpg','local':'kokuwa.jpg','author':'takato marui','license':'CC BY-SA 2.0','source_page':'https://commons.wikimedia.org/wiki/File:Dorcus_rectus.jpg'},
 {'key':'miyama','filename':'ミズナラのミヤマクワガタ.JPG','local':'miyama.jpg','author':'Kinokoekuwagata','license':'CC BY-SA 4.0','source_page':'https://commons.wikimedia.org/wiki/File:ミズナラのミヤマクワガタ.JPG'},
 {'key':'hirata','filename':'Dorcus titanus pilifer (Vollenhoven,1861).jpg','local':'hirata.jpg','author':'takato marui','license':'CC BY-SA 2.0','source_page':'https://commons.wikimedia.org/wiki/File:Dorcus_titanus_pilifer_(Vollenhoven,1861).jpg'},
 {'key':'ookuwa','filename':'Dorcushopeibinodulosus.JPG','local':'ookuwa.jpg','author':'keusju','license':'CC BY-SA 3.0 / GFDL','source_page':'https://commons.wikimedia.org/wiki/File:Dorcushopeibinodulosus.JPG'},
]
HEADERS={'User-Agent':'KuwagataTVProject/2.6','Referer':'https://commons.wikimedia.org/','Accept':'image/*,*/*;q=0.8'}

def original_url(filename: str) -> str:
    normalized=filename.replace(' ','_')
    digest=hashlib.md5(normalized.encode('utf-8')).hexdigest()
    encoded=quote(normalized,safe='()_,.-')
    return f'https://upload.wikimedia.org/wikipedia/commons/{digest[0]}/{digest[:2]}/{encoded}'

def get_one(a):
    url=original_url(a['filename']); target=OUT/a['local']; last=None
    for attempt in range(7):
        try:
            r=requests.get(url,headers=HEADERS,timeout=(20,240),allow_redirects=True)
            if r.status_code!=200 or 'image' not in r.headers.get('content-type','').lower() or len(r.content)<1000:
                raise RuntimeError(f'{r.status_code} {r.headers.get("content-type")} {len(r.content)} {r.url}')
            target.write_bytes(r.content)
            with Image.open(target) as im: im.load(); size=im.size
            print('OK',a['key'],target.stat().st_size,size,flush=True)
            time.sleep(3)
            return {**a,'bytes':target.stat().st_size,'size':size,'url':r.url}
        except Exception as e:
            last=e; print('RETRY',a['key'],repr(e),flush=True); time.sleep(min(10+attempt*10,70))
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
