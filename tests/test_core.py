from pathlib import Path
import json
import zipfile
from dataclasses import asdict

from novelforge.project import Project, restore_full_state
from novelforge.manager import OperationEngine
from novelforge.context import ContextEngine
from novelforge.config import AppConfig
from novelforge.api import DeepSeekClient
from novelforge.exporter import export_epub, export_txt, export_md, export_json
from novelforge.state import StateManager
from novelforge.prompts import DEFAULT_PROMPTS, PromptBuilder
from novelforge.checker import Checker


def test_project_creation_and_draft_population(tmp_path):
    p=Project.create(tmp_path/'p','测试小说',4,2,'自然语言资料','作者');d=p.db
    payload={'operations':[
        {'op':'create_canon_fact','target':'世界规则','fields':{'category':'规则','name':'世界规则','content':'规则A','lock_level':'hard'},'reason':'初始化','confidence':1},
        {'op':'create_entity','target':'主角','fields':{'kind':'character','name':'主角','description':'34岁','data':{'age':34}},'reason':'初始化','confidence':1},
        {'op':'create_event','target':'建国','fields':{'title':'建国','description':'国家成立','chapter_number':1,'event_time':'第1年'},'reason':'初始化','confidence':1},
        {'op':'create_foreshadow','target':'F001','fields':{'code':'F001','description':'神秘戒指','target_chapter':10},'reason':'初始化','confidence':1}
    ]}
    result=OperationEngine(d).apply(payload,'draft');assert len(result)==4
    assert len(d.canon_facts('draft'))==1 and len(d.entities(scope='draft'))==1 and len(d.events('draft'))==1 and d.foreshadows(scope='draft')[0]['code']=='F001'
    d.promote_drafts();assert len(d.canon_facts('canon'))==1 and len(d.entities(scope='canon'))==1 and len(d.events('canon'))==1 and d.foreshadows(scope='canon')[0]['code']=='F001'


def test_real_mutation_updates_entity_and_original_text(tmp_path):
    p=Project.create(tmp_path/'p','X',3,1,'','');d=p.db
    d.save_entity('character','角色A','',{'level':80});d.save_chapter(1,'第一章','角色A目前只有80级。\n\n战斗失败。','','confirmed','test')
    result=OperationEngine(d).apply({'operations':[
        {'op':'update_entity','target':'角色A','fields':{'kind':'character','name':'角色A','data':{'level':100}},'reason':'修正战力 Canon','confidence':1},
        {'op':'replace_text','target':'1','fields':{'chapter_number':1,'old_text':'角色A目前只有80级。','new_text':'角色A目前已经达到100级。'},'reason':'修复与新 Canon 冲突','confidence':1},
    ]},'canon')
    assert len(result)==2 and json.loads(d.entity('character','角色A')['data'])['level']==100
    assert '100级' in d.chapter(1)['content'] and d.chapter(1)['status']=='draft' and d.chapter(1)['current_revision']==2
    assert len(d.revisions(1))==2


def test_context_pack_without_scenes(tmp_path):
    p=Project.create(tmp_path/'p','X',3,1,'','');d=p.db
    d.save_canon_fact('规则','规则A','内容A','hard','user')
    d.save_chapter(1,'第一章','正文','','confirmed','test')
    text=ContextEngine(d,AppConfig()).pack(2)
    assert 'Hard Canon' in text and '规则A' in text
    assert 'Scene' not in text


def test_setting_extract_prompt_exists_and_classifies_long_term_settings():
    assert '长期设定' in DEFAULT_PROMPTS['setting_extract'] and '剧情状态' in DEFAULT_PROMPTS['setting_extract'] and 'conflict' in DEFAULT_PROMPTS['setting_extract']


def test_rewrite_prompts_keep_modes_separate():
    assert '整章' in DEFAULT_PROMPTS['rewrite_full'] and '完整新正文' in DEFAULT_PROMPTS['rewrite_full']
    assert '选中' in DEFAULT_PROMPTS['rewrite_local'] and '只修改' in DEFAULT_PROMPTS['rewrite_local']


