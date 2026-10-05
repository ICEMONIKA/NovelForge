from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, QThread, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QProgressBar,
    QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
    QSpinBox, QDoubleSpinBox, QAbstractItemView
)

from .api import DeepSeekClient
from .checker import Checker
from .config import APP_NAME, APP_VERSION, AppConfig
from .context import ContextEngine
from .database import now_iso
from .exporter import export_epub, export_json, export_md, export_txt
from .manager import OperationEngine
from .notification import NotificationManager
from .project import Project, restore_full_state
from .prompts import DEFAULT_PROMPTS, PromptBuilder
from .state import StateManager


STYLE = '''
QMainWindow,QWidget{background:#0b1118;color:#e9f0f7}
QFrame#Sidebar{background:#081019;border-right:1px solid #223243}
QLabel#Brand{font-size:24px;font-weight:800;padding:8px 10px 0}
QLabel#Version,QLabel#Subtle{color:#778ba0;padding:0 10px 12px}
QLabel#Project{color:#c7d4e1;padding:0 10px 16px}
QLabel#Title{font-size:27px;font-weight:800}
QLabel#BigPercent{font-size:30px;font-weight:900;color:#6cf2ff}
QPushButton{background:#151f2b;border:1px solid #2b3c4e;border-radius:9px;padding:8px 13px}
QPushButton:hover{background:#1d2a39;border-color:#4a637d}
QPushButton#Nav{background:transparent;border:none;text-align:left;color:#9eb0c3;padding:11px 13px}
QPushButton#Nav:hover{background:#14202d;color:#f5fbff}
QPushButton#NavActive{background:#123641;border:1px solid #1e96aa;color:#f0ffff;text-align:left;padding:11px 13px}
QPushButton#Primary{background:#17c1db;border:none;color:#041116;font-weight:900}
QPushButton#Primary:hover{background:#37d0e6}
QPushButton#Accent{background:#7f63ff;border:none;color:white;font-weight:900}
QPushButton#Danger{background:#431d2a;border-color:#7b3c4c;color:#ffe3e9}
QLineEdit,QTextEdit,QPlainTextEdit,QComboBox,QSpinBox,QDoubleSpinBox{background:#101a25;border:1px solid #2b3b4d;border-radius:9px;padding:8px;selection-background-color:#177f93}
QLineEdit:focus,QTextEdit:focus,QPlainTextEdit:focus,QComboBox:focus,QSpinBox:focus,QDoubleSpinBox:focus{background:#14212e;border-color:#31c8dc}
QPlainTextEdit#ManagerInput{background:#121f2c;border:1px solid #20c7dd;border-radius:14px;padding:14px;font-size:15px}
QPlainTextEdit#Editor{background:#101923;border:1px solid #2a3a4b;border-radius:12px;font-size:15px;padding:15px}
QListWidget,QTableWidget{background:#0e1721;border:1px solid #243343;border-radius:9px}
QListWidget::item{padding:9px;border-radius:7px}
QListWidget::item:selected{background:#123a49;color:white}
QHeaderView::section{background:#16212c;border:none;padding:8px;color:#9fb1c4}
QTabWidget::pane{border:1px solid #263647;border-radius:9px}
QTabBar::tab{background:#111a24;padding:8px 14px}
QTabBar::tab:selected{background:#1c2a38;color:#effcff}
QFrame#ManagerCard,QFrame#TaskCard{background:#0f1a25;border:1px solid #1b7788;border-radius:15px}
QFrame#Card{background:#111b26;border:1px solid #253445;border-radius:12px}
QProgressBar{border:1px solid #2d4355;border-radius:9px;background:#0b131c;text-align:center;height:24px;font-weight:900}
QProgressBar::chunk{background:#18c6de;border-radius:8px}
QStatusBar{background:#081019;color:#7e94aa}
'''


HELP = {
    '快速开始': '新建项目 → 用自然语言粘贴项目资料 → AI自动整理 → 在世界工作区确认设定 → 编写章节计划 → 生成 → 检查正文 → 编辑 → 确认章节。2.3 将总管 AI 调整为只读助手，把修改行为集中到明确的重写与设定提取工具。',
    'AI助手': 'AI助手用于查询、分析和讨论当前项目，不直接修改项目。需要修改时使用“完全重写、局部重写、设定提取”等明确工具，并通过 Diff 预览确认。',
    '小说': '小说工作台集中处理章节生命周期。左侧章节，中央计划与正文，右侧版本 / Context。已确认章节再次修改会产生新 revision，并让后续章节进入需复核状态。',
    '项目初始化': '创建项目时输入一份自然语言资料即可。AI 会自动提取世界规则、人物、关系、地点、时间线、伏笔、总纲和文风，先作为草稿数据填入工作区，确认后正式进入 Canon。',
    'AI生成章节': '生成流水线：Context → 前文交接与章节规划 → 正文 → 连续性审校 → 状态提取 → 事实摘要。最低前文回顾始终为 1 章。',
    'Canon与确认': 'Canon 是正式事实。AI自动提取的内容不会直接成为正式状态；初始化草稿与章节设定提取都需要作者确认。',
    '影响分析': '在“项目工具”或“AI”菜单点“设定影响分析”，输入要变更的设定，AI 会分析对 Canon、章节、时间线、伏笔的影响。结果只提供建议，不自动改项目。',
    '分支': '分支让你在主线之外试写不同走向。在“项目工具 → 分支管理”里可以新建、切换、删除分支；在分支上未改动的章节会自动跟随主线，改过的章节只在当前分支生效。切换分支前会自动保存快照。',
    '快照与日志': '系统在重要操作前后自动保存项目快照，可在“项目工具 → 项目快照”里浏览内容并从任意快照恢复。运行日志记录打开、生成、备份、导出等关键事件，可在“项目工具 → 运行日志”查看。',
    '导入与搜索': '“文件”菜单可以导入 .novelforge 备份或 JSON 项目；Ctrl+F 可全书搜索章节、Canon 和实体，双击章节结果直接定位。',
    '任务通知': '长任务结束会显示 100% 完成态、完成音效和系统通知（平台支持时）。任务中心还能回看最近任务。',
    '检查': '规则检查适合确定性问题；AI审校适合人物知识、动机、时间线、伏笔、POV和文风等问题。',
    '状态提案': '章节生成后的状态提取会先作为待审核提案保存。只有接受提案后才写入动态状态，避免错误推断污染后续章节。',
    '人物与认知': '人物静态设定之外，还会记录角色知道什么、相信什么、当前位置和人物弧线，避免角色突然掌握不可能知道的信息。',
    '时间线': '记录事件时间、章节、重要性、范围，用于前后顺序和人物状态检查。',
    '伏笔': '保存伏笔代码、首次出现、目标章节、生命周期、重要程度和最后触碰章节。',
    'AI Context': 'Context Inspector 展示生成时 AI 实际看到的项目、Canon、状态、摘要和最近确认章节。',
    '项目设置': '可设置 DeepSeek API Key、Base URL、模型、Thinking、Reasoning effort、输出长度、前文回顾、通知音效等。当前默认模型为 deepseek-flash。',
    'EPUB': '导出时可以选择仅已确认章节，并可设置 PNG/JPG/JPEG 封面。',
    '帮助中心': '搜索并查看每项功能“是什么、怎么用、有什么效果”。各工作区都有 ? 快捷入口。',
}


class Worker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(int, str, str)

    def __init__(self, fn: Callable[['Worker'], object]):
        super().__init__(); self.fn = fn; self.cancelled = False

    def cancel(self): self.cancelled = True

    def run(self):
        try: self.finished.emit(self.fn(self))
        except Exception as e: self.failed.emit(str(e))


class TaskPanel(QFrame):
    cancel_requested = Signal()
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName('TaskCard'); self.setVisible(False); self.setMinimumHeight(150)
        l=QVBoxLayout(self); head=QHBoxLayout(); self.icon=QLabel('●'); self.icon.setStyleSheet('color:#65ecff;font-size:16px');
        self.stage=QLabel('等待'); self.stage.setStyleSheet('font-size:15px;font-weight:800'); head.addWidget(self.icon); head.addWidget(self.stage); head.addStretch(); self.percent=QLabel('0%'); self.percent.setObjectName('BigPercent'); head.addWidget(self.percent); l.addLayout(head)
        self.steps=[]; row=QHBoxLayout();
        for text in ['准备','理解','规划','执行','检查','提交','完成']:
            lab=QLabel(text); lab.setAlignment(Qt.AlignCenter); lab.setStyleSheet('color:#617588;font-size:11px;padding:3px 6px;border-radius:6px;background:#0a131d'); row.addWidget(lab); self.steps.append(lab)
        l.addLayout(row)
        barrow=QHBoxLayout(); self.bar=QProgressBar(); self.bar.setRange(0,100); self.bar.setValue(0); barrow.addWidget(self.bar,1); self.cancel=QPushButton('取消任务'); self.cancel.clicked.connect(self.cancel_requested); barrow.addWidget(self.cancel); self.close=QPushButton('关闭'); self.close.clicked.connect(lambda:self.setVisible(False)); self.close.setEnabled(False); barrow.addWidget(self.close); l.addLayout(barrow)
        self.detail=QLabel(''); self.detail.setObjectName('Subtle'); l.addWidget(self.detail)

    def start(self, stage='开始'):
        self.setVisible(True); self.icon.setText('●'); self.icon.setStyleSheet('color:#65ecff;font-size:16px'); self.stage.setText(stage); self.percent.setText('0%'); self.bar.setValue(0); self.detail.setText('准备 AI 工作…'); self.cancel.setEnabled(True); self.close.setEnabled(False); self._set_steps(0)

    def _set_steps(self,pct):
        idx=0 if pct<5 else min(6, int(pct/16.7)+1)
        for i,x in enumerate(self.steps):
            x.setStyleSheet(('color:#e9faff;background:#123845;border:1px solid #1ba4b8;' if i<=idx else 'color:#617588;background:#0a131d;')+'border-radius:6px;padding:3px 6px;font-size:11px;')

    def update(self,pct,stage,detail=''):
        pct=max(0,min(100,int(pct))); self.bar.setValue(pct); self.percent.setText(f'{pct}%'); self.stage.setText(stage); self.detail.setText(detail); self._set_steps(pct)

    def finish(self,ok=True,message='任务完成'):
        self.update(100,'✓ 已完成' if ok else '✕ 任务结束',message); self.cancel.setEnabled(False); self.close.setEnabled(True); self.icon.setText('✓' if ok else '✕'); self.icon.setStyleSheet(('color:#55f0a1;' if ok else 'color:#ff6d86;')+'font-size:18px;font-weight:900')


class HelpDialog(QDialog):
    def __init__(self,parent,focus='快速开始'):
        super().__init__(parent); self.setWindowTitle('NovelForge · 帮助与教程'); self.resize(1100,760); l=QHBoxLayout(self); left=QVBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText('搜索：Canon、进度、EPUB……'); left.addWidget(self.search); self.list=QListWidget(); left.addWidget(self.list,1); l.addLayout(left); self.content=QPlainTextEdit(); self.content.setReadOnly(True); l.addWidget(self.content,1)
        self.data=HELP
        for k in self.data:self.list.addItem(k)
        self.search.textChanged.connect(self.filter); self.list.currentTextChanged.connect(self.show); keys=list(self.data); self.list.setCurrentRow(keys.index(focus) if focus in keys else 0)
    def filter(self,t):
        q=t.lower().strip()
        for i in range(self.list.count()): self.list.item(i).setHidden(bool(q and q not in self.list.item(i).text().lower()))
    def show(self,k): self.content.setPlainText(self.data.get(k,''))


