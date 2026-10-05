from __future__ import annotations

import json


class ContextEngine:
    def __init__(self, db, cfg):
        self.db = db
        self.cfg = cfg

    @staticmethod
    def clip(x, n):
        x = str(x or '')
        return x if len(x) <= n else x[:max(0, n - 80)] + '\n…【截断】…'

    def pack(self, chapter: int, include_project_raw=False):
        review_count = max(1, int(self.cfg.review_count))
        recent = [dict(r) for r in reversed(self.db.recent_chapters(chapter, review_count))]
        state = {
            'canon_facts': [dict(r) for r in self.db.canon_facts('canon')],
            'entities': [dict(r) for r in self.db.entities(scope='canon')],
            'relationships': [dict(r) for r in self.db.relationships('dynamic') + self.db.relationships('canon')],
            'events': [dict(r) for r in self.db.events('dynamic') + self.db.events('canon')],
            'foreshadows': [dict(r) for r in self.db.foreshadows('open', 'canon')] + [dict(r) for r in self.db.foreshadows('open', 'dynamic')],
            'knowledge': [dict(r) for r in self.db.knowledge()],
            'arcs': [dict(r) for r in self.db.character_arcs()],
        }
        meta = {k: self.db.get_meta(k, '') for k in ['title', 'subtitle', 'synopsis', 'canon', 'outline', 'style', 'author']}
        if include_project_raw:
            meta['raw_material'] = self.db.get_meta('raw_material', '')
        row = self.db.chapter(chapter)
        summaries = [dict(r) for r in self.db.summaries() if int(r['range_end']) < chapter]
        intents = [dict(r) for r in self.db.intents()]
        parts = []
        budget = max(20000, int(self.cfg.context_char_budget))

        def add(label, obj, limit):
            raw = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=2)
            raw = self.clip(raw, limit)
            parts.append(f'【{label}】\n{raw}')

        add('项目', meta, 14000)
        add('Hard Canon', state['canon_facts'], 22000)
        add('人物/地点/势力/物品等 Canon', state['entities'], 22000)
        add('关系与事件', {'relationships': state['relationships'], 'events': state['events']}, 22000)
        add('人物认知与人物弧线', {'knowledge': state['knowledge'], 'arcs': state['arcs']}, 18000)
        add('未回收伏笔', state['foreshadows'], 14000)
        add('作者意图', intents, 10000)
        add('中长期摘要', summaries, int(self.cfg.summary_char_budget))
        add(f'最近至少 {review_count} 章已确认原文', recent, int(self.cfg.recent_chapter_char_budget))
        add('当前章节记录', dict(row) if row else {}, 10000)
        return self.clip('\n\n'.join(parts), budget)

    def compact_project_index(self, limit=12000):
        data = {
            'title': self.db.get_meta('title', ''),
            'initialization_status': self.db.get_meta('initialization_status', 'pending'),
            'chapters': [{'number': r['number'], 'title': r['title'], 'status': r['status'], 'stale': r['stale']} for r in self.db.chapters()],
            'canon_facts': len(self.db.canon_facts('canon')),
            'entities': len(self.db.entities(scope='canon')),
            'events': len(self.db.events()),
            'foreshadows_open': len(self.db.foreshadows('open')),
            'pending_proposals': len(self.db.proposals()),
            'issues': len(self.db.issues(True)),
        }
        return self.clip(json.dumps(data, ensure_ascii=False, indent=2), limit)
