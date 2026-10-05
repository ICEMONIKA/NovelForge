from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 14


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


SCHEMA = '''
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS volumes(id INTEGER PRIMARY KEY AUTOINCREMENT,number INTEGER UNIQUE,title TEXT,synopsis TEXT DEFAULT '',created_at TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS chapters(id INTEGER PRIMARY KEY AUTOINCREMENT,number INTEGER UNIQUE,volume_number INTEGER DEFAULT 1,title TEXT DEFAULT '',plan TEXT DEFAULT '',content TEXT DEFAULT '',status TEXT DEFAULT 'planned',current_revision INTEGER DEFAULT 0,summary TEXT DEFAULT '',word_count INTEGER DEFAULT 0,stale INTEGER DEFAULT 0,pov_character TEXT DEFAULT '',perspective TEXT DEFAULT 'third_limited',tense TEXT DEFAULT 'past',created_at TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS chapter_revisions(id INTEGER PRIMARY KEY AUTOINCREMENT,chapter_number INTEGER,revision INTEGER,title TEXT,content TEXT,source TEXT,note TEXT DEFAULT '',plan TEXT DEFAULT '',status TEXT DEFAULT 'draft',pov_character TEXT DEFAULT '',perspective TEXT DEFAULT 'third_limited',tense TEXT DEFAULT 'past',created_at TEXT,UNIQUE(chapter_number,revision));
CREATE TABLE IF NOT EXISTS canon_facts(id INTEGER PRIMARY KEY AUTOINCREMENT,category TEXT,name TEXT,content TEXT,lock_level TEXT DEFAULT 'normal',status TEXT DEFAULT 'active',scope TEXT DEFAULT 'canon',source TEXT DEFAULT 'author',source_chapter INTEGER,updated_at TEXT);
CREATE TABLE IF NOT EXISTS entities(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,name TEXT,aliases TEXT DEFAULT '[]',description TEXT DEFAULT '',data TEXT DEFAULT '{}',status TEXT DEFAULT 'active',scope TEXT DEFAULT 'canon',source_chapter INTEGER,updated_at TEXT,UNIQUE(kind,name,scope));
CREATE TABLE IF NOT EXISTS relationships(id INTEGER PRIMARY KEY AUTOINCREMENT,source_name TEXT,target_name TEXT,relation TEXT,strength REAL DEFAULT .5,note TEXT DEFAULT '',scope TEXT DEFAULT 'dynamic',source_chapter INTEGER,updated_at TEXT,UNIQUE(source_name,target_name,relation,scope));
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,chapter_number INTEGER,event_time TEXT DEFAULT '',title TEXT,description TEXT DEFAULT '',importance INTEGER DEFAULT 2,tags TEXT DEFAULT '[]',status TEXT DEFAULT 'active',scope TEXT DEFAULT 'dynamic',source_chapter INTEGER,updated_at TEXT);
CREATE TABLE IF NOT EXISTS foreshadows(id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT UNIQUE,description TEXT,introduced_chapter INTEGER,target_chapter INTEGER,status TEXT DEFAULT 'open',importance INTEGER DEFAULT 2,notes TEXT DEFAULT '',lifecycle TEXT DEFAULT 'introduced',last_touched_chapter INTEGER,scope TEXT DEFAULT 'canon',updated_at TEXT);
CREATE TABLE IF NOT EXISTS summaries(id INTEGER PRIMARY KEY AUTOINCREMENT,range_start INTEGER,range_end INTEGER,summary TEXT,level TEXT DEFAULT 'chapter',created_at TEXT);
CREATE TABLE IF NOT EXISTS state_updates(id INTEGER PRIMARY KEY AUTOINCREMENT,chapter_number INTEGER,payload TEXT,applied INTEGER DEFAULT 1,revision INTEGER DEFAULT 0,created_at TEXT);
CREATE TABLE IF NOT EXISTS state_proposals(id INTEGER PRIMARY KEY AUTOINCREMENT,chapter_number INTEGER,revision INTEGER DEFAULT 0,payload TEXT,reason TEXT DEFAULT '',status TEXT DEFAULT 'pending',created_at TEXT,reviewed_at TEXT);
CREATE TABLE IF NOT EXISTS setting_proposals(id INTEGER PRIMARY KEY AUTOINCREMENT,chapter_number INTEGER,revision INTEGER DEFAULT 0,payload TEXT,reason TEXT DEFAULT '',status TEXT DEFAULT 'pending',created_at TEXT,reviewed_at TEXT);
CREATE TABLE IF NOT EXISTS character_knowledge(id INTEGER PRIMARY KEY AUTOINCREMENT,character_name TEXT,fact TEXT,knowledge_type TEXT DEFAULT 'known',certainty TEXT DEFAULT 'known',source_chapter INTEGER,last_updated_chapter INTEGER,status TEXT DEFAULT 'active',UNIQUE(character_name,fact));
CREATE TABLE IF NOT EXISTS character_arcs(id INTEGER PRIMARY KEY AUTOINCREMENT,character_name TEXT UNIQUE,stage TEXT DEFAULT '',desire TEXT DEFAULT '',fear TEXT DEFAULT '',belief TEXT DEFAULT '',conflict TEXT DEFAULT '',transformation TEXT DEFAULT '',next_stage TEXT DEFAULT '',trigger_event TEXT DEFAULT '',source_chapter INTEGER,updated_at TEXT);
CREATE TABLE IF NOT EXISTS author_intents(id INTEGER PRIMARY KEY AUTOINCREMENT,scope_type TEXT,scope_key TEXT,title TEXT,content TEXT,priority INTEGER DEFAULT 3,hard INTEGER DEFAULT 0,status TEXT DEFAULT 'active',created_at TEXT,updated_at TEXT,UNIQUE(scope_type,scope_key,title));
CREATE TABLE IF NOT EXISTS branches(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,parent_branch_id INTEGER,base_chapter INTEGER DEFAULT 1,status TEXT DEFAULT 'draft',description TEXT DEFAULT '',created_at TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS branch_chapters(id INTEGER PRIMARY KEY AUTOINCREMENT,branch_id INTEGER,chapter_number INTEGER,source_revision INTEGER,status TEXT DEFAULT 'active',UNIQUE(branch_id,chapter_number));
CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT,label TEXT,chapter_number INTEGER,payload TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS audit_issues(id INTEGER PRIMARY KEY AUTOINCREMENT,chapter_number INTEGER,severity TEXT,issue_type TEXT,message TEXT,location TEXT DEFAULT '',references_json TEXT DEFAULT '[]',resolved INTEGER DEFAULT 0,created_at TEXT);
CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,status TEXT,chapter_number INTEGER,progress INTEGER DEFAULT 0,stage TEXT DEFAULT '',detail TEXT DEFAULT '',started_at TEXT,finished_at TEXT,error TEXT DEFAULT '',usage_json TEXT DEFAULT '{}',result_json TEXT DEFAULT '{}');
CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT,level TEXT,event TEXT,message TEXT,detail TEXT DEFAULT '',created_at TEXT);
CREATE TABLE IF NOT EXISTS style_profiles(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT,source_chapter INTEGER,updated_at TEXT);
CREATE INDEX IF NOT EXISTS idx_chapters_number ON chapters(number);
CREATE INDEX IF NOT EXISTS idx_entities_scope ON entities(scope,kind);
CREATE INDEX IF NOT EXISTS idx_events_scope ON events(scope,chapter_number);
CREATE INDEX IF NOT EXISTS idx_knowledge_char ON character_knowledge(character_name);

'''