class TaskCenterDialog(QDialog):
    def __init__(self,parent,db):
        super().__init__(parent); self.setWindowTitle('NovelForge · 任务中心'); self.resize(1050,620); l=QVBoxLayout(self); self.table=QTableWidget(0,6); self.table.setHorizontalHeaderLabels(['任务','状态','进度','阶段','开始','结束']); self.table.setSelectionBehavior(QAbstractItemView.SelectRows); l.addWidget(self.table,1); b=QPushButton('关闭'); b.clicked.connect(self.accept); l.addWidget(b); self.refresh(db)
    def refresh(self,db):
        rows=db.jobs(100); self.table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            for j,v in enumerate([r['kind'],r['status'],f"{r['progress']}%",r['stage'],r['started_at'] or '',r['finished_at'] or '']): self.table.setItem(i,j,QTableWidgetItem(str(v)))


class TextDialog(QDialog):
    def __init__(self,parent,title,label,initial=''):
        super().__init__(parent); self.setWindowTitle(title); self.resize(950,650); l=QVBoxLayout(self); l.addWidget(QLabel(label)); self.edit=QPlainTextEdit(); self.edit.setPlainText(initial); l.addWidget(self.edit,1); b=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); l.addWidget(b)


class DiffDialog(QDialog):
    def __init__(self,parent,title,original,modified,mode='章节重写'):
        super().__init__(parent); self.setWindowTitle(title); self.resize(1200,780); self.original=original; self.modified=modified; l=QVBoxLayout(self); l.addWidget(QLabel(f'{mode}预览：原内容不会自动覆盖。请检查差异后选择接受或拒绝。'))
        tabs=QTabWidget(); a=QPlainTextEdit(); a.setReadOnly(True); a.setPlainText(original); b=QPlainTextEdit(); b.setReadOnly(True); b.setPlainText(modified); import difflib; d=QPlainTextEdit(); d.setReadOnly(True); d.setPlainText('\n'.join(difflib.unified_diff(original.splitlines(),modified.splitlines(),fromfile='原文',tofile='AI修改后',lineterm='')) or '没有文本差异。'); tabs.addTab(d,'Diff'); tabs.addTab(a,'原文'); tabs.addTab(b,'修改后'); l.addWidget(tabs,1); box=QDialogButtonBox(); accept=box.addButton('接受修改',QDialogButtonBox.AcceptRole); reject=box.addButton('拒绝',QDialogButtonBox.RejectRole); accept.setObjectName('Primary'); reject.setObjectName('Danger'); box.accepted.connect(self.accept); box.rejected.connect(self.reject); l.addWidget(box)


class CanonSettingDialog(QDialog):
    def __init__(self,parent,db):
        super().__init__(parent); self.db=db; self.current_id=None; self.setWindowTitle('Canon 设定管理'); self.resize(1120,760)
        l=QVBoxLayout(self); l.addWidget(QLabel('这里管理正式长期设定。新增、修改、删除都会立即作用于 Canon；删除会先要求确认。'))
        form=QFormLayout(); self.category=QLineEdit(); self.category.setPlaceholderText('人物 / 世界规则 / 战力体系 / 物品……'); self.name=QLineEdit(); self.name.setPlaceholderText('设定名称'); self.content=QPlainTextEdit(); self.content.setPlaceholderText('设定内容'); self.lock=QComboBox(); self.lock.addItems(['normal','hard']); form.addRow('分类',self.category); form.addRow('名称',self.name); form.addRow('内容',self.content); form.addRow('锁定级别',self.lock); l.addLayout(form)
        buttons=QHBoxLayout(); add=QPushButton('新增设定'); add.setObjectName('Primary'); add.clicked.connect(self.add); edit=QPushButton('保存修改'); edit.clicked.connect(self.edit); dele=QPushButton('删除设定'); dele.setObjectName('Danger'); dele.clicked.connect(self.remove); clear=QPushButton('清空'); clear.clicked.connect(self.clear_form); buttons.addWidget(add); buttons.addWidget(edit); buttons.addWidget(dele); buttons.addWidget(clear); buttons.addStretch(); l.addLayout(buttons)
        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(['分类','名称','内容','锁定','来源']); self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.itemSelectionChanged.connect(self.load_selected); l.addWidget(self.table,1); close=QPushButton('关闭'); close.clicked.connect(self.accept); l.addWidget(close); self.refresh()
    def refresh(self):
        rows=self.db.canon_facts('canon'); self.rows=rows; self.table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            for j,v in enumerate([r['category'],r['name'],r['content'],r['lock_level'],r['source']]): self.table.setItem(i,j,QTableWidgetItem(str(v)))
    def load_selected(self):
        row=self.table.currentRow()
        if row<0 or row>=len(self.rows):return
        r=self.rows[row]; self.current_id=int(r['id']); self.category.setText(r['category']); self.name.setText(r['name']); self.content.setPlainText(r['content']); self.lock.setCurrentText(r['lock_level'])
    def clear_form(self): self.current_id=None; self.category.clear(); self.name.clear(); self.content.clear(); self.lock.setCurrentText('normal'); self.table.clearSelection()
    def add(self):
        cat=self.category.text().strip() or '其他'; name=self.name.text().strip(); content=self.content.toPlainText().strip()
        if not name or not content:return QMessageBox.information(self,'资料不完整','名称和设定内容不能为空。')
        if self.db.canon_fact(name,cat,'canon'):return QMessageBox.information(self,'已存在','相同分类和名称的 Canon 设定已经存在，请使用“保存修改”。')
        self.db.save_canon_fact(cat,name,content,self.lock.currentText(),'user'); self.refresh(); self.clear_form()
    def edit(self):
        if self.current_id is None:return QMessageBox.information(self,'未选择','先选择一条设定。')
        old=self.rows[self.table.currentRow()]; old_name=old['name']; cat=self.category.text().strip() or '其他'; name=self.name.text().strip()
        if not name or not self.content.toPlainText().strip():return QMessageBox.information(self,'资料不完整','名称和设定内容不能为空。')
        if name!=old_name and self.db.canon_fact(name,cat,'canon'):return QMessageBox.information(self,'名称冲突','新的名称已经存在。')
        self.db.execute('UPDATE canon_facts SET category=?,name=?,content=?,lock_level=?,source=?,updated_at=? WHERE id=?',[cat,name,self.content.toPlainText().strip(),self.lock.currentText(),'user',now_iso(),self.current_id]); self.db.conn.commit(); self.refresh()
    def remove(self):
        if self.current_id is None:return QMessageBox.information(self,'未选择','先选择一条设定。')
        name=self.rows[self.table.currentRow()]['name']
        if QMessageBox.question(self,'删除 Canon','确定删除“'+name+'”？')!=QMessageBox.Yes:return
        self.db.execute('DELETE FROM canon_facts WHERE id=?',[self.current_id]); self.db.conn.commit(); self.refresh(); self.clear_form()


class SettingExtractDialog(QDialog):
    def __init__(self,parent,candidates):
        super().__init__(parent); self.setWindowTitle('设定提取 AI · 候选长期设定'); self.resize(1100,720); self.candidates=candidates; l=QVBoxLayout(self); l.addWidget(QLabel('AI 从本章发现以下可能需要长期保存的设定。勾选后确认，才会写入正式 Canon。'))
        self.table=QTableWidget(len(candidates),7); self.table.setHorizontalHeaderLabels(['采用','类型','名称','内容','证据','判断','置信度']); l.addWidget(self.table,1)
        for i,x in enumerate(candidates):
            box=QCheckBox(); box.setChecked(x.get('action') in {'create','update'} and float(x.get('confidence',0))>=0.7); self.table.setCellWidget(i,0,box)
            vals=[x.get('type',''),x.get('name',''),x.get('content',''),x.get('evidence',''),x.get('action',''),str(x.get('confidence',''))]
            for j,v in enumerate(vals,1):self.table.setItem(i,j,QTableWidgetItem(str(v)))
        bar=QDialogButtonBox(); yes=bar.addButton('加入 Canon',QDialogButtonBox.AcceptRole); no=bar.addButton('全部忽略',QDialogButtonBox.RejectRole); yes.setObjectName('Primary'); no.setObjectName('Danger'); yes.clicked.connect(self.accept); no.clicked.connect(self.reject); l.addWidget(bar)
    def selected(self):
        out=[]
        for i,x in enumerate(self.candidates):
            w=self.table.cellWidget(i,0)
            if w and w.isChecked():out.append(x)
        return out


class SearchDialog(QDialog):
    def __init__(self,parent,db,main):
        super().__init__(parent); self.db=db; self.main=main; self.setWindowTitle('全文搜索'); self.resize(1000,640); l=QVBoxLayout(self)
        h=QHBoxLayout(); self.q=QLineEdit(); self.q.setPlaceholderText('搜索章节、Canon、实体……'); self.q.returnPressed.connect(self.do); b=QPushButton('搜索'); b.setObjectName('Primary'); b.clicked.connect(self.do); h.addWidget(self.q,1); h.addWidget(b); l.addLayout(h)
        self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(['类型','章节','名称','内容片段']); self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.cellDoubleClicked.connect(self.goto); l.addWidget(self.table,1)
        self.hint=QLabel('双击章节结果可直接定位。'); self.hint.setObjectName('Subtle'); l.addWidget(self.hint); self.q.setFocus()
    def do(self):
        rows=self.db.search(self.q.text().strip(),100); self.rows=rows; self.table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            for j,v in enumerate([r['type'],str(r.get('chapter','')),r.get('name') or r.get('title',''),r.get('snippet','')]):self.table.setItem(i,j,QTableWidgetItem(str(v)))
        self.hint.setText(f'找到 {len(rows)} 条结果。双击章节结果可定位。')
    def goto(self,row,_):
        if not (0<=row<len(self.rows)):return
        r=self.rows[row]
        if r['type']=='chapter':
            self.accept(); self.main.open_page('novel'); self.main.pages['novel'].current=int(r['chapter']); self.main.pages['novel'].refresh()


class VolumeDialog(QDialog):
    def __init__(self,parent,db):
        super().__init__(parent); self.db=db; self.setWindowTitle('卷管理'); self.resize(900,560); l=QVBoxLayout(self); l.addWidget(QLabel('编辑卷标题与简介（卷章节分组在项目创建时按卷数自动分配）。'))
        self.table=QTableWidget(0,3); self.table.setHorizontalHeaderLabels(['卷号','标题','简介']); l.addWidget(self.table,1)
        bar=QHBoxLayout(); b=QPushButton('保存修改'); b.setObjectName('Primary'); b.clicked.connect(self.save); c=QPushButton('关闭'); c.clicked.connect(self.accept); bar.addWidget(b); bar.addWidget(c); bar.addStretch(); l.addLayout(bar); self.refresh()
    def refresh(self):
        rows=self.db.volumes(); self.rows=rows; self.table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            self.table.setItem(i,0,QTableWidgetItem(str(r['number'])))
            self.table.setItem(i,1,QTableWidgetItem(r['title'] or ''))
            self.table.setItem(i,2,QTableWidgetItem(r['synopsis'] or ''))
    def save(self):
        for i,r in enumerate(self.rows):
            t=self.table.item(i,1); s=self.table.item(i,2)
            self.db.save_volume(r['number'],t.text().strip() if t else None,s.text().strip() if s else None)
        self.refresh()


class StyleDialog(QDialog):
    def __init__(self,parent,db):
        super().__init__(parent); self.db=db; self.setWindowTitle('文风 Style Profile'); self.resize(900,640); l=QVBoxLayout(self); l.addWidget(QLabel('Style Profile 会进入每章生成的上下文。以 JSON 编辑，保存前会校验格式。'))
        self.editor=QPlainTextEdit(); l.addWidget(self.editor,1)
        bar=QHBoxLayout(); b=QPushButton('保存文风'); b.setObjectName('Primary'); b.clicked.connect(self.save); c=QPushButton('关闭'); c.clicked.connect(self.accept); bar.addWidget(b); bar.addWidget(c); bar.addStretch(); l.addLayout(bar)
        self.editor.setPlainText(json.dumps(self.db.style(),ensure_ascii=False,indent=2))
    def save(self):
        try:
            data=json.loads(self.editor.toPlainText() or '{}')
            if not isinstance(data,dict):raise ValueError('必须是 JSON 对象。')
            self.db.save_style(data); QMessageBox.information(self,'已保存','Style Profile 已保存。')
        except Exception as e:QMessageBox.critical(self,'保存失败',str(e))


