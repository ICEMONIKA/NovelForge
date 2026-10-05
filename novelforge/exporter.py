from __future__ import annotations

import html
import json
import mimetypes
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def paras(s):return [x.strip() for x in re.split(r'\n\s*\n',s or '') if x.strip()]

def export_txt(db,path):
    out=[db.get_meta('title','小说'),'']
    for r in db.chapters():
        if r['content'].strip():out += [f'第{r["number"]}章 {r["title"]}'.strip(),r['content'].strip(),'']
    Path(path).write_text('\n'.join(out),'utf-8')

def export_md(db,path):
    out=[f'# {db.get_meta("title","小说")}','']
    for r in db.chapters():
        if r['content'].strip():out += [f'## 第{r["number"]}章 {r["title"]}'.strip(),' ',r['content'].strip(),'']
    Path(path).write_text('\n'.join(out),'utf-8')

def export_json(db,path):Path(path).write_text(json.dumps(db.full_state(),ensure_ascii=False,indent=2),'utf-8')

def export_epub(db,path,confirmed_only=True,cover=None):
    title=db.get_meta('title','小说'); author=db.get_meta('author',''); lang=db.get_meta('language','zh-CN'); rows=[r for r in db.chapters() if r['content'].strip() and (not confirmed_only or r['status']=='confirmed')]; uid='urn:uuid:'+str(uuid.uuid4()); modified=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
    manifest=['<item id="nav" properties="nav" href="nav.xhtml" media-type="application/xhtml+xml"/>','<item id="css" href="style.css" media-type="text/css"/>']; spine=[]; nav=[]; files=[]; cover_item=''
    cover_path=Path(cover) if cover else None
    if cover_path and cover_path.exists():
        mt=mimetypes.guess_type(cover_path.name)[0] or 'image/jpeg'; ext=cover_path.suffix.lower() or '.jpg';
        if ext not in {'.png','.jpg','.jpeg'}:
            raise ValueError('EPUB 封面仅支持 PNG/JPG/JPEG。')
        cover_name='cover'+('.jpg' if ext=='.jpeg' else ext); cover_item=f'<item id="cover-image" href="{cover_name}" media-type="{"image/jpeg" if cover_name.endswith(".jpg") else "image/png"}" properties="cover-image"/>'; manifest.append(cover_item)
    for r in rows:
        n=int(r['number']); fn=f'chapter_{n:04d}.xhtml'; cid=f'ch{n}'; h=f'第{n}章 {r["title"]}'.strip(); body=''.join(f'<p>{html.escape(x).replace(chr(10),"<br/>")}</p>' for x in paras(r['content'])); x=f'<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" lang="{html.escape(lang)}"><head><title>{html.escape(h)}</title><link rel="stylesheet" href="style.css"/></head><body><h1>{html.escape(h)}</h1>{body}</body></html>'; files.append((fn,x)); manifest.append(f'<item id="{cid}" href="{fn}" media-type="application/xhtml+xml"/>'); spine.append(f'<itemref idref="{cid}"/>'); nav.append(f'<li><a href="{fn}">{html.escape(h)}</a></li>')
    cover_meta=''
    if cover_path and cover_path.exists():cover_meta='<meta name="cover" content="cover-image"/>'
    opf=f'<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" unique-identifier="id" version="3.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">{uid}</dc:identifier><dc:title>{html.escape(title)}</dc:title>{f"<dc:creator>{html.escape(author)}</dc:creator>" if author else ""}<dc:language>{html.escape(lang)}</dc:language><meta property="dcterms:modified">{modified}</meta>{cover_meta}</metadata><manifest>{"".join(manifest)}</manifest><spine>{"".join(spine)}</spine></package>'
    navx=f'<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>{html.escape(title)}</title></head><body><nav epub:type="toc" id="toc"><h1>{html.escape(title)}</h1><ol>{"".join(nav)}</ol></nav></body></html>'
    css='body{font-family:serif;line-height:1.9;margin:8%;color:#111}h1{text-align:center;margin:0 0 2em}p{text-indent:2em;margin:0 0 1em;text-align:justify}'
    container='<?xml version="1.0" encoding="UTF-8"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'
    with zipfile.ZipFile(path,'w') as z:
        info=zipfile.ZipInfo('mimetype'); info.compress_type=zipfile.ZIP_STORED; z.writestr(info,'application/epub+zip'); z.writestr('META-INF/container.xml',container); z.writestr('OEBPS/content.opf',opf); z.writestr('OEBPS/nav.xhtml',navx); z.writestr('OEBPS/style.css',css)
        if cover_path and cover_path.exists():z.write(cover_path,'OEBPS/cover'+('.jpg' if cover_path.suffix.lower()=='.jpeg' else cover_path.suffix.lower()))
        for fn,x in files:z.writestr('OEBPS/'+fn,x)
