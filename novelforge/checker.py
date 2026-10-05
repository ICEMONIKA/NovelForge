from __future__ import annotations
import re
class Checker:
    def __init__(self,db):self.db=db
    @staticmethod
    def _strip_dialogue(text):
        # 引号内的第一人称属于对白，不代表叙述视角，先剔除再检查。
        t=re.sub(r'“[^”]*”','',text or '')
        t=re.sub(r'"[^"]*"','',t)
        t=re.sub(r'「[^」]*」','',t)
        return t
    def local(self,n,text):
        out=[];r=self.db.chapter(n)
        if r and r['pov_character'] and len(text or '')>0 and r['perspective']=='third_limited':
            narration=self._strip_dialogue(text)
            hits=len(re.findall(r'我',narration))
            if hits>=3:out.append(('low','possible_pov_leak',f'第三人称限知章节的叙述部分出现 {hits} 处第一人称“我”，请检查是否为叙述越界。','全文'))
        for f in self.db.foreshadows('open'):
            if f['target_chapter'] and int(f['target_chapter'])<n:out.append(('low','foreshadow_overdue',f"伏笔 {f['code']} 已超过目标章节 {f['target_chapter']}。",'伏笔'))
        grams=re.findall(r'[\u4e00-\u9fff]{5,}',text or '');freq={x:grams.count(x) for x in set(grams)}
        for x,c in sorted(freq.items(),key=lambda kv:-kv[1])[:5]:
            if c>=8:out.append(('low','repetition',f'短语“{x}”出现 {c} 次。','全文'))
        return out
    def save_local(self,n,text):
        self.db.clear_issues(n)
        for sev,t,msg,loc in self.local(n,text):self.db.save_issue(n,sev,t,msg,loc)