class IntentDialog(QDialog):
    def __init__(self,parent,db):
        super().__init__(parent); self.db=db; self.setWindowTitle('作者意图'); self.resize(1000,620); l=QVBoxLayout(self); l.addWidget(QLabel('作者意图会进入每章生成的上下文，优先级高的排前面；“硬性”意图必须遵守。'))
        self.table=QTableWidget(0,6); self.table.setHorizontalHeaderLabels(['标题','范围','键','优先级','硬性','内容']); self.table.setSelectionBehavior(QAbstractItemView.SelectRows); l.addWidget(self.table,1)
        form=QHBoxLayout(); self.title=QLineEdit(); self.title.setPlaceholderText('意图标题'); self.content=QLineEdit(); self.content.setPlaceholderText('意图内容'); self.pri=QSpinBox(); self.pri.setRange(1,10); self.pri.setValue(3); self.hard=QCheckBox('硬性'); add=QPushButton('新增/更新'); add.setObjectName('Primary'); add.clicked.connect(self.add); dele=QPushButton('删除选中'); dele.setObjectName('Danger'); dele.clicked.connect(self.remove); form.addWidget(self.title,1); form.addWidget(self.content,2); form.addWidget(self.pri); form.addWidget(self.hard); form.addWidget(add); form.addWidget(dele); l.addLayout(form)
        close=QPushButton('关闭'); close.clicked.connect(self.accept); l.addWidget(close); self.refresh()
    def refresh(self):
        rows=self.db.intents(); self.rows=rows; self.table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            for j,v in enumerate([r['title'],r['scope_type'],r['scope_key'],str(r['priority']),'是' if r['hard'] else '否',r['content']]):self.table.setItem(i,j,QTableWidgetItem(str(v)))
    def add(self):
        t=self.title.text().strip(); c=self.content.text().strip()
        if not t or not c:return QMessageBox.information(self,'资料不完整','标题和内容不能为空。')
        self.db.set_intent('project','global',t,c,self.pri.value(),self.hard.isChecked()); self.refresh()
    def remove(self):
        row=self.table.currentRow()
        if not (0<=row<len(self.rows)):return QMessageBox.information(self,'未选择','先选择一条意图。')
        if QMessageBox.question(self,'删除意图','确定删除该意图？')!=QMessageBox.Yes:return
        self.db.delete_intent(self.rows[row]['id']); self.refresh()


class BranchDialog(QDialog):
    def __init__(self,parent,db,main):
        super().__init__(parent); self.db=db; self.main=main; self.setWindowTitle('分支管理'); self.resize(960,600); l=QVBoxLayout(self)
        cur=db.active_branch(); self.curlab=QLabel(f'当前分支：{cur["name"] if cur else "主线"}'); self.curlab.setObjectName('Subtle'); l.addWidget(self.curlab)
        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(['ID','名称','基础章节','说明','创建时间']); self.table.setSelectionBehavior(QAbstractItemView.SelectRows); l.addWidget(self.table,1)
        bar=QHBoxLayout(); nb=QPushButton('新建分支'); nb.setObjectName('Accent'); nb.clicked.connect(self.new); sw=QPushButton('切换到选中'); sw.setObjectName('Primary'); sw.clicked.connect(self.switch); dele=QPushButton('删除分支'); dele.setObjectName('Danger'); dele.clicked.connect(self.remove); close=QPushButton('关闭'); close.clicked.connect(self.accept); bar.addWidget(nb); bar.addWidget(sw); bar.addWidget(dele); bar.addWidget(close); bar.addStretch(); l.addLayout(bar); self.refresh()
    def refresh(self):
        rows=self.db.branches(); self.rows=rows; self.table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            for j,v in enumerate([str(r['id']),r['name'],str(r['base_chapter']),r['description'] or '',r['created_at'] or '']):self.table.setItem(i,j,QTableWidgetItem(str(v)))
        cur=self.db.active_branch(); self.curlab.setText(f'当前分支：{cur["name"] if cur else "主线"}')
    def new(self):
        name,ok=self.main.get_text('新建分支','分支名称',f'分支{len(self.rows)}')
        if not ok or not name.strip():return
        base,ok2=self.main.get_text('基础章节','从第几章起分叉（数字）','1')
        if not ok2:return
        try:base=int(base)
        except Exception:return QMessageBox.critical(self,'无效','基础章节必须是数字。')
        self.db.save_branch(name.strip(),1,base,''); self.main.project.db.save_snapshot(f'新建分支 {name}',self.main.project.db.full_state(),0); self.main.refresh_pages(); self.refresh()
    def switch(self):
        row=self.table.currentRow()
        if not (0<=row<len(self.rows)):return QMessageBox.information(self,'未选择','先选择要切换到的分支。')
        r=self.rows[row]
        if self.db.active_branch_id()==int(r['id']):return
        if QMessageBox.question(self,'切换分支',f'切换到“{r["name"]}”？切换前会自动保存当前分支的章节内容。')!=QMessageBox.Yes:return
        try:
            self.main.project.db.save_snapshot(f'切换分支前 {self.db.active_branch()["name"]}',self.main.project.db.full_state(),0)
            self.db.switch_branch(int(r['id']))
            self.main.refresh_pages(); self.main.open_page('novel'); self.refresh()
            self.db.save_log('info','switch_branch',f'切换到分支 {r["name"]}')
        except Exception as e:QMessageBox.critical(self,'切换失败',str(e))
    def remove(self):
        row=self.table.currentRow()
        if not (0<=row<len(self.rows)):return QMessageBox.information(self,'未选择','先选择要删除的分支。')
        r=self.rows[row]
        if int(r['id'])==1:return QMessageBox.information(self,'不能删除','主线分支不能删除。')
        if QMessageBox.question(self,'删除分支',f'删除“{r["name"]}”及其全部分支内容？')!=QMessageBox.Yes:return
        try:
            self.db.delete_branch(int(r['id'])); self.db.save_log('info','delete_branch',f'删除分支 {r["name"]}'); self.refresh()
        except Exception as e:QMessageBox.critical(self,'删除失败',str(e))


class SnapshotDialog(QDialog):
    def __init__(self,parent,db,main):
        super().__init__(parent); self.db=db; self.main=main; self.setWindowTitle('项目快照'); self.resize(1100,680); l=QVBoxLayout(self)
        self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(['ID','标签','相关章节','创建时间']); self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.itemSelectionChanged.connect(self.show_detail); l.addWidget(self.table,1)
        self.detail=QPlainTextEdit(); self.detail.setReadOnly(True); l.addWidget(self.detail,1)
        bar=QHBoxLayout(); b=QPushButton('从选中快照恢复'); b.setObjectName('Primary'); b.clicked.connect(self.restore); c=QPushButton('关闭'); c.clicked.connect(self.accept); bar.addWidget(b); bar.addWidget(c); bar.addStretch(); l.addLayout(bar); self.refresh()
    def refresh(self):
        rows=self.db.snapshots(); self.rows=rows; self.table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            for j,v in enumerate([str(r['id']),r['label'],str(r['chapter_number'] or ''),r['created_at'] or '']):self.table.setItem(i,j,QTableWidgetItem(str(v)))
    def show_detail(self):
        row=self.table.currentRow()
        if not (0<=row<len(self.rows)):self.detail.setPlainText('');return
        try:self.detail.setPlainText(json.dumps(json.loads(self.rows[row]['payload']),ensure_ascii=False,indent=2))
        except Exception:self.detail.setPlainText(str(self.rows[row]['payload']))
    def restore(self):
        row=self.table.currentRow()
        if not (0<=row<len(self.rows)):return QMessageBox.information(self,'未选择','先选择要恢复的快照。')
        r=self.rows[row]
        if QMessageBox.question(self,'恢复快照',f'恢复“{r["label"]}”？当前项目内容会被快照内容覆盖（章节会生成新版本）。')!=QMessageBox.Yes:return
        try:
            self.db.save_snapshot('恢复前自动备份',self.db.full_state(),0)
            restore_full_state(self.db,json.loads(r['payload']))
            self.main.refresh_pages(); self.refresh(); QMessageBox.information(self,'已恢复','快照已恢复。')
        except Exception as e:QMessageBox.critical(self,'恢复失败',str(e))


class LogDialog(QDialog):
    def __init__(self,parent,db):
        super().__init__(parent); self.db=db; self.setWindowTitle('运行日志'); self.resize(1050,620); l=QVBoxLayout(self); self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(['时间','级别','事件','消息','详情']); l.addWidget(self.table,1); c=QPushButton('关闭'); c.clicked.connect(self.accept); l.addWidget(c); self.refresh()
    def refresh(self):
        rows=self.db.logs(300); self.table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            for j,v in enumerate([r['created_at'] or '',r['level'],r['event'],r['message'],r['detail'] or '']):self.table.setItem(i,j,QTableWidgetItem(str(v)))


class NewProjectDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent); self.setWindowTitle('新建项目 · 自然语言资料'); self.resize(1150,780); l=QVBoxLayout(self); f=QFormLayout(); self.title=QLineEdit('未命名小说'); self.author=QLineEdit(); self.total=QSpinBox(); self.total.setRange(1,5000); self.total.setValue(48); self.volumes=QSpinBox(); self.volumes.setRange(1,100); self.volumes.setValue(2); self.path=QLineEdit(str(Path.home()/'NovelForgeProjects'/'我的小说')); f.addRow('书名',self.title); f.addRow('作者',self.author); f.addRow('总章节数',self.total); f.addRow('卷数',self.volumes); f.addRow('项目目录',self.path); l.addLayout(f); l.addWidget(QLabel('项目资料：直接用自然语言粘贴，格式可以混乱，不需要 JSON。'))
        self.material=QPlainTextEdit(); self.material.setObjectName('ManagerInput'); self.material.setPlaceholderText('故事基础、世界观、人物设定、总纲、写作风格、特殊事项……\n也可以把所有资料混在一大段。AI 会自动分类。'); l.addWidget(self.material,1); b=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); b.button(QDialogButtonBox.Ok).setText('创建并自动整理'); b.accepted.connect(self.accept); b.rejected.connect(self.reject); l.addWidget(b)


