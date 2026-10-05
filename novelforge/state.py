from __future__ import annotations

import json


class StateManager:
    def __init__(self, db): self.db = db
    def propose(self, n, payload, revision=0, reason='AI 状态提取'): return self.db.save_proposal(n, payload, revision, reason)

    def approve(self, pid):
        r=self.db.one("SELECT * FROM state_proposals WHERE id=? AND status='pending'",[pid])
        if not r:return False
        self.apply(int(r['chapter_number']),json.loads(r['payload']),int(r['revision'] or 0));self.db.review_proposal(pid,True);return True

    def reject(self,pid):
        r=self.db.one("SELECT id FROM state_proposals WHERE id=? AND status='pending'",[pid])
        if not r:return False
        self.db.review_proposal(pid,False);return True

    def apply(self,n,p,revision=0):
        for e in p.get('entities',[]) or []:
            if isinstance(e,dict) and e.get('name'):self.db.save_entity(e.get('kind','other'),e['name'],e.get('description',''),e.get('data',{}),e.get('aliases',[]),n,'dynamic')
        for r in p.get('relationships',[]) or []:
            if isinstance(r,dict) and r.get('source') and r.get('target'):self.db.save_relationship(r['source'],r['target'],r.get('relation','unknown'),float(r.get('strength',.5)),r.get('note',''),n,'dynamic')
        for e in p.get('events',[]) or []:
            if isinstance(e,dict) and e.get('title'):self.db.save_event(e['title'],e.get('description',''),e.get('chapter',n),e.get('time',''),int(e.get('importance',2)),e.get('tags',[]),n,'dynamic')
        for k in p.get('character_knowledge',[]) or []:
            if isinstance(k,dict) and k.get('character') and k.get('fact'):self.db.save_knowledge(k['character'],k['fact'],k.get('knowledge_type','known'),k.get('certainty','known'),n,n)
        for a in p.get('character_arcs',[]) or []:
            if isinstance(a,dict):self.db.save_character_arc(a,n)
        for f in p.get('foreshadowing_created',[]) or []:
            if isinstance(f,dict) and f.get('code'):self.db.save_foreshadow(f['code'],f.get('description',''),n,f.get('target_chapter'),f.get('status','open'),int(f.get('importance',2)),f.get('notes',''),'introduced',n,'dynamic')
        for f in p.get('foreshadowing_touched',[]) or []:
            if isinstance(f,dict) and f.get('code'):
                old=self.db.one('SELECT * FROM foreshadows WHERE code=?',[f['code']])
                if old:self.db.save_foreshadow(f['code'],old['description'],old['introduced_chapter'],old['target_chapter'],f.get('status',old['status']),old['importance'],f.get('notes',old['notes']),'touched',n,'dynamic')
        for f in p.get('foreshadowing_resolved',[]) or []:
            if isinstance(f,dict) and f.get('code'):
                old=self.db.one('SELECT * FROM foreshadows WHERE code=?',[f['code']])
                if old:self.db.save_foreshadow(f['code'],old['description'],old['introduced_chapter'],old['target_chapter'],'resolved',old['importance'],f.get('notes',old['notes']),'resolved',n,'dynamic')
        self.db.save_state_update(n,p,True,revision)

    def rebuild(self,last=None):
        updates={int(r['chapter_number']):json.loads(r['payload']) for r in self.db.latest_state_updates(True) if last is None or int(r['chapter_number'])<=int(last)}
        self.db.execute("DELETE FROM relationships WHERE scope='dynamic'")
        self.db.execute("DELETE FROM events WHERE scope='dynamic'")
        self.db.execute("DELETE FROM entities WHERE scope='dynamic'")
        self.db.execute("DELETE FROM foreshadows WHERE scope='dynamic'")
        self.db.execute('DELETE FROM character_knowledge')
        self.db.execute('DELETE FROM character_arcs')
        self.db.conn.commit()
        for n,p in sorted(updates.items()): self.apply(n,p)
        return {'updates':len(updates),'events':len(self.db.events('dynamic')),'foreshadows':len(self.db.foreshadows(scope='dynamic'))}
