from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

from .database import ProjectDB, SCHEMA_VERSION, now_iso


class Project:
    def __init__(self, folder: Path):
        self.folder=Path(folder); self.folder.mkdir(parents=True,exist_ok=True)
        for d in ['backups','exports','assets','logs']:(self.folder/d).mkdir(exist_ok=True)
        self.db=ProjectDB(self.folder/'project.sqlite3')

    @classmethod
    def create(cls,folder,title,total_chapters,volumes,raw_material,author=''):
        p=cls(folder);d=p.db;ts=now_iso();d.set_meta('schema_version',SCHEMA_VERSION);d.set_meta('title',title or '未命名小说');d.set_meta('author',author);d.set_meta('total_chapters',int(total_chapters));d.set_meta('volume_count',int(volumes));d.set_meta('raw_material',raw_material);d.set_meta('language','zh-CN');d.set_meta('subtitle','');d.set_meta('synopsis','');d.set_meta('canon','');d.set_meta('outline','');d.set_meta('style','');d.set_meta('initialization_status','pending')
        for n in range(1,int(volumes)+1):d.execute('INSERT OR IGNORE INTO volumes(number,title,synopsis,created_at,updated_at) VALUES(?,?,?,?,?)',[n,f'第{n}卷','',ts,ts])
        for n in range(1,int(total_chapters)+1):v=min(int(volumes),max(1,((n-1)*int(volumes))//max(1,int(total_chapters))+1));d.execute('INSERT OR IGNORE INTO chapters(number,volume_number,title,status,created_at,updated_at) VALUES(?,?,?,?,?,?)',[n,v,f'第{n}章','planned',ts,ts])
        d.execute('INSERT OR IGNORE INTO branches(id,name,parent_branch_id,base_chapter,status,description,created_at,updated_at) VALUES(1,?,?,?,?,?,?,?)',["主线",None,1,'active','正式主线',ts,ts]);d.conn.commit();d.save_snapshot('项目创建',d.full_state(),0);return p

    def close(self):self.db.close()

    def backup(self):
        out=self.folder/'backups'/f'backup_{now_iso().replace(":","-")}.novelforge'
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            for f in self.folder.rglob('*'):
                if f.is_file() and 'backups' not in f.parts and '__pycache__' not in f.parts:z.write(f,f.relative_to(self.folder))
        return out

    @staticmethod
    def import_archive(archive,target):
        target=Path(target);target.mkdir(parents=True,exist_ok=True);base=target.resolve()
        with zipfile.ZipFile(archive) as z:
            for x in z.infolist():
                dest=(target/x.filename).resolve()
                try: dest.relative_to(base)
                except ValueError: raise ValueError('归档包含非法路径。')
            z.extractall(target)
        return Project(target)

    @staticmethod
    def import_json(source,target):
        data=json.loads(Path(source).read_text('utf-8'));m=data.get('meta',{});chs=data.get('chapters',[])
        total=max(int(m.get('total_chapters',0) or 0), max([int(x.get('number',0)) for x in chs] or [1])); p=Project.create(target,m.get('title','导入小说'),total,int(m.get('volume_count',1) or 1),m.get('raw_material',''),m.get('author','')); d=p.db
        for k,v in m.items():
            try:d.set_meta(k,json.loads(v)) if isinstance(v,str) and v[:1] in '[{' else d.set_meta(k,v)
            except Exception:d.set_meta(k,v)
        for c in chs:
            n=int(c.get('number',0))
            if n:d.save_chapter(n,c.get('title',f'第{n}章'),c.get('content',''),c.get('plan',''),c.get('status','draft'),'import','JSON导入',pov=c.get('pov_character',''),perspective=c.get('perspective','third_limited'),tense=c.get('tense','past'))
        for f in data.get('canon_facts',[]):
            d.save_canon_fact(f.get('category','其他'),f.get('name',''),f.get('content',''),f.get('lock_level','normal'),f.get('source','import'),f.get('source_chapter'),f.get('scope','canon'),f.get('status','active'))
        for e in data.get('entities',[]):
            d.save_entity(e.get('kind','other'),e.get('name',''),e.get('description',''),json.loads(e.get('data','{}')) if isinstance(e.get('data'),str) else e.get('data',{}),json.loads(e.get('aliases','[]')) if isinstance(e.get('aliases'),str) else e.get('aliases',[]),e.get('source_chapter'),e.get('scope','canon'))
        for r in data.get('relationships',[]):d.save_relationship(r.get('source_name',''),r.get('target_name',''),r.get('relation','unknown'),float(r.get('strength',.5)),r.get('note',''),r.get('source_chapter'),r.get('scope','dynamic'))
        for e in data.get('events',[]):d.save_event(e.get('title',''),e.get('description',''),e.get('chapter_number'),e.get('event_time',''),int(e.get('importance',2)),json.loads(e.get('tags','[]')) if isinstance(e.get('tags'),str) else e.get('tags',[]),e.get('source_chapter'),e.get('scope','dynamic'))
        for f in data.get('foreshadows',[]):d.save_foreshadow(f.get('code',''),f.get('description',''),f.get('introduced_chapter'),f.get('target_chapter'),f.get('status','open'),int(f.get('importance',2)),f.get('notes',''),f.get('lifecycle','introduced'),f.get('last_touched_chapter'),f.get('scope','canon'))
        for s in data.get('summaries',[]):d.save_summary(int(s.get('range_start',1)),int(s.get('range_end',1)),s.get('summary',''),s.get('level','chapter'))
        for k in data.get('knowledge',[]):d.save_knowledge(k.get('character_name',''),k.get('fact',''),k.get('knowledge_type','known'),k.get('certainty','known'),k.get('source_chapter'),k.get('last_updated_chapter'))
        for a in data.get('arcs',[]):d.save_character_arc(a,a.get('source_chapter'))
        for i in data.get('intents',[]):d.set_intent(i.get('scope_type','project'),i.get('scope_key','global'),i.get('title',''),i.get('content',''),int(i.get('priority',3)),bool(i.get('hard',False)))
        if data.get('style'):d.save_style(data['style'])
        d.save_snapshot('JSON导入完成',d.full_state(),0);return p


def restore_full_state(db, data):
    """把 full_state() 导出的快照数据写回数据库（快照恢复用）。章节会生成新 revision。"""
    for c in data.get('chapters') or []:
        n=int(c.get('number',0) or 0)
        if n:
            db.save_chapter(n, c.get('title',f'第{n}章'), c.get('content',''), c.get('plan',''), c.get('status','draft'), 'restore', '从快照恢复', pov=c.get('pov_character',''), perspective=c.get('perspective','third_limited'), tense=c.get('tense','past'))
    for t in ['canon_facts','entities','relationships','events','foreshadows','summaries','character_knowledge','character_arcs','author_intents']:
        db.execute(f'DELETE FROM {t}'); db.conn.commit()
    def j(v):
        if isinstance(v,str):
            try:return json.loads(v)
            except Exception:return []
        return v or []
    for f in data.get('canon_facts') or []:
        db.save_canon_fact(f.get('category','其他'),f.get('name',''),f.get('content',''),f.get('lock_level','normal'),f.get('source','restore'),f.get('source_chapter'),f.get('scope','canon'),f.get('status','active'))
    for e in data.get('entities') or []:
        db.save_entity(e.get('kind','other'),e.get('name',''),e.get('description',''),j(e.get('data',{})),j(e.get('aliases',[])),e.get('source_chapter'),e.get('scope','canon'))
    for r in data.get('relationships') or []:
        db.save_relationship(r.get('source_name',''),r.get('target_name',''),r.get('relation','unknown'),float(r.get('strength',.5)),r.get('note',''),r.get('source_chapter'),r.get('scope','dynamic'))
    for e in data.get('events') or []:
        db.save_event(e.get('title',''),e.get('description',''),e.get('chapter_number'),e.get('event_time',''),int(e.get('importance',2)),j(e.get('tags',[])),e.get('source_chapter'),e.get('scope','dynamic'))
    for f in data.get('foreshadows') or []:
        db.save_foreshadow(f.get('code',''),f.get('description',''),f.get('introduced_chapter'),f.get('target_chapter'),f.get('status','open'),int(f.get('importance',2)),f.get('notes',''),f.get('lifecycle','introduced'),f.get('last_touched_chapter'),f.get('scope','canon'))
    for s in data.get('summaries') or []:
        db.save_summary(int(s.get('range_start',1)),int(s.get('range_end',1)),s.get('summary',''),s.get('level','chapter'))
    for k in data.get('knowledge') or []:
        db.save_knowledge(k.get('character_name',''),k.get('fact',''),k.get('knowledge_type','known'),k.get('certainty','known'),k.get('source_chapter'),k.get('last_updated_chapter'))
    for a in data.get('arcs') or []:
        db.save_character_arc(a,a.get('source_chapter'))
    for i in data.get('intents') or []:
        db.set_intent(i.get('scope_type','project'),i.get('scope_key','global'),i.get('title',''),i.get('content',''),int(i.get('priority',3)),bool(i.get('hard',False)))
    if data.get('style'):db.save_style(data['style'])
    for k,v in (data.get('meta') or {}).items():
        if k in ('schema_version','active_branch_id'):continue
        db.set_meta(k,v)
    db.save_log('info','snapshot_restore','从快照恢复完成')
    db.save_snapshot('从快照恢复',db.full_state(),0)