class AssistantPage(QWidget):
    def __init__(self,main):
        super().__init__(); self.main=main; self.pending_settings=[]
        l=QVBoxLayout(self); h=QHBoxLayout(); t=QLabel('AI 助手'); t.setObjectName('Title'); h.addWidget(t); self.state=QLabel('● 可分析 / 可添加设定'); self.state.setStyleSheet('color:#5febff;font-weight:800'); h.addWidget(self.state); h.addStretch(); b=QPushButton('? 帮助'); b.clicked.connect(lambda:main.show_help('AI助手')); h.addWidget(b); l.addLayout(h)
        l.addWidget(QLabel('AI 可以查询和分析项目，也可以按照明确要求整理长期设定。不会直接改正文。'))
        card=QFrame(); card.setObjectName('ManagerCard'); cl=QVBoxLayout(card); self.input=QPlainTextEdit(); self.input.setObjectName('ManagerInput'); self.input.setPlaceholderText('例如：添加一条长期设定：这个世界的魔法等级一共十阶。'); self.input.setMinimumHeight(160); self.input.installEventFilter(self); cl.addWidget(self.input)
        r=QHBoxLayout(); lab=QLabel('Ctrl+Enter 查询 / 整理设定'); lab.setObjectName('Subtle'); r.addWidget(lab); r.addStretch(); self.apply=QPushButton('应用 AI 设定'); self.apply.setObjectName('Accent'); self.apply.setEnabled(False); self.apply.clicked.connect(self.apply_settings); self.send=QPushButton('▶ AI处理'); self.send.setObjectName('Primary'); self.send.clicked.connect(self.run); r.addWidget(self.apply); r.addWidget(self.send); cl.addLayout(r); l.addWidget(card)
        tabs=QTabWidget(); self.answer=QPlainTextEdit(); self.answer.setReadOnly(True); self.raw=QPlainTextEdit(); self.raw.setReadOnly(True); tabs.addTab(self.answer,'回答'); tabs.addTab(self.raw,'Context'); l.addWidget(tabs,1)
    def eventFilter(self,obj,event):
        if obj is self.input and event.type()==QEvent.KeyPress and event.key()==Qt.Key_Return and event.modifiers()&Qt.ControlModifier:self.run(); return True
        return super().eventFilter(obj,event)
    def run(self):
        if not self.main.project:return self.answer.setPlainText('请先新建或打开项目。')
        msg=self.input.toPlainText().strip()
        if not msg:return
        if self.main.worker:return QMessageBox.information(self,'AI忙碌','已有 AI 任务运行中。')
        n=self.main._selected_chapter() or 1; client=DeepSeekClient(self.main.cfg); b=self.main.pb.assistant(msg,n); self.send.setEnabled(False); self.apply.setEnabled(False); self.main._start_job('assistant',n); self.main.task.start('AI 助手正在分析')
        def work(w):
            w.progress.emit(25,'读取项目上下文','读取 Canon、人物、章节、时间线和伏笔'); r=client.json(b.system,b.user,lambda:w.cancelled); data=DeepSeekClient.parse_json(r.content); w.progress.emit(90,'整理 AI 结果','检查是否提出长期设定'); return {'data':data,'context':self.main.pb.context(n)}
        self.main._run_worker(work,self.on_done)
    def on_done(self,p):
        d=p['data']; self.send.setEnabled(True); self.raw.setPlainText(p['context']); self.answer.setPlainText(d.get('answer','') or ''); self.pending_settings=[x for x in (d.get('settings') or []) if x.get('action')=='create' and x.get('name') and x.get('content')]; self.apply.setEnabled(bool(self.pending_settings)); self.state.setText(f'● 可分析 / 待应用设定 {len(self.pending_settings)} 条')
        if self.pending_settings:self.answer.appendPlainText('\n\n【AI提出的长期设定】\n'+'\n'.join(f'· {x.get("name")}: {x.get("content")}' for x in self.pending_settings))
        self.main.refresh_pages()
    def apply_settings(self):
        if not self.pending_settings or not self.main.project:return
        count=0; skipped=[]
        for x in self.pending_settings:
            name=x['name']; cat=x.get('category') or x.get('type') or '其他'
            if self.main.project.db.canon_fact(name,cat,'canon'):skipped.append(name); continue
            self.main.project.db.save_canon_fact(cat,name,x['content'],x.get('lock_level','normal'),'ai_assistant',self.main._selected_chapter() or None); count+=1
        self.main.project.db.save_snapshot('AI助手添加设定',self.main.project.db.full_state(),self.main._selected_chapter() or 0); self.pending_settings=[]; self.apply.setEnabled(False); self.state.setText('● 可分析 / 可添加设定'); self.main.refresh_pages(); msg=f'AI 助手已加入 {count} 条长期设定到 Canon';
        if skipped:msg+=f'；跳过已存在 {len(skipped)} 条'
        self.main.status(msg)


class NovelPage(QWidget):
    def __init__(self,main):
        super().__init__(); self.main=main; self.current=None; l=QVBoxLayout(self); h=QHBoxLayout(); t=QLabel('小说'); t.setObjectName('Title'); h.addWidget(t); h.addStretch(); hb=QPushButton('?'); hb.clicked.connect(lambda:main.show_help('小说')); h.addWidget(hb); l.addLayout(h)
        split=QSplitter(Qt.Horizontal); l.addWidget(split,1); self.ch=QListWidget(); self.ch.currentItemChanged.connect(self.select); split.addWidget(self.ch)
        center=QWidget(); c=QVBoxLayout(center); meta=QHBoxLayout(); self.num=QLabel(''); self.title=QLineEdit(); self.pov=QLineEdit(); self.pov.setPlaceholderText('POV人物'); self.status=QLabel(''); self.status.setObjectName('Subtle'); meta.addWidget(self.num); meta.addWidget(self.title,2); meta.addWidget(self.pov); meta.addWidget(self.status); c.addLayout(meta)
        tabs=QTabWidget(); self.plan=QPlainTextEdit(); self.plan.setPlaceholderText('本章计划：目的、必须发生、不得发生、人物目标、结尾状态……'); tabs.addTab(self.plan,'本章计划'); self.context=QPlainTextEdit(); self.context.setReadOnly(True); tabs.addTab(self.context,'AI Context'); self.issues=QPlainTextEdit(); self.issues.setReadOnly(True); tabs.addTab(self.issues,'检查'); c.addWidget(tabs,0)
        self.editor=QPlainTextEdit(); self.editor.setObjectName('Editor'); c.addWidget(self.editor,1); b=QHBoxLayout(); save=QPushButton('保存草稿'); save.clicked.connect(self.save); confirm=QPushButton('确认章节'); confirm.setObjectName('Primary'); confirm.clicked.connect(self.confirm); gen=QPushButton('生成本章'); gen.setObjectName('Accent'); gen.clicked.connect(main.generate_current); rewrite=QPushButton('AI重写'); rewrite.clicked.connect(main.open_rewrite); extract=QPushButton('设定提取 AI'); extract.clicked.connect(main.extract_settings_current); inspect=QPushButton('Context'); inspect.clicked.connect(lambda:tabs.setCurrentIndex(1)); b.addWidget(save); b.addWidget(confirm); b.addWidget(gen); b.addWidget(rewrite); b.addWidget(extract); b.addWidget(inspect); b.addStretch(); self.words=QLabel('0字'); b.addWidget(self.words); c.addLayout(b); split.addWidget(center)
        side=QTabWidget(); self.rev=QListWidget(); side.addTab(self.rev,'版本'); split.addWidget(side); split.setSizes([200,930,420])

    def refresh(self):
        if not self.main.project:return
        rows=self.main.project.db.chapters(); self.ch.blockSignals(True); self.ch.clear(); ico={'planned':'○','draft':'✎','generated':'AI','confirmed':'✓'}
        for r in rows:
            it=QListWidgetItem(f"{int(r['number']):03d} {ico.get(r['status'],'?')} {r['title']}"+(' ⚠' if r['stale'] else '')); it.setData(Qt.UserRole,int(r['number'])); self.ch.addItem(it)
        self.ch.blockSignals(False)
        if self.current:
            for i in range(self.ch.count()):
                if self.ch.item(i).data(Qt.UserRole)==self.current:self.ch.setCurrentRow(i);break
        elif self.ch.count():self.ch.setCurrentRow(0)

    def select(self,item,_=None):
        if not item:return
        self.current=int(item.data(Qt.UserRole)); r=self.main.project.db.chapter(self.current)
        if not r:return
        self.num.setText(f'#{self.current}'); self.title.setText(r['title']); self.pov.setText(r['pov_character'] or ''); self.status.setText(r['status']+(' · 需复核' if r['stale'] else '')); self.plan.setPlainText(r['plan'] or ''); self.editor.setPlainText(r['content'] or ''); self.words.setText(f"{int(r['word_count'] or 0):,}字"); self.context.setPlainText(self.main.pb.context(self.current)); iss=[x for x in self.main.project.db.issues(False) if int(x['chapter_number'])==self.current]; self.issues.setPlainText('\n'.join(f"[{x['severity']}] {x['issue_type']}：{x['message']}" for x in iss) or '暂无问题'); self.rev.clear();
        for v in self.main.project.db.revisions(self.current):self.rev.addItem(f"v{v['revision']} · {v['source']} · {v['created_at']}")

    def save(self):
        if not self.current:return
        old=self.main.project.db.chapter(self.current);was=bool(old and old['status']=='confirmed'); self.main.project.db.save_chapter(self.current,self.title.text().strip() or f'第{self.current}章',self.editor.toPlainText(),self.plan.toPlainText(),'draft','user','编辑保存',pov=self.pov.text().strip())
        if was:self.main.project.db.mark_stale_after(self.current)
        self.refresh();self.main.status(f'第 {self.current} 章已保存为草稿')

    def confirm(self):
        if not self.current or not self.editor.toPlainText().strip():return QMessageBox.warning(self,'无法确认','正文不能为空。')
        db=self.main.project.db;db.save_chapter(self.current,self.title.text().strip() or f'第{self.current}章',self.editor.toPlainText(),self.plan.toPlainText(),'confirmed','user','用户确认',pov=self.pov.text().strip());db.save_snapshot(f'确认第{self.current}章',db.full_state(),self.current);StateManager(db).rebuild(self.current);db.save_log('info','confirm_chapter',f'第 {self.current} 章已确认');self.refresh();self.main.status(f'第 {self.current} 章已确认')


class WorldPage(QWidget):
    def __init__(self,main):
        super().__init__(); self.main=main; l=QVBoxLayout(self); h=QHBoxLayout(); t=QLabel('世界'); t.setObjectName('Title'); h.addWidget(t); h.addStretch(); b=QPushButton('重新整理自然语言资料'); b.setObjectName('Primary'); b.clicked.connect(main.initialize_current); h.addWidget(b); c=QPushButton('确认项目设定'); c.setObjectName('Accent'); c.clicked.connect(main.confirm_initialization); h.addWidget(c); q=QPushButton('?'); q.clicked.connect(lambda:main.show_help('项目初始化')); h.addWidget(q); manage=QPushButton('管理 Canon 设定'); manage.setObjectName('Accent'); manage.clicked.connect(main.manage_canon_settings); h.addWidget(manage); l.addLayout(h); self.banner=QLabel(''); self.banner.setObjectName('Subtle'); l.addWidget(self.banner)
        self.tabs=QTabWidget(); l.addWidget(self.tabs,1); self.bible=QPlainTextEdit(); self.bible.setReadOnly(True); self.tabs.addTab(self.bible,'项目资料'); self.canon_table=QTableWidget(0,5); self.canon_table.setHorizontalHeaderLabels(['分类','名称','内容','锁定','来源']); self.tabs.addTab(self.canon_table,'Canon 设定'); self.entity=QTableWidget(0,5); self.entity.setHorizontalHeaderLabels(['名称','类型','范围','说明','来源']); self.tabs.addTab(self.entity,'人物 / 势力 / 地点 / 物品'); self.rel=QTableWidget(0,4); self.rel.setHorizontalHeaderLabels(['主体','对象','关系','说明']); self.tabs.addTab(self.rel,'关系'); self.time=QTableWidget(0,6); self.time.setHorizontalHeaderLabels(['章','时间','事件','重要性','范围','说明']); self.tabs.addTab(self.time,'时间线'); self.fo=QTableWidget(0,7); self.fo.setHorizontalHeaderLabels(['代码','状态','生命周期','首次','目标','重要性','范围']); self.tabs.addTab(self.fo,'伏笔')
    def refresh(self):
        if not self.main.project:return
        d=self.main.project.db; st=d.get_meta('initialization_status','pending'); self.banner.setText({'pending':'项目资料等待 AI 整理','draft':'✓ AI 已自动整理并填充工作区；当前为草稿，点击“确认项目设定”后正式生效','confirmed':'✓ 项目设定已确认为正式 Canon'}.get(st,st)); self.bible.setPlainText(json.dumps({k:d.get_meta(k,'') for k in ['synopsis','canon','outline','style','raw_material']},ensure_ascii=False,indent=2))
        cf=d.canon_facts('canon'); self.canon_table.setRowCount(len(cf));
        for i,r in enumerate(cf):
            for j,v in enumerate([r['category'],r['name'],r['content'],r['lock_level'],r['source']]):self.canon_table.setItem(i,j,QTableWidgetItem(str(v)))
        rows=d.entities(); self.entity.setRowCount(len(rows))
        for i,r in enumerate(rows):
            vals=[r['name'],r['kind'],r['scope'],r['description'],r['source_chapter'] or ''];
            for j,v in enumerate(vals):self.entity.setItem(i,j,QTableWidgetItem(str(v)))
        rs=d.relationships(); self.rel.setRowCount(len(rs));
        for i,r in enumerate(rs):
            for j,v in enumerate([r['source_name'],r['target_name'],r['relation'],r['note']]):self.rel.setItem(i,j,QTableWidgetItem(str(v)))
        ev=d.events(); self.time.setRowCount(len(ev));
        for i,r in enumerate(ev):
            for j,v in enumerate([r['chapter_number'] or '',r['event_time'],r['title'],r['importance'],r['scope'],r['description']]):self.time.setItem(i,j,QTableWidgetItem(str(v)))
        fs=d.foreshadows(); self.fo.setRowCount(len(fs));
        for i,r in enumerate(fs):
            for j,v in enumerate([r['code'],r['status'],r['lifecycle'],r['introduced_chapter'],r['target_chapter'],r['importance'],r['scope']]):self.fo.setItem(i,j,QTableWidgetItem(str(v)))


