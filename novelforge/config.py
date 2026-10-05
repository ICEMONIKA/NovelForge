from __future__ import annotations
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

APP_NAME='NovelForge 2.4'
APP_VERSION='2.4.0'
CONFIG_PATH=Path.home()/'.novelforge'/'config.json'

@dataclass
class AppConfig:
    api_key:str=''
    base_url:str='https://api.deepseek.com'
    model:str='deepseek-flash'
    thinking:bool=True
    reasoning_effort:str='high'
    temperature:float=.75
    top_p:float=1.0
    max_tokens:int=24000
    review_count:int=1
    context_char_budget:int=140000
    recent_chapter_char_budget:int=60000
    summary_char_budget:int=36000
    auto_audit:bool=True
    auto_extract:bool=True
    auto_summary:bool=True
    auto_backup:bool=True
    auto_save_seconds:int=8
    retry_times:int=3
    timeout_seconds:int=180
    strict_fact_check:bool=True
    health_check_after_confirm:bool=True
    notify_sound:bool=True
    notify_system:bool=True
    notify_volume:float=.7
    last_project:str=''

    @classmethod
    def load(cls):
        try:
            data=json.loads(CONFIG_PATH.read_text('utf-8')) if CONFIG_PATH.exists() else {}
            base=asdict(cls());base.update({k:v for k,v in data.items() if k in base})
            c=cls(**base);c.review_count=max(1,int(c.review_count));return c
        except Exception:return cls()

    def save(self):
        CONFIG_PATH.parent.mkdir(parents=True,exist_ok=True);tmp=CONFIG_PATH.with_suffix('.tmp')
        tmp.write_text(json.dumps(asdict(self),ensure_ascii=False,indent=2),'utf-8');os.replace(tmp,CONFIG_PATH)
