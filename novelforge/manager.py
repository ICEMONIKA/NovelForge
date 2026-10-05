from __future__ import annotations
from typing import Any

class OperationEngine:
    """仅处理用户确认后的结构化写入；AI 本身不直接拥有数据库写权限。"""
    ALLOWED={'set_meta','create_canon_fact','update_canon_fact','delete_canon_fact','create_entity','update_entity','delete_entity','create_relationship','create_event','create_foreshadow','set_intent','set_style','replace_text','mark_stale','create_snapshot'}
    DESTRUCTIVE={'delete_canon_fact','delete_entity'}
    def __init__(self,db):self.db=db
    def validate(self,payload):
        errs=[]
        ops=payload.get('operations') or []
        if not isinstance(ops,list):return ['operations 必须是数组']
        for i,o in enumerate(ops,1):
            if not isinstance(o,dict):errs.append(f'第{i}项必须是对象');continue
            if o.get('op') not in self.ALLOWED:errs.append(f'第{i}项操作不被允许：{o.get("op")}')
            if not isinstance(o.get('fields',{}),dict):errs.append(f'第{i}项 fields 必须是对象')
        return errs
    @staticmethod
    def preview(payload):
        lines=[]
        for i,o in enumerate(payload.get('operations') or [],1):
            f=o.get('fields') or {}; target=o.get('target') or f.get('name') or f.get('title') or f.get('code') or f.get('key') or ''
            lines.append(f'{i}. {o.get("op")} → {target}\n   原因：{o.get("reason","")}\n   置信度：{o.get("confidence","")}')
        if payload.get('conflicts'):lines.append('\n⚠ 冲突\n'+'\n'.join('· '+str(x.get('message',x)) for x in payload['conflicts']))
        if payload.get('questions'):lines.append('\n需要确认\n'+'\n'.join('· '+str(x.get('question',x)) for x in payload['questions']))
        return '\n'.join(lines) or '没有结构化修改。'
    def apply(self,payload,scope='canon',allow_destructive=False):
        errs=self.validate(payload)
        if errs:raise ValueError('\n'.join(errs))
        result=[]
        for o in payload.get('operations') or []:
            op=o['op']; f=o.get('fields') or {}; target=o.get('target','')
            if op in self.DESTRUCTIVE and not allow_destructive:raise PermissionError(f'高风险操作 {op} 需要人工确认。')
            if op=='set_meta':self.db.set_meta(target or f.get('key',''),f.get('value',''))
            elif op=='create_canon_fact':self.db.save_canon_fact(f.get('category','其他'),f.get('name') or target,f.get('content',''),f.get('lock_level','normal'),f.get('source','ai'),f.get('source_chapter'),scope,'active')
            elif op=='update_canon_fact':self.db.update_canon_fact(f.get('name') or target,content=f.get('content'),category=f.get('category'),lock_level=f.get('lock_level'),scope=scope)
            elif op=='delete_canon_fact':self.db.delete_canon_fact(f.get('name') or target,f.get('category'),scope)
            elif op=='create_entity':self.db.save_entity(f.get('kind','other'),f.get('name') or target,f.get('description',''),f.get('data',{}),f.get('aliases',[]),f.get('source_chapter'),scope)
            elif op=='update_entity':self.db.update_entity(f.get('kind','other'),f.get('name') or target,new_name=f.get('new_name'),description=f.get('description'),data=f.get('data'),aliases=f.get('aliases'),scope=scope,merge_data=bool(f.get('merge_data',True)))
            elif op=='delete_entity':self.db.delete_entity(f.get('kind','other'),f.get('name') or target,scope)
            elif op=='create_relationship':self.db.save_relationship(f.get('source',''),f.get('target',''),f.get('relation','unknown'),float(f.get('strength',.5)),f.get('note',''),f.get('source_chapter'),scope)
            elif op=='create_event':self.db.save_event(f.get('title') or target,f.get('description',''),f.get('chapter_number'),f.get('event_time',''),int(f.get('importance',2)),f.get('tags',[]),f.get('source_chapter'),scope)
            elif op=='create_foreshadow':self.db.save_foreshadow(f.get('code') or target,f.get('description',''),f.get('introduced_chapter'),f.get('target_chapter'),f.get('status','open'),int(f.get('importance',2)),f.get('notes',''),f.get('lifecycle','introduced'),f.get('last_touched_chapter'),scope)
            elif op=='set_intent':self.db.set_intent(f.get('scope_type','project'),f.get('scope_key','global'),f.get('title') or target,f.get('content',''),int(f.get('priority',3)),bool(f.get('hard',False)))
            elif op=='set_style':self.db.save_style(f)
            elif op=='replace_text':
                n=int(f.get('chapter_number') or target);row=self.db.chapter(n);old=f.get('old_text','');new=f.get('new_text','')
                if not row:raise ValueError(f'找不到章节：{n}')
                if not old or row['content'].count(old)!=1:raise ValueError(f'第{n}章中的目标文本不是唯一匹配，已拒绝修改。')
                self.db.save_chapter(n,row['title'],row['content'].replace(old,new,1),row['plan'],'draft','ai','AI局部替换',pov=row['pov_character'],perspective=row['perspective'],tense=row['tense']);self.db.mark_stale_after(n)
            elif op=='mark_stale':self.db.mark_stale_after(int(f.get('chapter_number') or target))
            elif op=='create_snapshot':self.db.save_snapshot(f.get('label') or target or '快照',self.db.full_state(),f.get('chapter_number'))
            result.append({'op':op,'target':target or f.get('name') or f.get('chapter_number')})
        if result:self.db.save_snapshot('用户确认 AI 修改',self.db.full_state(),0)
        return result