class TimelinePage(QWidget):
    def __init__(self,main):
        super().__init__(); self.main=main; l=QVBoxLayout(self); t=QLabel('时间线'); t.setObjectName('Title'); l.addWidget(t); self.table=QTableWidget(0,6); self.table.setHorizontalHeaderLabels(['章','时间','事件','重要性','范围','说明']); l.addWidget(self.table,1)
    def refresh(self):
        if not self.main.project:return
        r=self.main.project.db.events(); self.table.setRowCount(len(r))
        for i,x in enumerate(r):
            for j,v in enumerate([x['chapter_number'] or '',x['event_time'],x['title'],x['importance'],x['scope'],x['description']]):self.table.setItem(i,j,QTableWidgetItem(str(v)))


class CheckPage(QWidget):
    def __init__(self,main):
        super().__init__(); self.main=main; l=QVBoxLayout(self); h=QHBoxLayout(); t=QLabel('检查'); t.setObjectName('Title'); h.addWidget(t); h.addStretch(); r=QPushButton('规则全书检查'); r.setObjectName('Primary'); r.clicked.connect(lambda:main.run_health(None)); h.addWidget(r); a=QPushButton('AI全书审校'); a.setObjectName('Accent'); a.clicked.connect(main.ai_global_audit); h.addWidget(a); p=QPushButton('状态提案'); p.clicked.connect(main.open_proposals); h.addWidget(p); q=QPushButton('?'); q.clicked.connect(lambda:main.show_help('检查')); h.addWidget(q); l.addLayout(h); self.summary=QLabel(''); self.summary.setObjectName('Subtle'); l.addWidget(self.summary); self.table=QTableWidget(0,6); self.table.setHorizontalHeaderLabels(['章','级别','类型','问题','位置','状态']); l.addWidget(self.table,1)
    def refresh(self):
        if not self.main.project:return
        rs=self.main.project.db.issues(False); self.table.setRowCount(len(rs))
        for i,r in enumerate(rs):
            for j,v in enumerate([r['chapter_number'],r['severity'],r['issue_type'],r['message'],r['location'],'待处理' if not r['resolved'] else '已解决']):self.table.setItem(i,j,QTableWidgetItem(str(v)))
        self.summary.setText(f'问题：{len(rs)} · 待处理：{len(self.main.project.db.issues(True))} · 状态提案：{len(self.main.project.db.proposals())}')