def test_api_thinking_payload_matches_current_config_contract():
    c=AppConfig(); body=DeepSeekClient(c).request_kwargs('s','u',True)
    assert body['model']=='deepseek-flash' and body['reasoning_effort']=='high' and body['extra_body']=={'thinking':{'type':'enabled'}} and 'temperature' not in body


def test_state_rebuild_clears_dynamic_foreshadows(tmp_path):
    p=Project.create(tmp_path/'p','X',3,1,'','');db=p.db
    StateManager(db).apply(1,{'foreshadowing_created':[{'code':'F1','description':'A','target_chapter':3}]});assert len(db.foreshadows(scope='dynamic'))==1
    db.execute('DELETE FROM state_updates WHERE chapter_number=1');db.conn.commit();StateManager(db).rebuild();assert len(db.foreshadows(scope='dynamic'))==0


def test_epub_cover_and_exports(tmp_path):
    p=Project.create(tmp_path/'p','电子书',2,1,'','作者');db=p.db;db.save_chapter(1,'第一章','段落一\n\n段落二','','confirmed','test');db.save_chapter(2,'第二章','段落三','','draft','test')
    ep=tmp_path/'a.epub';tx=tmp_path/'a.txt';md=tmp_path/'a.md';js=tmp_path/'a.json';cover=tmp_path/'cover.jpg';cover.write_bytes(b'\xff\xd8\xff\xd9')
    export_epub(db,ep,confirmed_only=True,cover=cover);export_txt(db,tx);export_md(db,md);export_json(db,js)
    with zipfile.ZipFile(ep) as z:
        assert z.namelist()[0]=='mimetype' and z.getinfo('mimetype').compress_type==zipfile.ZIP_STORED and 'OEBPS/chapter_0001.xhtml' in z.namelist() and 'OEBPS/chapter_0002.xhtml' not in z.namelist() and 'OEBPS/cover.jpg' in z.namelist()
        assert 'href="cover.jpg"' in z.read('OEBPS/content.opf').decode('utf-8')
    assert '第二章' in tx.read_text('utf-8') and '# 电子书' in md.read_text('utf-8') and json.loads(js.read_text('utf-8'))['meta']['title']=='电子书'


def test_manual_canon_setting_crud(tmp_path):
    p=Project.create(tmp_path/'p','X',1,1,'',''); d=p.db
    d.save_canon_fact('世界规则','魔法阶位','一共有十阶','hard','user')
    assert d.canon_fact('魔法阶位','世界规则')['content']=='一共有十阶'
    d.update_canon_fact('魔法阶位',content='一共有十二阶',category='世界规则',lock_level='hard')
    assert d.canon_fact('魔法阶位','世界规则')['content']=='一共有十二阶'
    assert d.delete_canon_fact('魔法阶位','世界规则')==1
    assert d.canon_fact('魔法阶位','世界规则') is None


def test_assistant_can_return_setting_candidates_without_claiming_direct_write():
    from novelforge.prompts import DEFAULT_PROMPTS
    prompt=DEFAULT_PROMPTS['assistant']
    assert '应用 AI 设定' in prompt
    assert '不能直接修改正文' in prompt
    assert 'settings' in prompt


def test_config_has_last_project_field():
    c=AppConfig(); assert c.last_project==''
    c.last_project=r'D:\novel\proj'
    assert asdict(c)['last_project']==r'D:\novel\proj'


def test_save_log_and_read(tmp_path):
    p=Project.create(tmp_path/'p','X',1,1,'',''); d=p.db
    d.save_log('info','open_project','项目已打开','/tmp/x')
    rows=d.logs(); assert rows and rows[0]['event']=='open_project' and rows[0]['level']=='info'