class ProjectDB:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.migrate()

    def close(self):
        self.conn.commit()
        self.conn.close()

    def migrate(self):
        additions = {
            'chapters': [('pov_character', "TEXT DEFAULT ''"), ('perspective', "TEXT DEFAULT 'third_limited'"), ('tense', "TEXT DEFAULT 'past'")],
            'chapter_revisions': [('plan', "TEXT DEFAULT ''"), ('status', "TEXT DEFAULT 'draft'"), ('pov_character', "TEXT DEFAULT ''"), ('perspective', "TEXT DEFAULT 'third_limited'"), ('tense', "TEXT DEFAULT 'past'")],
            'entities': [('scope', "TEXT DEFAULT 'canon'"), ('source_chapter', 'INTEGER')],
            'canon_facts': [('scope', "TEXT DEFAULT 'canon'"), ('status', "TEXT DEFAULT 'active'")],
            'foreshadows': [('scope', "TEXT DEFAULT 'canon'")],
            'jobs': [('progress', 'INTEGER DEFAULT 0'), ('stage', "TEXT DEFAULT ''"), ('detail', "TEXT DEFAULT ''"), ('result_json', "TEXT DEFAULT '{}'")],
        }
        for table, cols in additions.items():
            existing = {r['name'] for r in self.query(f'PRAGMA table_info({table})')}
            for name, spec in cols:
                if name not in existing:
                    self.execute(f'ALTER TABLE {table} ADD COLUMN {name} {spec}')
        # 确保任何数据库都存在“主线”分支（旧项目兜底）。
        self.execute("INSERT OR IGNORE INTO branches(id,name,parent_branch_id,base_chapter,status,description,created_at,updated_at) VALUES(1,'主线',NULL,1,'active','正式主线',?,?)",[now_iso(),now_iso()])
        self.set_meta('schema_version', SCHEMA_VERSION)

    def execute(self, sql: str, params: Iterable[Any] = ()):
        return self.conn.execute(sql, tuple(params))

    def query(self, sql: str, params: Iterable[Any] = ()):
        return list(self.execute(sql, params).fetchall())

    def one(self, sql: str, params: Iterable[Any] = ()):
        return self.execute(sql, params).fetchone()

    @contextmanager
    def transaction(self):
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def set_meta(self, key: str, value: Any):
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        self.execute('INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', [key, raw])
        self.conn.commit()

    def get_meta(self, key: str, default=''):
        r = self.one('SELECT value FROM meta WHERE key=?', [key])
        if not r:
            return default
        try:
            return json.loads(r['value'])
        except Exception:
            return r['value']

    def save_chapter(self, n, title, content, plan='', status='draft', source='user', note='', pov='', perspective='third_limited', tense='past'):
        old = self.chapter(n)
        rev = (int(old['current_revision']) + 1 if old else 1)
        ts = now_iso()
        f_pov = pov or (old['pov_character'] if old else '') or ''
        f_perspective = perspective or (old['perspective'] if old else 'third_limited') or 'third_limited'
        f_tense = tense or (old['tense'] if old else 'past') or 'past'
        if old and old['status'] == 'confirmed' and status != 'confirmed':
            self.invalidate_state(n)
            self.mark_stale_after(n)
        if old:
            self.execute(
                'UPDATE chapters SET title=?,content=?,plan=?,status=?,current_revision=?,word_count=?,stale=0,pov_character=?,perspective=?,tense=?,updated_at=? WHERE number=?',
                [title, content, plan, status, rev, len(''.join(content.split())), f_pov, f_perspective, f_tense, ts, n]
            )
        else:
            self.execute(
                'INSERT INTO chapters(number,volume_number,title,plan,content,status,current_revision,word_count,pov_character,perspective,tense,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                [n, 1, title, plan, content, status, rev, len(''.join(content.split())), f_pov, f_perspective, f_tense, ts, ts]
            )
        self.execute('INSERT INTO chapter_revisions(chapter_number,revision,title,content,source,note,created_at,plan,status,pov_character,perspective,tense) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', [n, rev, title, content, source, note, ts, plan, status, f_pov, f_perspective, f_tense])
        # 记录当前分支对本章的内容指针（分支切换时据此恢复内容）。
        self.record_branch_chapter(self.active_branch_id(), n, rev)
        self.conn.commit()
        return rev

    def chapter(self, n): return self.one('SELECT * FROM chapters WHERE number=?', [n])
    def chapters(self): return self.query('SELECT * FROM chapters ORDER BY number')
    def recent_chapters(self, before, count):
        return self.query("SELECT * FROM chapters WHERE number<? AND status='confirmed' ORDER BY number DESC LIMIT ?", [before, max(1, int(count))])
    def revisions(self, n): return self.query('SELECT * FROM chapter_revisions WHERE chapter_number=? ORDER BY revision DESC', [n])
    def mark_stale_after(self, n):
        self.execute("UPDATE chapters SET stale=1 WHERE number>? AND status IN ('confirmed','generated','draft')", [n])
        self.conn.commit()
    def mark_chapter_stale(self, n):
        self.execute('UPDATE chapters SET stale=1 WHERE number=?', [n]); self.conn.commit()
    def invalidate_state(self, n):
        self.execute('DELETE FROM state_updates WHERE chapter_number=?', [n])
        self.execute("UPDATE state_proposals SET status='rejected',reviewed_at=? WHERE chapter_number=? AND status='pending'", [now_iso(), n])
        self.conn.commit()

    def save_entity(self, kind, name, description='', data=None, aliases=None, source_chapter=None, scope='canon'):
        self.execute(
            '''INSERT INTO entities(kind,name,aliases,description,data,status,scope,source_chapter,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(kind,name,scope) DO UPDATE SET aliases=excluded.aliases,description=excluded.description,
               data=excluded.data,status=excluded.status,source_chapter=excluded.source_chapter,updated_at=excluded.updated_at''',
            [kind, name, json.dumps(aliases or [], ensure_ascii=False), description, json.dumps(data or {}, ensure_ascii=False), 'active', scope, source_chapter, now_iso()]
        )
        self.conn.commit()

    def entity(self, kind, name, scope='canon'):
        return self.one('SELECT * FROM entities WHERE kind=? AND name=? AND scope=?', [kind, name, scope])

    def update_entity(self, kind, name, *, new_name=None, description=None, data=None, aliases=None, scope='canon', merge_data=True):
        old = self.entity(kind, name, scope)
        if not old:
            raise ValueError(f'找不到实体：{kind} / {name}（{scope}）')
        existing = json.loads(old['data'] or '{}')
        incoming = data if isinstance(data, dict) else None
        merged = dict(existing)
        if incoming is not None and merge_data:
            merged.update(incoming)
        elif incoming is not None:
            merged = incoming
        final_name = (new_name or old['name']).strip()
        self.execute(
            '''UPDATE entities SET name=?,aliases=?,description=?,data=?,updated_at=? WHERE id=?''',
            [final_name, json.dumps(aliases if aliases is not None else json.loads(old['aliases'] or '[]'), ensure_ascii=False),
             old['description'] if description is None else description, json.dumps(merged, ensure_ascii=False), now_iso(), old['id']]
        )
        self.conn.commit()

    def delete_entity(self, kind, name, scope='canon'):
        cur = self.execute('DELETE FROM entities WHERE kind=? AND name=? AND scope=?', [kind, name, scope]); self.conn.commit(); return cur.rowcount
    def entities(self, kind=None, scope=None):
        wh, p = [], []
        if kind: wh.append('kind=?'); p.append(kind)
        if scope: wh.append('scope=?'); p.append(scope)
        return self.query('SELECT * FROM entities' + (' WHERE ' + ' AND '.join(wh) if wh else '') + ' ORDER BY kind,name', p)

    def save_canon_fact(self, category, name, content, lock_level='normal', source='author', source_chapter=None, scope='canon', status='active'):
        old = self.one('SELECT id FROM canon_facts WHERE category=? AND name=? AND scope=?', [category, name, scope])
        if old:
            self.execute('UPDATE canon_facts SET content=?,lock_level=?,source=?,source_chapter=?,status=?,updated_at=? WHERE id=?', [content, lock_level, source, source_chapter, status, now_iso(), old['id']])
        else:
            self.execute('INSERT INTO canon_facts(category,name,content,lock_level,status,scope,source,source_chapter,updated_at) VALUES(?,?,?,?,?,?,?,?,?)', [category, name, content, lock_level, status, scope, source, source_chapter, now_iso()])
        self.conn.commit()

    def canon_fact(self, name, category=None, scope='canon'):
        if category:
            return self.one('SELECT * FROM canon_facts WHERE category=? AND name=? AND scope=?', [category, name, scope])
        return self.one('SELECT * FROM canon_facts WHERE name=? AND scope=? ORDER BY id DESC', [name, scope])

    def update_canon_fact(self, name, *, content=None, category=None, lock_level=None, scope='canon'):
        old = self.canon_fact(name, category, scope)
        if not old:
            raise ValueError(f'找不到 Canon 事实：{name}')
        self.execute(
            'UPDATE canon_facts SET category=?,content=?,lock_level=?,updated_at=? WHERE id=?',
            [old['category'] if category is None else category,
             old['content'] if content is None else content,
             old['lock_level'] if lock_level is None else lock_level,
             now_iso(), old['id']]
        )
        self.conn.commit()
    def delete_canon_fact(self, name, category=None, scope='canon'):
        r = self.canon_fact(name, category, scope)
        if not r:return 0
        cur=self.execute('DELETE FROM canon_facts WHERE id=?',[r['id']]);self.conn.commit();return cur.rowcount
    def canon_facts(self, scope='canon'): return self.query('SELECT * FROM canon_facts WHERE scope=? AND status=? ORDER BY category,name', [scope, 'active'])

    def promote_drafts(self):
        self.execute("UPDATE canon_facts SET scope='canon' WHERE scope='draft'")
        self.execute("UPDATE entities SET scope='canon' WHERE scope='draft'")
        self.execute("UPDATE relationships SET scope='canon' WHERE scope='draft'")
        self.execute("UPDATE events SET scope='canon' WHERE scope='draft'")
        self.execute("UPDATE foreshadows SET scope='canon' WHERE scope='draft'")
        self.conn.commit()

    def save_relationship(self, source, target, relation, strength=.5, note='', source_chapter=None, scope='dynamic'):
        self.execute('INSERT INTO relationships(source_name,target_name,relation,strength,note,scope,source_chapter,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(source_name,target_name,relation,scope) DO UPDATE SET strength=excluded.strength,note=excluded.note,source_chapter=excluded.source_chapter,updated_at=excluded.updated_at', [source, target, relation, strength, note, scope, source_chapter, now_iso()]); self.conn.commit()
    def relationships(self, scope=None): return self.query('SELECT * FROM relationships' + (' WHERE scope=?' if scope else '') + ' ORDER BY source_name,target_name', [scope] if scope else [])
    def save_event(self, title, description='', chapter_number=None, event_time='', importance=2, tags=None, source_chapter=None, scope='dynamic'):
        self.execute('INSERT INTO events(chapter_number,event_time,title,description,importance,tags,status,scope,source_chapter,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)', [chapter_number, event_time, title, description, importance, json.dumps(tags or [], ensure_ascii=False), 'active', scope, source_chapter, now_iso()]); self.conn.commit()
    def events(self, scope=None): return self.query('SELECT * FROM events' + (' WHERE scope=?' if scope else '') + ' ORDER BY chapter_number,id', [scope] if scope else [])
    def save_foreshadow(self, code, description, introduced_chapter=None, target_chapter=None, status='open', importance=2, notes='', lifecycle='introduced', last_touched_chapter=None, scope='canon'):
        self.execute('INSERT INTO foreshadows(code,description,introduced_chapter,target_chapter,status,importance,notes,lifecycle,last_touched_chapter,scope,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET description=excluded.description,target_chapter=COALESCE(excluded.target_chapter,foreshadows.target_chapter),status=excluded.status,importance=excluded.importance,notes=excluded.notes,lifecycle=excluded.lifecycle,last_touched_chapter=COALESCE(excluded.last_touched_chapter,foreshadows.last_touched_chapter),scope=excluded.scope,updated_at=excluded.updated_at', [code, description, introduced_chapter, target_chapter, status, importance, notes, lifecycle, last_touched_chapter, scope, now_iso()]); self.conn.commit()
    def foreshadows(self, status=None, scope=None):
        wh, p = [], []
        if status: wh.append('status=?'); p.append(status)
        if scope: wh.append('scope=?'); p.append(scope)
        return self.query('SELECT * FROM foreshadows' + (' WHERE ' + ' AND '.join(wh) if wh else '') + ' ORDER BY importance DESC,id', p)

    def save_summary(self, start, end, summary, level='chapter'):
        r = self.one('SELECT id FROM summaries WHERE range_start=? AND range_end=? AND level=?', [start, end, level]); ts = now_iso()
        if r:self.execute('UPDATE summaries SET summary=?,created_at=? WHERE id=?', [summary, ts, r['id']])
        else:self.execute('INSERT INTO summaries(range_start,range_end,summary,level,created_at) VALUES(?,?,?,?,?)', [start, end, summary, level, ts])
        self.conn.commit()
    def summaries(self): return self.query('SELECT * FROM summaries ORDER BY range_start')
    def save_state_update(self, n, payload, applied=True, revision=0): self.execute('INSERT INTO state_updates(chapter_number,payload,applied,revision,created_at) VALUES(?,?,?,?,?)', [n, json.dumps(payload, ensure_ascii=False), int(applied), revision, now_iso()]); self.conn.commit()
    def latest_state_updates(self, applied_only=True): return self.query('SELECT * FROM state_updates' + (' WHERE applied=1' if applied_only else '') + ' ORDER BY chapter_number,id')
    def save_proposal(self, n, payload, revision=0, reason='AI 状态提取'):
        self.execute("DELETE FROM state_proposals WHERE chapter_number=? AND status='pending'", [n]); self.conn.commit();cur=self.execute('INSERT INTO state_proposals(chapter_number,revision,payload,reason,status,created_at) VALUES(?,?,?,?,?,?)',[n,revision,json.dumps(payload,ensure_ascii=False),reason,'pending',now_iso()]);self.conn.commit();return cur.lastrowid
    def setting_proposals(self, chapter=None, status='pending'):
        wh,p=[],[]
        if chapter is not None:wh.append('chapter_number=?');p.append(chapter)
        if status is not None:wh.append('status=?');p.append(status)
        return self.query('SELECT * FROM setting_proposals'+(' WHERE '+' AND '.join(wh) if wh else '')+' ORDER BY id DESC',p)
    def save_setting_proposal(self,n,payload,revision=0,reason='AI设定提取'):
        self.execute("DELETE FROM setting_proposals WHERE chapter_number=? AND status='pending'",[n]);self.conn.commit();cur=self.execute('INSERT INTO setting_proposals(chapter_number,revision,payload,reason,status,created_at) VALUES(?,?,?,?,?,?)',[n,revision,json.dumps(payload,ensure_ascii=False),reason,'pending',now_iso()]);self.conn.commit();return cur.lastrowid
    def review_setting_proposal(self,pid,approved):self.execute('UPDATE setting_proposals SET status=?,reviewed_at=? WHERE id=?',["approved" if approved else "rejected",now_iso(),pid]);self.conn.commit()

    def proposals(self, chapter=None, status='pending'):
        wh,p=[],[]
        if chapter is not None:wh.append('chapter_number=?');p.append(chapter)
        if status is not None:wh.append('status=?');p.append(status)
        return self.query('SELECT * FROM state_proposals'+(' WHERE '+' AND '.join(wh) if wh else '')+' ORDER BY id DESC',p)
    def review_proposal(self,pid,approved):self.execute('UPDATE state_proposals SET status=?,reviewed_at=? WHERE id=?',["approved" if approved else "rejected",now_iso(),pid]);self.conn.commit()
    def knowledge(self,char=None):return self.query('SELECT * FROM character_knowledge'+(' WHERE character_name=?' if char else '')+' ORDER BY character_name,id',[char] if char else [])
    def save_knowledge(self,char,fact,knowledge_type='known',certainty='known',source_chapter=None,last_updated_chapter=None):self.execute('INSERT INTO character_knowledge(character_name,fact,knowledge_type,certainty,source_chapter,last_updated_chapter) VALUES(?,?,?,?,?,?) ON CONFLICT(character_name,fact) DO UPDATE SET knowledge_type=excluded.knowledge_type,certainty=excluded.certainty,last_updated_chapter=excluded.last_updated_chapter,status="active"',[char,fact,knowledge_type,certainty,source_chapter,last_updated_chapter]);self.conn.commit()
    def save_character_arc(self,x,chapter=None):
        n=x.get('character_name') or x.get('character')
        if not n:return
        self.execute('INSERT INTO character_arcs(character_name,stage,desire,fear,belief,conflict,transformation,next_stage,trigger_event,source_chapter,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(character_name) DO UPDATE SET stage=excluded.stage,desire=excluded.desire,fear=excluded.fear,belief=excluded.belief,conflict=excluded.conflict,transformation=excluded.transformation,next_stage=excluded.next_stage,trigger_event=excluded.trigger_event,source_chapter=excluded.source_chapter,updated_at=excluded.updated_at',[n,x.get('stage',''),x.get('desire',''),x.get('fear',''),x.get('belief',''),x.get('conflict',''),x.get('transformation',''),x.get('next_stage',''),x.get('trigger_event',''),chapter,now_iso()]);self.conn.commit()
    def character_arcs(self):return self.query('SELECT * FROM character_arcs ORDER BY character_name')

    def set_intent(self,scope_type,scope_key,title,content,priority=3,hard=False):self.execute('INSERT INTO author_intents(scope_type,scope_key,title,content,priority,hard,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(scope_type,scope_key,title) DO UPDATE SET content=excluded.content,priority=excluded.priority,hard=excluded.hard,updated_at=excluded.updated_at',[scope_type,scope_key,title,content,priority,int(hard),now_iso(),now_iso()]);self.conn.commit()
    def intents(self):return self.query("SELECT * FROM author_intents WHERE status='active' ORDER BY priority DESC,id")
    def save_snapshot(self,label,payload,chapter=None):self.execute('INSERT INTO snapshots(label,chapter_number,payload,created_at) VALUES(?,?,?,?)',[label,chapter,json.dumps(payload,ensure_ascii=False),now_iso()]);self.conn.commit()
    def snapshots(self):return self.query('SELECT * FROM snapshots ORDER BY id DESC')
    def clear_issues(self,n=None):self.execute('DELETE FROM audit_issues'+(' WHERE chapter_number=?' if n is not None else ''),[n] if n is not None else []);self.conn.commit()
    def save_issue(self,n,severity,typ,msg,location='',refs=None):self.execute('INSERT INTO audit_issues(chapter_number,severity,issue_type,message,location,references_json,created_at) VALUES(?,?,?,?,?,?,?)',[n,severity,typ,msg,location,json.dumps(refs or [],ensure_ascii=False),now_iso()]);self.conn.commit()
    def issues(self,unresolved_only=False):return self.query('SELECT * FROM audit_issues'+(' WHERE resolved=0' if unresolved_only else '')+' ORDER BY chapter_number DESC,id DESC')
    def resolve_issue(self,pid):self.execute('UPDATE audit_issues SET resolved=1 WHERE id=?',[pid]);self.conn.commit()

    def create_job(self,kind,n=None):cur=self.execute('INSERT INTO jobs(kind,status,chapter_number,progress,stage,detail,started_at) VALUES(?,?,?,?,?,?,?)',[kind,'running',n,0,'准备中','',now_iso()]);self.conn.commit();return cur.lastrowid
    def update_job(self,j,progress,stage,detail=''):self.execute('UPDATE jobs SET progress=?,stage=?,detail=? WHERE id=?',[int(progress),stage,detail,j]);self.conn.commit()
    def finish_job(self,j,status='done',error='',usage=None,result=None):self.execute('UPDATE jobs SET status=?,finished_at=?,error=?,usage_json=?,result_json=?,progress=? WHERE id=?',[status,now_iso(),error,json.dumps(usage or {},ensure_ascii=False),json.dumps(result or {},ensure_ascii=False),100 if status=='done' else 0,j]);self.conn.commit()
    def jobs(self,limit=80):return self.query('SELECT * FROM jobs ORDER BY id DESC LIMIT ?',[max(1,int(limit))])

    def save_style(self,payload,source_chapter=None):self.execute('INSERT INTO style_profiles(id,payload,source_chapter,updated_at) VALUES(1,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,source_chapter=excluded.source_chapter,updated_at=excluded.updated_at',[json.dumps(payload,ensure_ascii=False),source_chapter,now_iso()]);self.conn.commit()
    def style(self):
        r=self.one('SELECT payload FROM style_profiles WHERE id=1');return json.loads(r['payload']) if r else {}
    def branches(self):return self.query('SELECT * FROM branches ORDER BY id')
    def branch(self, branch_id):return self.one('SELECT * FROM branches WHERE id=?', [int(branch_id)])
    def active_branch_id(self):
        try:return int(self.get_meta('active_branch_id', 1) or 1)
        except Exception:return 1
    def active_branch(self):
        b=self.branch(self.active_branch_id());return b or self.branch(1)
    def save_branch(self,name,parent=1,base=1,description=''):
        # 先把当前所有章节的 revision 记为主线指针，作为分支的回退基线。
        for r in self.query('SELECT number,current_revision FROM chapters'):
            self.record_branch_chapter(1, int(r['number']), int(r['current_revision'] or 0))
        cur=self.execute('INSERT INTO branches(name,parent_branch_id,base_chapter,status,description,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',[name,parent,int(base),'draft',description,now_iso(),now_iso()]);self.conn.commit();return cur.lastrowid
    def delete_branch(self, branch_id):
        branch_id=int(branch_id)
        if branch_id==1:raise ValueError('主线分支不能删除。')
        if self.active_branch_id()==branch_id:raise ValueError('请先切换到其它分支再删除。')
        self.execute('DELETE FROM branch_chapters WHERE branch_id=?',[branch_id])
        self.execute('DELETE FROM branches WHERE id=?',[branch_id])
        self.conn.commit()
    def record_branch_chapter(self, branch_id, n, revision):
        self.execute('INSERT INTO branch_chapters(branch_id,chapter_number,source_revision,status) VALUES(?,?,?,?) ON CONFLICT(branch_id,chapter_number) DO UPDATE SET source_revision=excluded.source_revision,status="active"',[int(branch_id),int(n),int(revision),'active'])
        self.conn.commit()
    def branch_chapter(self, branch_id, n):return self.one('SELECT * FROM branch_chapters WHERE branch_id=? AND chapter_number=?',[int(branch_id),int(n)])
    def switch_branch(self, branch_id):
        target=self.branch(branch_id)
        if not target:raise ValueError(f'找不到分支：{branch_id}')
        cur=self.active_branch_id()
        # 把当前 chapters 表内容记回当前分支的指针。
        # 规则：主线指针缺失时补记（兼容旧项目）；非主线分支只记录与主线
        # 不一致的章节（说明该分支确实改动过），未改动的章节继续跟随主线。
        for r in self.query('SELECT number,current_revision FROM chapters'):
            n=int(r['number']); rev=int(r['current_revision'] or 0)
            mp=self.branch_chapter(1,n)
            mrev=int(mp['source_revision'] or 0) if mp else -1
            if cur==1:
                if mp is None:self.record_branch_chapter(1,n,rev)
            else:
                if rev!=mrev:self.record_branch_chapter(cur,n,rev)
        # 按目标分支的指针恢复各章内容；分支没有改动过的章节回退到主线指针。
        for r in self.query('SELECT * FROM chapters ORDER BY number'):
            n=int(r['number'])
            bc=self.branch_chapter(int(branch_id),n)
            if bc is None and int(branch_id)!=1:bc=self.branch_chapter(1,n)
            rev=None
            if bc is not None:
                rev=self.one('SELECT * FROM chapter_revisions WHERE chapter_number=? AND revision=?',[n,int(bc['source_revision'] or 0)])
            if rev is not None:
                self.execute('UPDATE chapters SET title=?,content=?,plan=?,status=?,current_revision=?,word_count=?,stale=0,pov_character=?,perspective=?,tense=?,updated_at=? WHERE number=?',[rev['title'],rev['content'],rev['plan'] or '',rev['status'] or 'draft',int(rev['revision']),len(''.join((rev['content'] or '').split())),rev['pov_character'] or '',rev['perspective'] or 'third_limited',rev['tense'] or 'past',now_iso(),n])
            else:
                # 目标分支下该章没有正文（从未保存过）：恢复为计划态空章，
                # 避免其它分支新建/改写的章节内容泄漏到当前分支。
                self.execute('UPDATE chapters SET title=?,content=?,plan=?,status=?,current_revision=?,word_count=?,stale=0,pov_character=?,perspective=?,tense=?,updated_at=? WHERE number=?',[f'第{n}章','','','planned',0,0,'','third_limited','past',now_iso(),n])
        self.conn.commit()
        self.set_meta('active_branch_id', int(branch_id))
        return target

    def search(self, query: str, limit=30):
        q = (query or '').strip()
        if not q:return []
        like = f'%{q}%'
        results=[]
        for r in self.query('SELECT number,title,plan,content,status,stale FROM chapters WHERE title LIKE ? OR plan LIKE ? OR content LIKE ? ORDER BY number LIMIT ?', [like,like,like,max(1,int(limit))]):
            hay=' '.join([r['title'] or '',r['plan'] or '',r['content'] or ''])
            idx=hay.lower().find(q.lower())
            start=max(0,idx-100) if idx>=0 else 0
            results.append({'type':'chapter','chapter':int(r['number']),'title':r['title'],'status':r['status'],'stale':int(r['stale'] or 0),'snippet':hay[start:start+360]})
        for r in self.query('SELECT category,name,content,lock_level,scope FROM canon_facts WHERE name LIKE ? OR content LIKE ? ORDER BY id LIMIT ?', [like,like,max(1,int(limit))]):
            results.append({'type':'canon','name':r['name'],'category':r['category'],'scope':r['scope'],'lock_level':r['lock_level'],'snippet':(r['content'] or '')[:360]})
        for r in self.query('SELECT kind,name,description,data,scope FROM entities WHERE name LIKE ? OR description LIKE ? OR data LIKE ? ORDER BY kind,name LIMIT ?', [like,like,like,max(1,int(limit))]):
            results.append({'type':'entity','kind':r['kind'],'name':r['name'],'scope':r['scope'],'snippet':(r['description'] or '')[:360],'data':json.loads(r['data'] or '{}')})
        return results[:max(1,int(limit))]

    def search_chapters(self, query: str, limit=30):return [x for x in self.search(query,limit) if x['type']=='chapter']

    def save_log(self,level,event,message,detail=''):
        self.execute('INSERT INTO logs(level,event,message,detail,created_at) VALUES(?,?,?,?,?)',[level,event,message,detail,now_iso()]);self.conn.commit()
    def logs(self,limit=200):return self.query('SELECT * FROM logs ORDER BY id DESC LIMIT ?',[max(1,int(limit))])

    def volumes(self):return self.query('SELECT * FROM volumes ORDER BY number')
    def save_volume(self,number,title=None,synopsis=None):
        r=self.one('SELECT * FROM volumes WHERE number=?',[int(number)])
        if not r:raise ValueError(f'找不到第 {number} 卷。')
        self.execute('UPDATE volumes SET title=?,synopsis=?,updated_at=? WHERE number=?',[r['title'] if title is None else title,r['synopsis'] if synopsis is None else synopsis,now_iso(),int(number)]);self.conn.commit()
    def delete_intent(self,pid):self.execute('DELETE FROM author_intents WHERE id=?',[int(pid)]);self.conn.commit()

    def full_state(self):
        q=lambda sql:[dict(x) for x in self.query(sql)]
        return {
            'meta': {r['key']:r['value'] for r in self.query('SELECT key,value FROM meta')},
            'chapters': q('SELECT * FROM chapters ORDER BY number'),
            'canon_facts': q('SELECT * FROM canon_facts ORDER BY category,name'),
            'entities': q('SELECT * FROM entities ORDER BY scope,kind,name'),
            'relationships': q('SELECT * FROM relationships ORDER BY id'),
            'events': q('SELECT * FROM events ORDER BY chapter_number,id'),
            'foreshadows': q('SELECT * FROM foreshadows ORDER BY id'),
            'summaries': q('SELECT * FROM summaries ORDER BY range_start'),
            'knowledge': q('SELECT * FROM character_knowledge ORDER BY character_name,id'),
            'arcs': q('SELECT * FROM character_arcs ORDER BY character_name'),
            'intents': q('SELECT * FROM author_intents ORDER BY id'),
            'style': self.style(),
        }