class ProjectPage(QWidget):
    def __init__(self,main):
        super().__init__(); self.main=main; l=QVBoxLayout(self); t=QLabel('项目'); t.setObjectName('Title'); l.addWidget(t); tabs=QTabWidget(); l.addWidget(tabs,1)
        self.raw=QPlainTextEdit(); self.raw.setPlaceholderText('保存的原始自然语言项目资料。修改后点击“重新整理项目资料”。'); tabs.addTab(self.raw,'项目资料')
        ai=QWidget(); f=QFormLayout(ai); self.api=QLineEdit(); self.api.setEchoMode(QLineEdit.Password); self.base=QLineEdit(); self.model=QLineEdit(); self.th=QCheckBox(); self.eff=QComboBox(); self.eff.addItems(['low','high','max']); self.max=QSpinBox(); self.max.setRange(1,393216); self.review=QSpinBox(); self.review.setRange(1,100); self.ctx=QSpinBox(); self.ctx.setRange(10000,1000000); self.audit=QCheckBox(); self.extract=QCheckBox(); self.back=QCheckBox(); self.auto_audit=QCheckBox(); self.sound=QCheckBox(); self.system_notify=QCheckBox(); self.volume=QDoubleSpinBox(); self.volume.setRange(0,1); self.volume.setSingleStep(.05)
        for n,w in [('API Key',self.api),('Base URL',self.base),('Model',self.model),('Thinking',self.th),('Reasoning effort',self.eff),('Max output tokens',self.max),('前文最少回顾章数',self.review),('Context 字符预算',self.ctx),('生成后自动 AI 审校',self.audit),('生成后自动状态提取',self.extract),('重要操作自动备份',self.back),('任务完成音效',self.sound),('系统任务通知',self.system_notify),('通知音量',self.volume)]:f.addRow(n,w)
        row=QHBoxLayout(); sv=QPushButton('保存 AI 设置'); sv.setObjectName('Primary'); sv.clicked.connect(self.save_settings); tt=QPushButton('测试连接'); tt.clicked.connect(self.test); ts=QPushButton('测试完成音效'); ts.clicked.connect(lambda:self.main.notify.notify('NovelForge','这是一条任务完成提示音。','success')); row.addWidget(sv); row.addWidget(tt); row.addWidget(ts); row.addStretch(); f.addRow(row); tabs.addTab(ai,'AI 设置')
        pm=QWidget(); pl=QVBoxLayout(pm); self.pk=QComboBox(); self.pk.addItems(list(DEFAULT_PROMPTS)); self.pe=QPlainTextEdit(); pl.addWidget(self.pk); pl.addWidget(self.pe,1); ps=QPushButton('保存 Prompt'); ps.clicked.connect(self.save_prompt); pl.addWidget(ps); self.pk.currentTextChanged.connect(self.load_prompt); tabs.addTab(pm,'Prompt')
        actions=QWidget(); al=QGridLayout(actions); buttons=[('重新整理项目资料',main.initialize_current),('确认项目设定',main.confirm_initialization),('设定影响分析',main.impact_analysis),('分支管理',main.manage_branches),('项目快照',main.manage_snapshots),('卷管理',main.manage_volumes),('编辑文风 Profile',main.edit_style),('管理作者意图',main.edit_intents),('搜索全书',main.open_search),('运行日志',main.show_logs),('备份项目',main.backup),('任务中心',main.task_center),('导出 EPUB',main.export_epub),('导出 TXT',main.export_txt),('导出 Markdown',main.export_md),('导出 JSON',main.export_json),('重建剧情状态',main.rebuild_state)]
        for i,(txt,fn) in enumerate(buttons): b=QPushButton(txt); b.clicked.connect(fn); al.addWidget(b,i//3,i%3)
        self.status=QPlainTextEdit(); self.status.setReadOnly(True); al.addWidget(self.status,6,0,2,3); tabs.addTab(actions,'项目工具'); self.load_settings()
    def refresh(self):
        if not self.main.project:return
        d=self.main.project.db; self.raw.setPlainText(d.get_meta('raw_material','')); self.status.setPlainText(json.dumps({'版本':APP_VERSION,'初始化状态':d.get_meta('initialization_status','pending'),'章节':len(d.chapters()),'已确认':len([x for x in d.chapters() if x['status']=='confirmed']),'Canon事实':len(d.canon_facts('canon')),'世界实体':len(d.entities(scope='canon')),'时间线':len(d.events('canon')),'开放伏笔':len(d.foreshadows('open')),'问题':len(d.issues(True)),'设定提案':len(d.setting_proposals())},ensure_ascii=False,indent=2)); self.load_settings(); self.load_prompt(self.pk.currentText())
    def load_settings(self):
        c=self.main.cfg; self.api.setText(c.api_key); self.base.setText(c.base_url); self.model.setText(c.model); self.th.setChecked(c.thinking); self.eff.setCurrentText(c.reasoning_effort); self.max.setValue(c.max_tokens); self.review.setValue(max(1,c.review_count)); self.ctx.setValue(c.context_char_budget); self.audit.setChecked(c.auto_audit); self.extract.setChecked(c.auto_extract); self.back.setChecked(c.auto_backup); self.sound.setChecked(c.notify_sound); self.system_notify.setChecked(c.notify_system); self.volume.setValue(c.notify_volume)
    def save_settings(self):
        c=self.main.cfg; c.api_key=self.api.text().strip(); c.base_url=self.base.text().strip() or 'https://api.deepseek.com'; c.model=self.model.text().strip() or 'deepseek-flash'; c.thinking=self.th.isChecked(); c.reasoning_effort=self.eff.currentText(); c.max_tokens=self.max.value(); c.review_count=max(1,self.review.value()); c.context_char_budget=self.ctx.value(); c.auto_audit=self.audit.isChecked(); c.auto_extract=self.extract.isChecked(); c.auto_backup=self.back.isChecked(); c.notify_sound=self.sound.isChecked(); c.notify_system=self.system_notify.isChecked(); c.notify_volume=self.volume.value(); c.save(); self.main.notify.cfg=c; self.main.status('AI 设置已保存')
    def test(self):
        self.save_settings()
        try:QMessageBox.information(self,'DeepSeek',DeepSeekClient(self.main.cfg).text('你是连接测试助手。','只回复：NovelForge 连接成功。').content.strip())
        except Exception as e:QMessageBox.critical(self,'连接失败',str(e))
    def load_prompt(self,k):
        if self.main.project and k:self.pe.setPlainText(self.main.project.db.get_meta('prompt:'+k,DEFAULT_PROMPTS[k]))
    def save_prompt(self):
        if self.main.project:self.main.project.db.set_meta('prompt:'+self.pk.currentText(),self.pe.toPlainText()); self.main.status('Prompt 已保存')


class MainWindow(QMainWindow):
    def __init__(self,cfg):
        super().__init__(); self.cfg=cfg; self.project=None; self.thread=None; self.worker=None; self.job_id=None; self.pages={}; self._callback=None; self.setWindowTitle(f'{APP_NAME} · AI 长篇小说 IDE'); self.resize(1650,1000); self.setStyleSheet(STYLE); self.setFont(QFont('Microsoft YaHei UI',10))
        root=QWidget(); self.root_layout=QVBoxLayout(root); self.root_layout.setContentsMargins(0,0,0,0); self.root_layout.setSpacing(8); self.task=TaskPanel(root); self.task.cancel_requested.connect(self.cancel_ai); self.root_layout.addWidget(self.task)
        body=QWidget(); bl=QHBoxLayout(body); bl.setContentsMargins(0,0,0,0); bl.setSpacing(0); self.sidebar=self.build_sidebar(); bl.addWidget(self.sidebar); from PySide6.QtWidgets import QStackedWidget; self.stack=QStackedWidget(); bl.addWidget(self.stack,1); self.root_layout.addWidget(body,1); self.setCentralWidget(root); self.build_menu();
        self.pb=None; self.notify=NotificationManager(self,cfg,Path(__file__).resolve().parents[1]/'assets'/'sounds'); self.add_page('manager',AssistantPage(self)); self.add_page('novel',NovelPage(self)); self.add_page('world',WorldPage(self)); self.add_page('timeline',TimelinePage(self)); self.add_page('check',CheckPage(self)); self.add_page('project',ProjectPage(self)); self.open_page('manager'); self.statusBar().showMessage('请新建或打开项目'); self.autosave=QTimer(self); self.autosave.timeout.connect(self.autosave_tick); self.autosave.start(max(2,cfg.auto_save_seconds)*1000)

    def build_sidebar(self):
        w=QWidget(); w.setObjectName('Sidebar'); l=QVBoxLayout(w); l.setContentsMargins(11,14,11,14); b=QLabel('NovelForge'); b.setObjectName('Brand'); l.addWidget(b); v=QLabel(f'{APP_VERSION} · AI Story Workbench'); v.setObjectName('Version'); l.addWidget(v); self.plabel=QLabel('未打开项目'); self.plabel.setObjectName('Project'); l.addWidget(self.plabel); self.nav={}
        for k,text in [('manager','AI 助手'),('novel','小说'),('world','世界'),('timeline','时间线'),('check','检查'),('project','项目')]: x=QPushButton(text); x.setObjectName('Nav'); x.clicked.connect(lambda _,a=k:self.open_page(a)); l.addWidget(x); self.nav[k]=x
        l.addStretch(); tb=QPushButton('🔔 任务中心'); tb.clicked.connect(self.task_center); l.addWidget(tb); h=QPushButton('❔ 帮助与教程'); h.clicked.connect(lambda:self.show_help('快速开始')); l.addWidget(h); return w

    def build_menu(self):
        mb=self.menuBar(); f=mb.addMenu('文件')
        for n,fn,sc in [('新建项目',self.new_project,'Ctrl+N'),('打开项目',self.open_project,'Ctrl+O'),('导入备份(.novelforge)',self.import_backup,''),('导入 JSON',self.import_json,''),('搜索全书',self.open_search,'Ctrl+F'),('备份项目',self.backup,'Ctrl+Shift+B'),('导出 EPUB',self.export_epub,'Ctrl+E'),('导出 TXT',self.export_txt,'Ctrl+Alt+T'),('导出 JSON',self.export_json,'Ctrl+Alt+J'),('退出',self.close,'Alt+F4')]: a=QAction(n,self); a.setShortcut(sc); a.triggered.connect(fn); f.addAction(a)
        ai=mb.addMenu('AI')
        for n,fn in [('AI 助手',lambda:self.open_page('manager')),('生成本章',self.generate_current),('生成下一章',self.generate_next),('检查当前章',self.audit_current),('AI全书审校',self.ai_global_audit),('设定影响分析',self.impact_analysis)]: a=QAction(n,self); a.triggered.connect(fn); ai.addAction(a)
        h=mb.addMenu('帮助'); a=QAction('帮助与教程',self); a.triggered.connect(lambda:self.show_help('快速开始')); h.addAction(a)

    def add_page(self,k,p):self.pages[k]=p; self.stack.addWidget(p)
    def open_page(self,k):
        if k not in self.pages:return
        self.stack.setCurrentWidget(self.pages[k])
        for name,b in self.nav.items():b.setObjectName('NavActive' if name==k else 'Nav'); b.style().unpolish(b); b.style().polish(b)
        p=self.pages[k]
        if hasattr(p,'refresh'):
            try:p.refresh()
            except Exception:pass
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        eff=QGraphicsOpacityEffect(self.stack); self.stack.setGraphicsEffect(eff); eff.setOpacity(.55); an=QPropertyAnimation(eff,b'opacity',self); an.setDuration(180); an.setStartValue(.55); an.setEndValue(1); an.setEasingCurve(QEasingCurve.OutCubic); an.start(QPropertyAnimation.DeleteWhenStopped); self._fade=an

    def refresh_pages(self):
        if self.project:
            title=self.project.db.get_meta('title','未命名小说')
            b=self.project.db.active_branch(); bname=b['name'] if b else '主线'
            self.plabel.setText(f'{title} · {bname}')
        self.pb=PromptBuilder(self.project.db,self.cfg) if self.project else None
        for p in self.pages.values():
            if hasattr(p,'refresh'):
                try:p.refresh()
                except Exception:pass

    def status(self,msg):self.statusBar().showMessage(msg)
    def show_help(self,focus='快速开始'):HelpDialog(self,focus).exec()
    def task_center(self):
        if not self.project:return QMessageBox.information(self,'任务中心','请先打开项目。')
        TaskCenterDialog(self,self.project.db).exec()

    def new_project(self):
        d=NewProjectDialog(self)
        if d.exec()!=QDialog.Accepted:return
        path=Path(d.path.text()).expanduser()
        if (path/'project.sqlite3').exists():
            if QMessageBox.question(self,'项目已存在','该目录已有项目，是否打开它？')!=QMessageBox.Yes:return
            self._open_project_path(path); return
        if self.project:self.project.close()
        self.project=Project.create(path,d.title.text().strip() or '未命名小说',d.total.value(),d.volumes.value(),d.material.toPlainText(),d.author.text().strip())
        self.cfg.last_project=str(path); self.cfg.save()
        self.project.db.save_log('info','create_project','项目已创建',str(path))
        self.refresh_pages(); self.open_page('manager'); self.status('项目创建成功，开始整理自然语言设定…')
        if self.cfg.auto_backup:
            try:self.project.backup()
            except Exception:pass
        if self.cfg.api_key.strip(): self.initialize_current(auto=True)
        else:self.status('项目已创建；填写 DeepSeek Key 后即可自动整理设定')

    def open_project(self):
        path=QFileDialog.getExistingDirectory(self,'选择 NovelForge 项目目录')
        if not path:return
        self._open_project_path(path)

    def _open_project_path(self, path, silent=False):
        path=Path(path).expanduser()
        if not (path/'project.sqlite3').exists():
            if not silent:QMessageBox.warning(self,'无法打开',f'该目录不是有效的 NovelForge 项目：\n{path}')
            return False
        try:
            if self.project:self.project.close()
            self.project=Project(path)
            self.cfg.last_project=str(path); self.cfg.save()
            self.refresh_pages(); self.open_page('manager')
            self.status(f'项目已打开：{self.project.db.get_meta("title","未命名小说")}')
            self.project.db.save_log('info','open_project','项目已打开',str(path))
            return True
        except Exception as e:
            if not silent:QMessageBox.critical(self,'打开失败',str(e))
            return False

    def auto_open_last(self):
        last=(self.cfg.last_project or '').strip()
        if not last:return
        if not self._open_project_path(last, silent=True):
            self.cfg.last_project=''; self.cfg.save()
            self.status('上次打开的项目未找到，已忽略')

    def backup(self):
        if not self.project:return
        try:
            name=self.project.backup().name; self.status('备份完成：'+name); self.project.db.save_log('info','backup','备份完成',name); self.notify.notify('NovelForge','项目备份完成。','success')
        except Exception as e:QMessageBox.critical(self,'备份失败',str(e))

    def initialize_current(self,auto=False):
        if not self.project:return
        raw=self.project.db.get_meta('raw_material','').strip()
        if not raw:
            if not auto:QMessageBox.information(self,'没有资料','项目中没有保存自然语言资料。')
            return
        if self.worker:return
        if not self.cfg.api_key.strip():
            if not auto:QMessageBox.information(self,'需要 API Key','请到“项目 → AI设置”填写 DeepSeek API Key。')
            return
        client=DeepSeekClient(self.cfg); b=self.pb.initializer(raw); self._start_job('initialize',None); self.task.start('AI 正在解析项目资料')
        def task(w):
            stages=[(8,'读取原始资料','识别故事基础、世界观、人物、总纲、文风和特殊事项'),(25,'结构化世界观','提取规则、国家、种族、地理、历史、力量体系'),(43,'整理人物与关系','识别人物、身份、关系与限定条件'),(60,'建立时间线与伏笔','区分已发生事实与未来总纲'),(77,'建立文风与作者意图','生成可执行 Style Profile'),(93,'检查冲突','寻找矛盾、缺失和不确定项')]
            for pct,stage,detail in stages:
                w.progress.emit(pct,stage,detail)
                if w.cancelled:raise RuntimeError('任务已取消')
            r=client.json(b.system,b.user,lambda:w.cancelled)
            return {'init':DeepSeekClient.parse_json(r.content)}
        self._run_worker(task,self.on_initialize)

    def on_initialize(self,p):
        data=p['init']; ops=[]
        for f in data.get('canon_facts') or []:ops.append({'op':'create_canon_fact','target':f.get('name',''),'fields':f,'reason':'项目初始化自动整理','confidence':1})
        for e in data.get('entities') or []:ops.append({'op':'create_entity','target':e.get('name',''),'fields':e,'reason':'项目初始化自动整理','confidence':1})
        for r in data.get('relationships') or []:ops.append({'op':'create_relationship','target':f"{r.get('source','')} → {r.get('target','')}",'fields':r,'reason':'项目初始化自动整理','confidence':1})
        for x in data.get('timeline') or []:ops.append({'op':'create_event','target':x.get('title',''),'fields':x,'reason':'项目初始化时间线','confidence':1})
        for f in data.get('foreshadowing') or []:ops.append({'op':'create_foreshadow','target':f.get('code',''),'fields':f,'reason':'项目初始化伏笔','confidence':1})
        for i in data.get('intents') or []:ops.append({'op':'set_intent','target':i.get('title',''),'fields':i,'reason':'项目初始化作者意图','confidence':1})
        if data.get('style_profile'):ops.append({'op':'set_style','target':'Style Profile','fields':data['style_profile'],'reason':'项目初始化文风','confidence':1})
        meta=data.get('project_meta') or {}; self.project.db.set_meta('draft_synopsis',meta.get('synopsis','')); self.project.db.set_meta('draft_outline',data.get('outline','')); self.project.db.set_meta('draft_style',json.dumps(data.get('style_profile') or {},ensure_ascii=False)); payload={'operations':ops,'conflicts':data.get('conflicts',[]),'questions':data.get('questions',[]),'impact':data.get('warnings',[])}
        try:
            OperationEngine(self.project.db).apply(payload,'draft'); self.project.db.set_meta('initialization_status','draft'); self.refresh_pages(); self.open_page('world'); self.status(f'AI 已整理并填充 {len(ops)} 项项目资料；等待确认'); self.show_init_review(payload); self.notify.notify('NovelForge','项目资料已自动整理完成，等待确认。','success')
        except Exception as e:QMessageBox.critical(self,'初始化失败',str(e))

    def show_init_review(self,payload):
        d=QDialog(self); d.setWindowTitle('项目初始化完成 · 请确认'); d.resize(1050,760); l=QVBoxLayout(d); l.addWidget(QLabel('AI 已把自然语言资料填入世界、人物、时间线、关系和伏笔。当前是草稿，确认后才成为正式 Canon。')); e=QPlainTextEdit(); e.setReadOnly(True); e.setPlainText(OperationEngine.preview(payload)); l.addWidget(e,1); tabs=QTabWidget(); raw=QPlainTextEdit(); raw.setReadOnly(True); raw.setPlainText(json.dumps(payload,ensure_ascii=False,indent=2)); tabs.addTab(raw,'内部结构'); l.addWidget(tabs,1); b=QDialogButtonBox(QDialogButtonBox.Ok); b.button(QDialogButtonBox.Ok).setText('关闭，稍后确认'); b.accepted.connect(d.accept); l.addWidget(b); d.exec()

    def confirm_initialization(self):
        if not self.project:return
        if self.project.db.get_meta('initialization_status','pending')!='draft':return QMessageBox.information(self,'没有待确认内容','当前项目没有待确认的初始化草稿。')
        self.project.db.promote_drafts(); self.project.db.set_meta('synopsis',self.project.db.get_meta('draft_synopsis','')); self.project.db.set_meta('outline',self.project.db.get_meta('draft_outline','')); self.project.db.set_meta('style',self.project.db.get_meta('draft_style','')); self.project.db.set_meta('initialization_status','confirmed'); self.project.db.save_snapshot('确认项目设定',self.project.db.full_state(),0); self.refresh_pages(); self.status('项目设定已确认，正式进入写作状态'); self.notify.notify('NovelForge','项目设定已确认，可以开始生成章节。','success')

    def generate_next(self):
        if not self.project:return
        if self.project.db.get_meta('initialization_status','pending')!='confirmed':return QMessageBox.information(self,'请先确认设定','项目设定还没有确认。')
        rows=self.project.db.chapters(); target=next((int(x['number']) for x in rows if x['status']!='confirmed'),None)
        if target is None:target=max([int(x['number']) for x in rows] or [0])+1;self.project.db.execute('INSERT INTO chapters(number,volume_number,title,status,created_at,updated_at) VALUES(?,?,?,?,?,?)',[target,1,f'第{target}章','planned',now_iso(),now_iso()]);self.project.db.conn.commit()
        self.open_page('novel'); self.pages['novel'].current=target; self.pages['novel'].refresh(); self.generate_current()

    def generate_current(self):
        if not self.project:return
        if self.project.db.get_meta('initialization_status','pending')!='confirmed':return QMessageBox.information(self,'请先确认设定','项目设定还没有确认。')
        n=self._selected_chapter()
        if not n:return
        # 读取「本章计划」：优先取编辑器当前内容（可能尚未保存），否则回退数据库。
        plan_text=''
        page=self.pages.get('novel')
        if isinstance(page,NovelPage) and page.current==n:
            plan_text=page.plan.toPlainText().strip()
        if not plan_text:
            row=self.project.db.chapter(n)
            plan_text=(row['plan'] or '').strip() if row else ''
        instr,ok=self.get_text('本次生成要求','给这一章的额外要求；可留空。');
        if not ok:return
        if self.worker:return QMessageBox.information(self,'AI忙碌','已有 AI 任务运行中。')
        # 合并「本章计划」与「本次生成要求」，显式传给规划 AI 和正文 AI。
        req=[]
        if plan_text:req.append('【本章计划（作者设定，必须遵循）】\n'+plan_text)
        if instr.strip():req.append('【本次额外要求】\n'+instr.strip())
        instruction='\n\n'.join(req)
        client=DeepSeekClient(self.cfg); pb=self.pb; self._start_job('generate',n); self.task.start('AI 正在生成章节')
        def task(w):
            w.progress.emit(12,'前文交接与章节规划','一次完成前文交接和本章蓝图'); b=pb.plan(n,instruction); pl=client.json(b.system,b.user,lambda:w.cancelled); plan=DeepSeekClient.parse_json(pl.content)
            w.progress.emit(44,'正文生成','按照 Canon、人物认知、POV和时间线生成正文'); b=pb.writer(n,instruction,plan); gen=client.json(b.system,b.user,lambda:w.cancelled); gd=DeepSeekClient.parse_json(gen.content); content=(gd.get('chapter') or {}).get('content','')
            audit=None
            if self.cfg.auto_audit:w.progress.emit(63,'连续性审校','检查 Canon、人物、时间线、知识、伏笔和POV'); b=pb.audit(n,content); au=client.json(b.system,b.user,lambda:w.cancelled); audit=DeepSeekClient.parse_json(au.content)
            state={}
            if self.cfg.auto_extract:w.progress.emit(78,'剧情状态提取','提取人物状态、事件、关系、认知和伏笔变化'); b=pb.extract(n,content); ex=client.json(b.system,b.user,lambda:w.cancelled); state=DeepSeekClient.parse_json(ex.content)
            summary=''
            if self.cfg.auto_summary:w.progress.emit(91,'事实摘要','生成供后续章节使用的长期摘要'); b=pb.summary(content); summary=client.text(b.system,b.user,lambda:w.cancelled).content.strip()
            w.progress.emit(98,'整理结果','保存候选正文与待审核状态提案'); return {'n':n,'generated':gd,'plan':plan,'audit':audit,'state':state,'summary':summary}
        self._run_worker(task,self.on_generated)

    def on_generated(self,p):
        db=self.project.db; n=p['n']; old=db.chapter(n); c=p['generated'].get('chapter') or {}; title=c.get('title') or (old['title'] if old else f'第{n}章'); db.save_chapter(n,title,c.get('content',''),json.dumps(p['plan'],ensure_ascii=False,indent=2),'generated','ai','AI生成',pov=(old['pov_character'] if old else ''))
        if p.get('summary'):db.save_summary(n,n,p['summary'],'chapter')
        db.clear_issues(n); Checker(db).save_local(n,c.get('content',''))
        for x in (p.get('audit') or {}).get('issues') or []:db.save_issue(n,x.get('severity','low'),x.get('type','unknown'),x.get('message',''),x.get('location',''),x.get('references',[]))
        StateManager(db).propose(n,p.get('state',{}),int(db.chapter(n)['current_revision'] or 0),'AI状态提取，待用户审核'); db.save_snapshot(f'AI候选第{n}章',db.full_state(),n); self.refresh_pages(); self.open_page('novel'); self.pages['novel'].current=n; self.pages['novel'].refresh(); self.status(f'第 {n} 章生成完成；正文待审核，状态提案未自动应用')

    def audit_current(self):
        n=self._selected_chapter();
        if not n or not self.project:return
        r=self.project.db.chapter(n)
        if not r or not r['content']:return QMessageBox.information(self,'没有正文','当前章节没有正文。')
        client=DeepSeekClient(self.cfg); b=self.pb.audit(n,r['content']); self._start_job('audit',n); self.task.start('AI正在审校章节'); self._run_worker(lambda w:{'n':n,'audit':DeepSeekClient.parse_json(client.json(b.system,b.user,lambda:w.cancelled).content)},self.on_audited)

    def on_audited(self,p):
        self.project.db.clear_issues(p['n']); data=p['audit'];
        for x in data.get('issues') or []:self.project.db.save_issue(p['n'],x.get('severity','low'),x.get('type','unknown'),x.get('message',''),x.get('location',''),x.get('references',[]))
        self.refresh_pages(); self.status(f'第 {p["n"]} 章 AI 审校完成')

    def ai_global_audit(self):
        if not self.project or self.worker:return
        rows=[r for r in self.project.db.chapters() if r['content'].strip()]
        if not rows:return
        if QMessageBox.question(self,'AI全书审校',f'将逐章调用 AI 审校 {len(rows)} 章，可能消耗较多 API。继续？')!=QMessageBox.Yes:return
        client=DeepSeekClient(self.cfg); pb=self.pb; self._start_job('global_audit'); self.task.start('AI正在执行全书审校')
        def task(w):
            total=0
            for i,r in enumerate(rows,1):
                w.progress.emit(int((i-1)/len(rows)*90),f'审校第 {i}/{len(rows)} 章',f'分析第 {r["number"]} 章'); b=pb.audit(int(r['number']),r['content']); au=client.json(b.system,b.user,lambda:w.cancelled); data=DeepSeekClient.parse_json(au.content); self.project.db.clear_issues(int(r['number']));
                for x in data.get('issues') or []:self.project.db.save_issue(int(r['number']),x.get('severity','low'),x.get('type','unknown'),x.get('message',''),x.get('location',''),x.get('references',[])); total += len(data.get('issues') or [])
            return {'total':total,'chapters':len(rows)}
        self._run_worker(task,lambda p:(self.refresh_pages(),self.status(f'全书 AI 审校完成：{p["chapters"]}章，{p["total"]}项问题')))

    def open_rewrite(self):
        p=self.pages.get('novel')
        if not isinstance(p,NovelPage) or not p.current:return
        d=QDialog(self);d.setWindowTitle('AI 重写');d.resize(820,420);l=QVBoxLayout(d);l.addWidget(QLabel('选择重写模式'))
        mode=QComboBox();mode.addItems(['完全重写','保证当前逻辑，局部重写']);l.addWidget(mode);l.addWidget(QLabel('修改要求'))
        inst=QPlainTextEdit();inst.setPlaceholderText('例如：加强战斗过程、减少流水账、让对白自然一些……');l.addWidget(inst,1);l.addWidget(QLabel('局部重写：有选区就修改选区；没有选区时默认修改光标所在段落，无需额外勾选原文。'))
        bar=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);bar.button(QDialogButtonBox.Ok).setText('开始生成');bar.accepted.connect(d.accept);bar.rejected.connect(d.reject);l.addWidget(bar)
        if d.exec()!=QDialog.Accepted:return
        instruction=inst.toPlainText().strip(); mode_text=mode.currentText();
        if not instruction:return QMessageBox.information(self,'缺少要求','请输入修改要求。')
        selected=p.editor.textCursor().selectedText()
        if mode_text.startswith('保证') and not selected.strip():
            block=p.editor.textCursor().block(); selected=block.text()
            if not selected.strip():return QMessageBox.information(self,'没有可修改内容','局部重写会默认使用光标所在段落；当前段落为空。')
        self._run_rewrite(p.current,mode_text,instruction,selected)

    def _run_rewrite(self,n,mode,instruction,selected):
        if self.worker:return QMessageBox.information(self,'AI忙碌','已有 AI 任务运行中。')
        row=self.project.db.chapter(n);client=DeepSeekClient(self.cfg);
        if mode.startswith('完全'):
            must_keep=[f'章节标题：{row["title"]}',f'章节计划：{row["plan"]}',f'章节摘要（若有）：{row["summary"]}']
            must_keep += [x['content'] for x in self.project.db.canon_facts('canon') if x['lock_level']=='hard'][:60]
            b=self.pb.rewrite_full(n,row['content'],instruction,must_keep);jobkind='rewrite_full';self.task.start('AI 正在完全重写章节');
            def work(w):w.progress.emit(15,'读取原章','准备 Canon、角色状态、时间线和伏笔');r=client.text(b.system,b.user,lambda:w.cancelled);w.progress.emit(92,'生成完成','等待你检查 Diff');return {'mode':'full','n':n,'original':row['content'],'modified':r.content.strip()}
        else:
            cursor=self.pages['novel'].editor.textCursor();pos=cursor.position();anchor=cursor.anchor();a,bp=min(pos,anchor),max(pos,anchor);full=row['content'];near=full[max(0,a-1200):min(len(full),bp+1200)];bb=self.pb.rewrite_local(n,selected,instruction,near);jobkind='rewrite_local';self.task.start('AI 正在局部重写');
            def work(w):w.progress.emit(20,'读取局部上下文','锁定选中文本及前后衔接');r=client.text(bb.system,bb.user,lambda:w.cancelled);w.progress.emit(92,'生成完成','等待你检查 Diff');return {'mode':'local','n':n,'original':selected,'modified':r.content.strip(),'start':a,'end':bp}
        self._start_job(jobkind,n);self._run_worker(work,self.on_rewrite_preview)

    def on_rewrite_preview(self,p):
        self._rewrite_pending=p
        d=DiffDialog(self,f'第{p["n"]}章 · {"完全重写" if p["mode"]=="full" else "局部重写"}',p['original'],p['modified'],p['mode']);ok=d.exec()==QDialog.Accepted
        if not ok:self.status('已拒绝 AI 重写，不改变原文');return
        row=self.project.db.chapter(p['n']);
        if p['mode']=='full':new=p['modified']
        else:new=row['content'][:p['start']]+p['modified']+row['content'][p['end']:]
        self.project.db.save_chapter(p['n'],row['title'],new,row['plan'],'draft','ai','AI重写已确认',pov=row['pov_character'],perspective=row['perspective'],tense=row['tense']);self.project.db.mark_stale_after(p['n']);self.refresh_pages();self.open_page('novel');self.pages['novel'].current=p['n'];self.pages['novel'].refresh();self.status(f'第 {p["n"]} 章 AI重写已接受并保存新版本')

    def extract_settings_current(self):
        n=self._selected_chapter();
        if not n or not self.project:return
        row=self.project.db.chapter(n)
        if not row or not row['content'].strip():return QMessageBox.information(self,'没有正文','当前章节没有正文。')
        if self.worker:return QMessageBox.information(self,'AI忙碌','已有 AI 任务运行中。')
        client=DeepSeekClient(self.cfg);b=self.pb.setting_extract(n,row['content']);self._start_job('setting_extract',n);self.task.start('设定提取 AI 正在分析本章')
        def work(w):w.progress.emit(20,'扫描本章','寻找可能具有长期有效性的规则和定义');r=client.json(b.system,b.user,lambda:w.cancelled);w.progress.emit(90,'整理候选设定','准备人工确认');return {'n':n,'data':DeepSeekClient.parse_json(r.content)}
        self._run_worker(work,self.show_setting_candidates)

    def show_setting_candidates(self,p):
        data=p['data'];candidates=data.get('candidates') or []
        if not candidates:return QMessageBox.information(self,'设定提取','本章没有发现明显的新长期设定。')
        d=SettingExtractDialog(self,candidates)
        proposal_id=self.project.db.save_setting_proposal(p['n'],data,int(self.project.db.chapter(p['n'])['current_revision'] or 0),'设定提取 AI 候选')
        if d.exec()!=QDialog.Accepted:
            self.project.db.review_setting_proposal(proposal_id,False);return
        selected=d.selected();ops=[]
        for x in selected:
            if x.get('action') not in {'create','update'}:continue
            # 先按 Canon fact 落地；复杂实体由用户后续在世界工作区整理。
            action=x.get('action','create');name=x.get('name','');category=x.get('category') or x.get('type','其他')
            existing=self.project.db.canon_fact(name,category,'canon')
            if action=='update' and not existing: action='create'
            ops.append({'op':'create_canon_fact' if action=='create' else 'update_canon_fact','target':name,'fields':{'category':category,'name':name,'content':x.get('content',''),'lock_level':x.get('lock_level','normal'),'source_chapter':p['n']},'reason':x.get('reason','本章设定提取'),'confidence':x.get('confidence',0)})
        if not ops:return self.status('没有选择任何长期设定')
        try:
            OperationEngine(self.project.db).apply({'operations':ops},'canon');self.project.db.review_setting_proposal(proposal_id,True);self.project.db.save_snapshot(f'第{p["n"]}章设定提取确认',self.project.db.full_state(),p['n']);self.refresh_pages();self.status(f'已加入 {len(ops)} 条长期设定到 Canon')
        except Exception as e:
            QMessageBox.critical(self,'设定写入失败',str(e))

    def rewrite_selection(self):
        self.open_rewrite()

    def manage_canon_settings(self):
        if not self.project:return
        CanonSettingDialog(self,self.project.db).exec(); self.refresh_pages()

    def open_search(self):
        if not self.project:return QMessageBox.information(self,'搜索','请先打开项目。')
        SearchDialog(self,self.project.db,self).exec()

    def manage_branches(self):
        if not self.project:return
        BranchDialog(self,self.project.db,self).exec(); self.refresh_pages()

    def manage_snapshots(self):
        if not self.project:return
        SnapshotDialog(self,self.project.db,self).exec(); self.refresh_pages()

    def manage_volumes(self):
        if not self.project:return
        VolumeDialog(self,self.project.db).exec(); self.refresh_pages()

    def edit_style(self):
        if not self.project:return
        StyleDialog(self,self.project.db).exec(); self.refresh_pages()

    def edit_intents(self):
        if not self.project:return
        IntentDialog(self,self.project.db).exec(); self.refresh_pages()

    def show_logs(self):
        if not self.project:return
        LogDialog(self,self.project.db).exec()

    def import_backup(self):
        archive,_=QFileDialog.getOpenFileName(self,'选择备份文件','','NovelForge 备份 (*.novelforge)')
        if not archive:return
        target=QFileDialog.getExistingDirectory(self,'选择导入目标目录')
        if not target:return
        try:
            p=Project.import_archive(Path(archive),Path(target))
            if self.project:self.project.close()
            self.project=p; self.cfg.last_project=str(target); self.cfg.save(); self.refresh_pages(); self.open_page('manager'); self.status('备份已导入'); self.project.db.save_log('info','import','导入备份',archive)
        except Exception as e:QMessageBox.critical(self,'导入失败',str(e))

    def import_json(self):
        src,_=QFileDialog.getOpenFileName(self,'选择 JSON 文件','','JSON (*.json)')
        if not src:return
        target=QFileDialog.getExistingDirectory(self,'选择导入目标目录')
        if not target:return
        try:
            p=Project.import_json(Path(src),Path(target))
            if self.project:self.project.close()
            self.project=p; self.cfg.last_project=str(target); self.cfg.save(); self.refresh_pages(); self.open_page('manager'); self.status('JSON 已导入'); self.project.db.save_log('info','import','导入 JSON',src)
        except Exception as e:QMessageBox.critical(self,'导入失败',str(e))

    def impact_analysis(self):
        if not self.project:return QMessageBox.information(self,'影响分析','请先打开项目。')
        if self.worker:return QMessageBox.information(self,'AI忙碌','已有 AI 任务运行中。')
        change,ok=self.get_text('设定影响分析','描述要变更的设定（例如：把魔法等级上限从十阶改成十二阶）')
        if not ok or not change.strip():return
        client=DeepSeekClient(self.cfg); b=self.pb.impact(change.strip()); self._start_job('impact',None); self.task.start('AI 正在分析设定影响')
        def work(w):
            w.progress.emit(20,'读取项目状态','分析 Canon、章节、时间线与伏笔'); r=client.json(b.system,b.user,lambda:w.cancelled); w.progress.emit(95,'整理影响结果',''); return DeepSeekClient.parse_json(r.content)
        self._run_worker(work,self.on_impact)

    def on_impact(self,data):
        d=QDialog(self); d.setWindowTitle('设定影响分析结果'); d.resize(1050,740); l=QVBoxLayout(d); l.addWidget(QLabel('以下只作分析，不会自动修改项目。')); e=QPlainTextEdit(); e.setReadOnly(True); e.setPlainText(json.dumps(data,ensure_ascii=False,indent=2)); l.addWidget(e,1); b=QDialogButtonBox(QDialogButtonBox.Ok); b.accepted.connect(d.accept); l.addWidget(b); d.exec()

    def rebuild_state(self):
        if not self.project:return
        text,ok=self.get_text('重建剧情状态','输入截至哪一章；留空表示全部。')
        if not ok:return
        try:n=int(text) if text.strip() else None; r=StateManager(self.project.db).rebuild(n); self.project.db.save_snapshot('重建剧情状态',self.project.db.full_state(),n or 0); self.refresh_pages(); self.status(f'状态重建完成：{r["updates"]}个状态更新')
        except Exception as e:QMessageBox.critical(self,'重建失败',str(e))

    def open_proposals(self):
        if not self.project:return
        rows=self.project.db.proposals()
        if not rows:return QMessageBox.information(self,'状态提案','当前没有待审核状态提案。')
        r=rows[0]; d=QDialog(self); d.setWindowTitle('状态提案审核'); d.resize(980,700); l=QVBoxLayout(d); l.addWidget(QLabel(f'第 {r["chapter_number"]} 章 · {r["reason"]}')); e=QPlainTextEdit(); e.setReadOnly(True); e.setPlainText(json.dumps(json.loads(r['payload']),ensure_ascii=False,indent=2)); l.addWidget(e,1); bar=QHBoxLayout(); yes=QPushButton('接受'); yes.setObjectName('Primary'); no=QPushButton('拒绝'); no.setObjectName('Danger'); bar.addWidget(yes); bar.addWidget(no); bar.addStretch(); l.addLayout(bar); yes.clicked.connect(lambda:(StateManager(self.project.db).approve(int(r['id'])),d.accept(),self.refresh_pages())); no.clicked.connect(lambda:(StateManager(self.project.db).reject(int(r['id'])),d.accept(),self.refresh_pages())); d.exec()

    def run_health(self,n=None):
        if not self.project:return
        db=self.project.db; rows=[db.chapter(n)] if n else [r for r in db.chapters() if r['content'].strip()]
        for r in rows:
            if r:Checker(db).save_local(int(r['number']),r['content'])
        self.refresh_pages(); self.status(f'规则检查完成：{len(rows)}章')

    def get_text(self,title,label,initial=''):
        d=TextDialog(self,title,label,initial); return d.edit.toPlainText(),d.exec()==QDialog.Accepted
    def _selected_chapter(self):
        p=self.pages.get('novel'); return p.current if isinstance(p,NovelPage) else None
    def _start_job(self,kind,n=None):
        if self.project:self.job_id=self.project.db.create_job(kind,n)

    def _run_worker(self,fn,callback):
        if self.thread:return
        self.thread=QThread(self); self.worker=Worker(fn); self.worker.moveToThread(self.thread); self._callback=callback
        self.worker.progress.connect(self.task.update)
        if self.job_id and self.project:self.worker.progress.connect(lambda p,s,d:self.project.db.update_job(self.job_id,p,s,d))
        self.worker.finished.connect(self._worker_success); self.worker.failed.connect(self._worker_failed); self.thread.started.connect(self.worker.run); self.thread.finished.connect(self._thread_cleanup); self.thread.start()

    def _worker_success(self,result):
        cb=self._callback; self._callback=None
        try:
            if cb:cb(result)
            self._finish_task(True,'任务完成',result)
        except Exception as e:
            self._finish_task(False,str(e),{'error':str(e)})

    def _worker_failed(self,msg):
        self._callback=None; self._finish_task(False,msg,{'error':msg}); QMessageBox.critical(self,'AI任务失败',msg); self.status('AI任务失败')

    def _finish_task(self,ok,message,result=None):
        if self.project:
            try:self.project.db.save_log('info' if ok else 'error','task_finish',message)
            except Exception:pass
        if self.project and self.job_id:
            try:self.project.db.finish_job(self.job_id,'done' if ok else 'failed','' if ok else message,result=result or {})
            except Exception:pass
            self.job_id=None
        self.task.finish(ok,message)
        if ok:self.notify.notify('NovelForge','AI任务已经完成。','success')
        else:self.notify.notify('NovelForge','AI任务失败，请查看错误信息。','error')
        if self.thread:self.thread.quit()

    def _thread_cleanup(self):
        t=self.thread
        self.thread=None; self.worker=None
        if t:
            try:t.deleteLater()
            except Exception:pass

    def cancel_ai(self):
        if self.worker:self.worker.cancel(); self.task.detail.setText('正在取消，等待当前 API 请求结束…')

    def _export(self,ext,fn,label,epub=False):
        if not self.project:return
        title=(self.project.db.get_meta('title','小说') or '小说').replace('/','_').replace('\\','_'); path,_=QFileDialog.getSaveFileName(self,f'导出{label}',str(self.project.folder/'exports'/(title+ext)),f'{label} (*{ext})')
        if not path:return
        try:
            if epub:
                only=QMessageBox.question(self,'导出范围','只导出已确认章节？',QMessageBox.Yes|QMessageBox.No,QMessageBox.Yes)==QMessageBox.Yes; cover,_=QFileDialog.getOpenFileName(self,'选择封面（可取消）',str(self.project.folder/'assets'),'图片 (*.png *.jpg *.jpeg)'); fn(self.project.db,Path(path),confirmed_only=only,cover=Path(cover) if cover else None)
            else:fn(self.project.db,Path(path))
            self.project.db.save_log('info','export',f'{label}导出完成',str(path)); self.status(f'{label}导出完成'); self.notify.notify('NovelForge',f'{label} 导出完成。','success')
        except Exception as e:QMessageBox.critical(self,'导出失败',str(e))
    def export_epub(self):self._export('.epub',export_epub,'EPUB',True)
    def export_txt(self):self._export('.txt',export_txt,'TXT')
    def export_md(self):self._export('.md',export_md,'Markdown')
    def export_json(self):self._export('.json',export_json,'JSON')

    def autosave_tick(self):
        p=self.pages.get('novel')
        if self.project and isinstance(p,NovelPage) and p.current and p.editor.document().isModified():
            old=self.project.db.chapter(p.current);was=bool(old and old['status']=='confirmed');self.project.db.save_chapter(p.current,p.title.text(),p.editor.toPlainText(),p.plan.toPlainText(),'draft','autosave','自动保存',pov=p.pov.text());
            if was:self.project.db.mark_stale_after(p.current)
            p.editor.document().setModified(False)

    def closeEvent(self,e):
        if self.worker:self.worker.cancel()
        if self.project:self.project.close()
        e.accept()


def run_app():
    app=QApplication.instance() or QApplication([]); app.setApplicationName(APP_NAME); app.setApplicationDisplayName(APP_NAME); w=MainWindow(AppConfig.load()); w.show(); w.auto_open_last(); return app.exec()
