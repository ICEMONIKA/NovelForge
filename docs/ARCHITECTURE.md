# NovelForge 2.4 Architecture

## 总原则

AI 是辅助层，不是事实源。正式 Canon 和用户确认后的动态状态才是小说长期事实。

## AI 工作流

### 项目
`Natural Language → initializer → draft data → user confirmation → Canon`

### 章节
`Context → handoff → Scene planner → writer → audit → state extraction → summary → user confirmation`

### 设定提取
`chapter → setting_extract → candidate settings → user selection → Canon`

### 重写
`mode selection → full/local AI rewrite → Diff → accept/reject → revision`

## Scene

Scene 同时保存计划与实际执行结果，因此可以回答：本章计划了什么、正文实际发生了什么、偏差在哪里、状态如何变化。

## 数据层

- `canon_facts`: 长期正式设定
- `entities`: 人物、势力、地点、物品等结构化实体
- `character_knowledge`: 角色认知边界
- `events`: 时间线与剧情事件
- `foreshadows`: 伏笔生命周期
- `scenes`: 章节中间层
- `chapter_revisions`: 正文版本（含计划、状态、POV 快照，分支切换据此恢复）
- `state_proposals`: AI 状态提取待确认区
- `setting_proposals`: 设定提取历史
- `branches` / `branch_chapters`: 多分支（多结局），分支未改动的章节自动跟随主线
- `snapshots`: 关键操作自动快照，可浏览与恢复
- `logs`: 运行日志
- `author_intents` / `volumes`: 作者意图、卷结构

## 分支

`chapters` 表始终保存当前激活分支的工作视图；每次保存章节会把 revision 指针写入 `branch_chapters`。切换分支时把当前视图记回旧分支指针，再按目标分支指针（缺失时回退主线）恢复章节。分支上未改动的章节跟随主线的最新内容。

## 修改安全

普通修改工具只在用户明确确认后执行。高风险删除仍有额外保护。章节重写不会覆盖旧 revision；历史章节修改会使后续章节进入需复核状态。重要操作前后自动保存快照，可随时从快照恢复。