def test_volume_rename_and_intent_delete(tmp_path):
    p=Project.create(tmp_path/'p','X',1,2,'',''); d=p.db
    d.save_volume(1,title='第一卷·风起')
    assert d.volumes()[0]['title']=='第一卷·风起'
    d.set_intent('project','global','意图A','内容',3,False)
    assert len(d.intents())==1
    d.delete_intent(int(d.intents()[0]['id']))
    assert len(d.intents())==0


def test_search_finds_chapter_and_canon(tmp_path):
    p=Project.create(tmp_path/'p','X',2,1,'',''); d=p.db
    d.save_chapter(1,'第一章','主角进入王都。','','confirmed','test')
    d.save_canon_fact('规则','王都','王都是大陆中心。','normal','user')
    res=d.search('王都')
    assert any(x['type']=='chapter' for x in res) and any(x['type']=='canon' for x in res)


def test_branch_switch_isolates_content(tmp_path):
    p=Project.create(tmp_path/'p','X',3,1,'',''); d=p.db
    d.save_chapter(1,'第一章','主线内容A','','confirmed','test')
    bid=d.save_branch('支线B',1,1,'尝试支线')
    d.switch_branch(bid)
    assert d.chapter(1)['content']=='主线内容A'
    d.save_chapter(1,'第一章','支线内容B','','draft','user')
    d.switch_branch(1)
    assert d.chapter(1)['content']=='主线内容A' and d.chapter(1)['status']=='confirmed'
    d.switch_branch(bid)
    assert d.chapter(1)['content']=='支线内容B'
    d.switch_branch(1)
    d.delete_branch(bid)
    assert d.branch(bid) is None


def test_branch_new_chapter_not_leaked_to_main(tmp_path):
    p=Project.create(tmp_path/'p','X',3,1,'',''); d=p.db
    d.save_chapter(1,'第一章','主线A','','confirmed','test')
    bid=d.save_branch('支线',1,1,'')
    d.switch_branch(bid)
    d.save_chapter(2,'第二章','支线新内容','','draft','user')
    d.switch_branch(1)
    assert (d.chapter(2)['content'] or '')=='' and d.chapter(2)['status']=='planned'
    d.switch_branch(bid)
    assert d.chapter(2)['content']=='支线新内容'


def test_snapshot_restore(tmp_path):
    p=Project.create(tmp_path/'p','X',2,1,'',''); d=p.db
    d.save_chapter(1,'第一章','原文','','confirmed','test')
    d.save_canon_fact('规则','规则A','内容A','hard','user')
    d.save_snapshot('基准',d.full_state(),0)
    d.save_chapter(1,'第一章','改坏了','','draft','test')
    d.delete_canon_fact('规则A','规则')
    restore_full_state(d,json.loads(d.snapshots()[0]['payload']))
    assert d.chapter(1)['content']=='原文' and d.chapter(1)['status']=='confirmed'
    assert d.canon_fact('规则A','规则') is not None


def test_checker_ignores_dialogue_first_person(tmp_path):
    p=Project.create(tmp_path/'p','X',1,1,'',''); d=p.db
    d.save_chapter(1,'第一章','他说：“我知道了。”众人散去。','','draft','test',pov='主角',perspective='third_limited',tense='past')
    issues=Checker(d).local(1,d.chapter(1)['content'])
    assert not any(x[1]=='possible_pov_leak' for x in issues)
    d.save_chapter(1,'第一章','我走进房间，我坐下，我看着窗外。','','draft','test',pov='主角')
    issues=Checker(d).local(1,d.chapter(1)['content'])
    assert any(x[1]=='possible_pov_leak' for x in issues)


def test_revision_snapshot_keeps_plan_and_status(tmp_path):
    p=Project.create(tmp_path/'p','X',2,1,'',''); d=p.db
    d.save_chapter(1,'第一章','正文','本章计划内容','confirmed','test',pov='主角')
    rev=d.revisions(1)[0]
    assert rev['plan']=='本章计划内容' and rev['status']=='confirmed' and rev['pov_character']=='主角'
