# NovelForge 2.4

> 自然语言优先的桌面长篇小说 IDE —— **AI 分析 + 明确工具 + 用户确认**

`Python 3.10+` · `PySide6 (Qt6)` · `SQLite (WAL)` · `DeepSeek API`

NovelForge 2.4 不采用"总管 Agent 自动执行"模式，而是把 AI 严格限制在**分析、生成候选、给出建议**的位置上。所有会改变项目事实的写入都必须经过作者确认。AI 的推测永远不会自动变成正式 Canon。

---

## 目录

- [1. 这是什么](#1-这是什么)
- [2. 本版（2.4）重要变更](#2-本版24重要变更)
- [3. 运行环境与安装](#3-运行环境与安装)
- [4. 五分钟快速开始](#4-五分钟快速开始)
- [5. 核心概念](#5-核心概念)
- [6. 界面结构](#6-界面结构)
- [7. AI 能力清单](#7-ai-能力清单)
- [8. 章节生成流水线](#8-章节生成流水线)
- [9. Context 上下文引擎](#9-context-上下文引擎)
- [10. 数据模型](#10-数据模型)
- [11. 分支（多结局）机制](#11-分支多结局机制)
- [12. 快照与恢复](#12-快照与恢复)
- [13. 修改安全模型](#13-修改安全模型)
- [14. 导入与导出](#14-导入与导出)
- [15. 运行日志与任务中心](#15-运行日志与任务中心)
- [16. 全部设置项](#16-全部设置项)
- [17. 目录结构](#17-目录结构)
- [18. 测试](#18-测试)
- [19. 构建与打包](#19-构建与打包)
- [20. DeepSeek 配置与成本提示](#20-deepseek-配置与成本提示)
- [21. 常见问题](#21-常见问题)
- [22. 已知限制](#22-已知限制)

---

## 1. 这是什么

NovelForge 是一个**面向长篇小说的桌面创作 IDE**。它要解决的核心问题是：

> 长篇小说写到几十万字后，作者自己都会忘记"某个角色在第 12 章知道什么""这件物品的属性是什么""这个伏笔埋了没回收"。AI 写长篇最容易崩的地方，也正是在这里——它会凭空补设定、让角色知道不该知道的事、写出与前面矛盾的数值。

因此 2.4 的设计原则是：

| 原则 | 具体做法 |
|---|---|
| **AI 不是事实源** | Canon（正式设定）只有作者确认才能写入 |
| **分层存真相** | 世界事实 / 作者意图 / 文风 / 未来计划 / 角色当前状态互不混淆 |
| **过程可追溯** | 章节每次修改产生新 revision；关键操作自动快照 |
| **推测先隔离** | AI 提取的状态先进入"待审核提案"，接受后才进动态状态 |
| **修改可回滚** | 所有重要操作前后自动保存项目快照，可浏览并恢复 |

---

## 2. 本版（2.4）重要变更

### 2.1 架构调整

- **移除 Scene 中间层**。2.3 及之前的"Scene Blueprint（Scene 计划层 + 实际层）"被整体删除：不再有 `scenes` 数据表、Scene 管理界面、Scene 相关上下文段落与 Scene 结果回写。章节规划改为**章节级蓝图**，直接进入正文生成。
- **合并"前文交接"与"章节规划"**。原先 `handoff` → `planner` 两次 AI 调用合并为一次 `plan` 调用，生成流水线由 6 次调用降为 5 次。
- **统一 system prompt（激活上下文缓存）**。生成流水线的各步骤（规划/正文/审校/提取/摘要）现在共用同一个 `SYSTEM_ENGINE` system 提示词，各自的角色指令被移动到 user 消息**末尾**（大 context 之后）。这样多步调用共享完全相同的 `system + context` 前缀，可命中 DeepSeek 上下文缓存，显著降低输入费用。

### 2.2 功能补齐

- **启动自动打开上次项目**（`last_project` 记录在全局配置，失效时静默忽略并清除）。
- **分支（多结局）**：新建 / 切换 / 删除分支；分支未改动的章节自动跟随主线。
- **项目快照**：浏览 + 从任意快照恢复。
- **全文搜索**（章节 / Canon / 实体，双击定位）。
- **导入项目**（`.novelforge` 备份、JSON）。
- **卷管理**、**文风 Profile 直接编辑**、**作者意图直接编辑**。
- **设定影响分析 AI** 接入界面。
- **运行日志**（关键事件落库 + 查看器）。

### 2.3 修复

- `PromptBuilder` 缺少 `get` 方法导致生成章节报 `AttributeError`（改为正确的 `prompt()`）。
- `branch_chapters` 插入语句绑定参数数量不匹配（`Incorrect number of bindings supplied`）。
- **「本章计划」此前完全没有进入生成流程**，现在作为最高优先级要求传给规划与正文 AI（并优先读取编辑器里尚未保存的内容）。
- 分支上新建的章节在切回主线时会泄漏内容，现改为恢复为"计划态空章"。
- 规则检查器不再把对白里的"我"误判为叙述视角越界。

---

## 3. 运行环境与安装

### 3.1 依赖

`requirements.txt`：

```
PySide6>=6.7,<7
openai>=1.90,<2
```

- Python **3.10 或更高**（代码大量使用 `X | None` 与 `dataclass` 类型注解）
- 需要能访问 `https://api.deepseek.com`
- 桌面环境（PySide6 GUI）；通知音效依赖 `assets/sounds/*.wav`

### 3.2 安装与运行

```bash
python -m pip install -r requirements.txt
python main.py
```

Windows 用户可直接双击 **`run_windows.bat`**（内含依赖安装 + 启动）。

### 3.3 首次运行

1. 打开程序 → 未打开项目时状态栏提示"请新建或打开项目"。
2. 进入 **项目 → AI 设置**，填入 DeepSeek **API Key**。
3. 点 **测试连接** 确认可用（会真实调用一次 API，只回复固定文案）。

> 未填写 API Key 时，项目仍可创建与编辑，只是所有 AI 功能会提示需要 Key。

---

## 4. 五分钟快速开始

```
新建项目 ──► AI 自动整理资料（草稿） ──► 世界工作区确认设定（→ Canon）
   │
   └─► 小说工作台：写「本章计划」 ──► 生成本章 ──► 审校/状态提案 ──► 编辑 ──► 确认章节
```

1. **文件 → 新建项目**（Ctrl+N）
   填书名、作者、总章节数、卷数，然后把世界观/人物/总纲/文风等**用自然语言粘贴**进去——不需要 JSON，可以凌乱混杂。
2. 点【创建并自动整理】。若已配置 API Key，会自动调用**项目初始化 AI**，把资料结构化后填入各工作区（此时是 **draft 草稿**）。
3. 切到 **世界** 工作区检查整理结果，点【确认项目设定】，草稿正式晋升为 **Canon**。
4. 切到 **小说** 工作台，选中第 1 章，在【本章计划】里写本章目标（例如"主角首次进入王都，必须见到守门人，结尾拿到邀请函"）。
5. 点【生成本章】。AI 会依次完成：前文交接与章节规划 → 正文 → 连续性审校 → 剧情状态提取 → 事实摘要。
6. 生成结果是 **候选正文**（状态为 `generated`），SCene 等辅助数据不再存在；正文旁边的【检查】页签会列出审校问题。修改满意后点【确认章节】，状态变为 `confirmed`。
7. 生成时产生的状态变更（人物位置、关系、认知、伏笔等）会作为**状态提案**待审核，在 **检查 → 状态提案** 中逐条接受或拒绝。
8. 重复 4~7 写下一章（【生成下一章】会自动选中下一个未确认章节）。

---

## 5. 核心概念

### 5.1 Canon（正式事实）

`canon_facts` 表的正式长期设定，带两个关键属性：

- **category（分类）**：人物 / 世界规则 / 战力体系 / 物品……
- **lock_level（锁定级别）**：`normal` / `hard`。`hard` 表示硬性设定，会作为"必须保留"内容进入重写与生成。

AI 自动整理出来的内容先以 `scope='draft'` 存储，作者点【确认项目设定】后 `promote_drafts()` 统一晋升为 `scope='canon'`。

### 5.2 动态状态

由**状态提取 AI**从正文中抽取、经作者审核后写入的氛围层数据：

| 表 | 含义 |
|---|---|
| `character_knowledge` | 角色认知边界（谁知道什么、是"知道"还是"以为"还是"怀疑"） |
| `character_arcs` | 人物弧线（阶段、欲望、恐惧、信念、冲突、转变、下一阶段、触发事件） |
| `relationships` | 动态关系（身份之外的实时关系与强度） |
| `events` | 时间线事件 |
| `foreshadows` | 伏笔生命周期（introduced / touched / resolved） |

动态层可以**整体重建**：项目工具 →【重建剧情状态】，会清空动态数据并按 `state_updates` 逐章重放。

### 5.3 本章计划（作者意图）

每章有一个作者手写的【本章计划】字段（`chapters.plan`）。它是**生成时优先级最高的作者要求**，会在规划与正文阶段显式传给 AI。

> 生成时，程序优先读取编辑器里**尚未保存**的计划文本；若为空则回退数据库中的值。生成完成后 `chapters.plan` 会被 AI 产出的章节蓝图覆盖（原始正文与历史版本仍保存在 revision 中）。

### 5.4 章节生命周期

```
planned ──► draft ──► generated ──► confirmed
   ○           ✎           AI            ✓
```

- 每次保存都会写入 `chapter_revisions`（含标题、正文、计划、状态、POV、人称、时态快照），**旧版本永不覆盖**。
- 修改一个**已确认**章节，会让其之后的所有章节标记 `stale`（列表中显示 ⚠ 需复核）。
- 每次保存都会记录当前**分支**的内容指针（见第 11 章）。

### 5.5 分支

同一份项目里可以剥离出多条剧情走向（多结局）。分支未改动过的章节会自动跟随主线；改动过的章节只在当前分支生效。详见第 11 章。

---

## 6. 界面结构

### 6.1 侧栏导航

| 页面 | 用途 |
|---|---|
| **AI 助手** | 提问、分析、整理长期设定（不会直接改正文） |
| **小说** | 章节生命周期主工作台 |
| **世界** | 项目资料 / Canon / 实体 / 关系 / 时间线 / 伏笔 |
| **时间线** | 事件总览 |
| **检查** | 规则检查、AI 审校、状态提案 |
| **项目** | 项目资料、AI 设置、Prompt、项目工具 |

侧栏顶部显示**书名 · 当前分支**。

### 6.2 菜单

**文件**

| 菜单项 | 快捷键 | 说明 |
|---|---|---|
| 新建项目 | `Ctrl+N` | 自然语言建项 |
| 打开项目 | `Ctrl+O` | 选择项目目录（含 `project.sqlite3`） |
| 导入备份(.novelforge) | — | 解压备份到目标目录并打开 |
| 导入 JSON | — | 从 `full_state` 导出的 JSON 建项目 |
| 搜索全书 | `Ctrl+F` | 章节 / Canon / 实体搜索 |
| 备份项目 | `Ctrl+Shift+B` | 打包为 `.novelforge` |
| 导出 EPUB | `Ctrl+E` | 可选仅已确认章节 + 封面 |
| 导出 TXT | `Ctrl+Alt+T` | — |
| 导出 JSON | `Ctrl+Alt+J` | 全量状态 |
| 退出 | `Alt+F4` | — |

**AI**

`AI 助手` / `生成本章` / `生成下一章` / `检查当前章` / `AI全书审校` / `设定影响分析`

**帮助**

`帮助与教程`（内置可搜索的帮助中心，各工作区也有 `?` 快捷入口）

### 6.3 小说工作台

```
┌──────────┬─────────────────────────────────────────────┬──────────┐
│ 章节列表 │ 编号 · 标题 · POV · 状态                     │  版本     │
│          ├─────────────────────────────────────────────┤          │
│ 001 ○    │ [本章计划] [AI Context] [检查]               │ v3 · ai  │
│ 002 ✎    │                                             │ v2 · user│
│ 003 AI ⚠ │  ┌───────────────────────────────────────┐  │ v1 · ai  │
│ 004 ✓    │  │            正文编辑器                 │  │          │
│          │  └───────────────────────────────────────┘  │          │
│          │ [保存草稿][确认章节][生成本章][AI重写]       │          │
│          │ [设定提取 AI][Context]            1,234字    │          │
└──────────┴─────────────────────────────────────────────┴──────────┘
```

- **本章计划**：作者手写计划，生成时最高优先级。
- **AI Context**：展示生成时 AI **实际看到**的完整上下文（可用来排查"AI 为什么不知道这件事"）。
- **检查**：当前章的规则检查 + AI 审校问题列表。
- **版本**：历史 revision 列表。
- **自动保存**：编辑器有改动时按 `auto_save_seconds`（默认 8 秒）自动存为草稿。

### 6.4 世界工作区

页签：`项目资料` / `Canon 设定` / `人物·势力·地点·物品` / `关系` / `时间线` / `伏笔`

- 【重新整理自然语言资料】重新跑项目初始化 AI。
- 【确认项目设定】把草稿晋升为 Canon。
- 【管理 Canon 设定】打开 Canon 增删改对话框（新增 / 保存修改 / 删除设定 / 清空）。

### 6.5 检查页

- **规则全书检查**：跑本地确定性规则（见 7.13）。
- **AI全书审校**：逐章调用 AI 审校（会提示消耗较多 API）。
- **状态提案**：审阅并接受/拒绝生成时产生的状态变更。

### 6.6 项目页 → 项目工具

17 个入口：

`重新整理项目资料` `确认项目设定` `设定影响分析` `分支管理` `项目快照` `卷管理` `编辑文风 Profile` `管理作者意图` `搜索全书` `运行日志` `备份项目` `任务中心` `导出 EPUB` `导出 TXT` `导出 Markdown` `导出 JSON` `重建剧情状态`

下方文本框实时显示项目统计（版本、初始化状态、章节数、已确认数、Canon 事实数、世界实体数、时间线数、开放伏笔数、问题数、设定提案数）。

---

## 7. AI 能力清单

所有提示词都可在 **项目 → Prompt** 页签查看与覆盖（覆盖值存入项目数据库 `meta` 的 `prompt:<名称>`，优先级高于内置默认值）。

| # | 名称 | 角色 | 输入 | 输出 |
|---|---|---|---|---|
| 1 | `initializer` | 项目初始化架构师 | 自然语言原始资料 | 世界/人物/关系/时间线/伏笔/总纲/文风草稿 |
| 2 | `assistant` | 项目 AI 助手 | 全量 Context + 作者问题 | 回答 + 可选长期设定候选 |
| 3 | `setting_extract` | 设定提取 AI | Context + 章正文 | 长期设定候选（含证据/位置/冲突标记） |
| 4 | `rewrite_full` | 完全重写 AI | Context + 原章 + 必须保留清单 | 完整新正文 |
| 5 | `rewrite_local` | 局部重写 AI | Context + 选区 + 前后文 | 仅替换选区的文本 |
| 6 | `plan` | 章节规划器 | Context + 本章要求 | 前文交接 + 章节蓝图（不含 Scene） |
| 7 | `writer` | 受约束正文引擎 | Context + 本章要求 + 章节蓝图 | 章正文 + 状态更新 + 阻塞冲突 |
| 8 | `audit` | 连续性审校器 | Context + 候选正文 | 评分 + 问题列表 + 知识泄漏 + 伏笔提示 |
| 9 | `extract` | 剧情状态提取器 | Context + 章正文 | 实体/关系/事件/物品/认知/弧线/伏笔变更 |
| 10 | `summary` | 事实摘要器 | 章正文 | 紧凑中文摘要 |
| 11 | `impact` | 影响分析器 | Context + 设定变更描述 | direct_conflicts / indirect_impacts / safe_changes / unknowns |
| 12 | `style` | 文风提取器 | 样文 | Style Profile JSON |

### 7.1~7.5 建项与设定类

- **项目初始化**：把混乱的自然语言拆成结构化事实。规则强调"用户明确说出的事实优先""总纲中的未来剧情不能写成已发生的事件""角色知道什么必须独立处理"。
- **AI 助手**：只能查询/分析；当作者明确说"添加/记录一条长期设定"时，输出 `settings` 候选，点【应用 AI 设定】后才写入 Canon（已存在的同名同分类设定会被跳过）。它**不会**修改正文。
- **设定提取**：严格区分「长期设定 / 剧情状态 / 普通剧情信息」，每项候选必须给证据与位置，与现有 Canon 冲突时标记 `conflict` 而不覆盖。勾选后写入 Canon。
- **完全重写**：保留 Hard Canon、锁定人物设定、时间线、已发生关键事实、重大结果与核心伏笔状态；可改变结构、对白、描写、节奏、战斗过程。先进入 **Diff** 预览。
- **局部重写**：只改选区。若没有选区，默认使用**光标所在段落**。

### 7.6~7.10 章节流水线

见[第 8 章](#8-章节生成流水线)。

### 7.11 设定影响分析

在 **AI 菜单**或**项目工具**点【设定影响分析】，输入要变更的设定（例如"把魔法等级上限从十阶改成十二阶"），AI 会分析对 Canon、实体、章节、时间线、伏笔、关系与角色知识的影响，并分类列出受影响章节与原因。**只分析，不改项目。**

### 7.12 文风 Profile

`style_profiles` 表保存单条 Style Profile（POV、叙述距离、句长、对白、节奏、信息密度、幽默、词汇、段落、禁用模式），会进入每次生成的上下文。可在 **项目工具 → 编辑文风 Profile** 里以 JSON 直接编辑并校验格式。

### 7.13 规则检查（非 AI）

`checker.py` 提供确定性检查，不消耗 API：

| 规则 | 判定 |
|---|---|
| `possible_pov_leak` | 第三人称限知章节中，**剔除引号内对白后**叙述部分出现 ≥3 处"我" |
| `foreshadow_overdue` | 未回收伏笔的 `target_chapter` 已小于当前章 |
| `repetition` | 5 字以上中文短语出现 ≥8 次（取前 5） |

---

## 8. 章节生成流水线

点击【生成本章】后执行 **5 次 AI 调用**（可在 AI 设置里关掉后三步）：

```
① plan      前文交接与章节规划   12%
② writer    正文生成             44%
③ audit     连续性审校           63%   ← auto_audit
④ extract   剧情状态提取         78%   ← auto_extract
⑤ summary   事实摘要             91%   ← auto_summary
                              98% 整理结果
```

### 8.1 输入要求（`instruction`）

生成前会把两部分合并为「本章要求」：

```
【本章计划（作者设定，必须遵循）】
<编辑器中的本章计划>

【本次额外要求】
<点击生成时弹窗里输入的临时要求>
```

### 8.2 各步骤说明

| 步骤 | 做什么 | 输出 |
|---|---|---|
| **① plan** | 先做前文交接（上一章结束时的位置/目标/认知/未解决冲突），再做章节级蓝图（目标、必须发生、可选发生、禁止发生、人物目标、信息边界、伏笔边界、结尾状态、下一章钩子） | `{handoff:{...}, chapter_plan:{...}}` |
| **② writer** | 事实优先级：Hard Canon > 锁定事实 > 已确认动态状态 > 作者硬性意图 > 本章蓝图 > 前文交接 > AI 自由发挥 | `{chapter:{title,content}, summary, state_update, blocking_conflicts}` |
| **③ audit** | 检查 Canon、人物静态与动态设定、角色知识、关系、时间线、地点、物品、能力、事件因果、章节计划、人物弧线、伏笔、POV、提前揭示、重复与文风 | `{score, issues[], passed[], knowledge_leaks[], foreshadowing_notes[], chapter_plan_deviation[]}` |
| **④ extract** | 从正文提取明确发生的状态变化 | `state_update`（实体/关系/事件/物品/认知/弧线/伏笔） |
| **⑤ summary** | 生成供后续章节使用的紧凑摘要，写入 `summaries` | 纯文本 |

### 8.3 生成结果如何落库

1. 正文写入 `chapters`（状态 `generated`，source `ai`），同时产生新 revision；
2. 摘要写入 `summaries`；
3. 规则检查 + AI 审校问题写入 `audit_issues`；
4. 状态提取结果写入 **`state_proposals`（待审核）**——不会自动应用；
5. 自动保存快照 `AI候选第N章`；
6. 界面自动跳到该章并刷新。

> 正文是**候选稿**，状态是 `generated` 而非 `confirmed`。满意后手动点【确认章节】。

### 8.4 其他生成入口

- **生成下一章**：定位第一个未确认章节（没有就新建一章）后走同一流程。
- **检查当前章**：只跑 ③ audit。
- **AI全书审校**：对所有有正文的章节逐章跑 ③，结果覆盖写入 `audit_issues`。

---

## 9. Context 上下文引擎

`context.py` 决定"每次生成时 AI 到底能看到什么"。这是整个项目质量与成本的核心。

### 9.1 段落与预算（字符）

按顺序拼接，最后整体裁剪到 `context_char_budget`：

| # | 段名 | 上限（字符） | 内容 |
|---|---|---|---|
| 1 | 项目 | 14,000 | title/subtitle/synopsis/canon/outline/style/author |
| 2 | Hard Canon | 22,000 | `canon_facts`（scope=canon、status=active） |
| 3 | 人物/地点/势力/物品等 Canon | 22,000 | `entities` |
| 4 | 关系与事件 | 22,000 | `relationships` + `events`（dynamic + canon） |
| 5 | 人物认知与人物弧线 | 18,000 | `character_knowledge` + `character_arcs` |
| 6 | 未回收伏笔 | 14,000 | `foreshadows`（status=open） |
| 7 | 作者意图 | 10,000 | `author_intents` |
| 8 | 中长期摘要 | `summary_char_budget`（36,000） | `summaries`（range_end < 当前章） |
| 9 | 最近至少 N 章已确认原文 | `recent_chapter_char_budget`（60,000） | `recent_chapters`，N = `review_count`（最小 1） |
| 10 | 当前章节记录 | 10,000 | `chapters` 当前行（含本章计划） |

超出单段上限时截断并追加 `…【截断】…`；整体超出 `context_char_budget` 再整体截断。

### 9.2 缓存友好设计（本版新增）

生成流水线的 `plan/writer/audit/extract/summary` **共用同一个 system prompt**（`SYSTEM_ENGINE`），各自的角色指令放在 user 消息的**末尾**：

```
system: 你是 NovelForge 的小说创作引擎……
user:   <大段 Context（各步骤完全一致）>
        【任务指令】<该步骤的角色提示词>
        【本章要求】/【章节蓝图】/【候选正文】……
```

由于 prefix（system + Context）在各步骤间完全一致，可以命中 DeepSeek 的上下文缓存。详见第 20 章。

其他功能（`initializer` / `assistant` / `setting_extract` / `rewrite_full` / `rewrite_local` / `impact` / `style`）仍使用各自的 system 提示词。

### 9.3 Context Inspector

小说工作台的【AI Context】页签、AI 助手结果页的【Context】页签，展示的就是这份打包结果——**排查"AI 为什么没遵守某设定"时先看这里**。

---

## 10. 数据模型

每个项目是一个目录，核心是一个 SQLite 文件：`<项目目录>/project.sqlite3`（WAL 模式）。

### 10.1 数据表

| 表 | 层级 | 说明 |
|---|---|---|
| `meta` | 元数据 | 键值对（书名、作者、总章节数、初始化状态、`prompt:*` 覆盖、`active_branch_id` 等） |
| `volumes` | 结构 | 卷（number / title / synopsis） |
| `chapters` | 正文 | 章节（number / volume_number / title / plan / content / status / current_revision / word_count / stale / pov_character / perspective / tense） |
| `chapter_revisions` | 历史 | 全量版本快照（含 plan / status / POV / 人称 / 时态），分支切换据此恢复 |
| `canon_facts` | Canon | 长期正式设定（category / name / content / lock_level / scope / status / source） |
| `entities` | Canon | 人物、势力、种族、地点、物品、能力等（kind / name / aliases / description / data） |
| `relationships` | 动态 | 关系（source_name / target_name / relation / strength / note / scope） |
| `events` | 动态 | 时间线事件（chapter_number / event_time / title / description / importance / tags） |
| `foreshadows` | Canon | 伏笔（code / introduced_chapter / target_chapter / status / importance / lifecycle / last_touched_chapter） |
| `summaries` | 派生 | 章节摘要（range_start / range_end / summary / level） |
| `character_knowledge` | 动态 | 角色认知（character_name / fact / knowledge_type / certainty / source_chapter） |
| `character_arcs` | 动态 | 人物弧线（stage / desire / fear / belief / conflict / transformation / next_stage / trigger_event） |
| `author_intents` | 意图 | 作者意图（scope_type / scope_key / title / content / priority / hard） |
| `state_updates` | 动态 | 已应用的状态变更流水（用于重建） |
| `state_proposals` | 待审核 | AI 状态提取提案（payload / reason / status） |
| `setting_proposals` | 历史 | 设定提取历史（payload / status） |
| `branches` | 分支 | 分支（name / parent_branch_id / base_chapter / status / description） |
| `branch_chapters` | 分支 | 分支内容指针（branch_id / chapter_number / source_revision） |
| `snapshots` | 快照 | 项目快照（label / chapter_number / payload） |
| `audit_issues` | 检查 | 审校与规则问题（severity / issue_type / message / location / references / resolved） |
| `jobs` | 任务 | AI 任务记录（kind / status / progress / stage / detail / usage / result） |
| `logs` | 日志 | 运行日志（level / event / message / detail） |
| `style_profiles` | 文风 | 单条 Style Profile（id 固定为 1） |

> 注意：`scenes` 表在 2.4 已被移除。**旧项目的数据库里该表会保留但不再使用**（`CREATE TABLE IF NOT EXISTS` 不会删除已有表），不影响运行。

### 10.2 版本与迁移

`database.py` 中 `SCHEMA_VERSION = 14`。启动时先 `executescript(SCHEMA)`（全部 `CREATE TABLE IF NOT EXISTS`），再执行 `migrate()` 补齐历史版本缺失的列，并确保存在 id=1 的"主线"分支。

因此**用新版本打开旧项目是安全的**：新列会被自动 `ALTER TABLE` 补上。

---

## 11. 分支（多结局）机制

### 11.1 心智模型

`chapters` 表**永远保存"当前激活分支"的工作视图**，而不是所有分支的内容。各分支的内容由 `chapter_revisions`（版本快照）+ `branch_chapters`（指针）共同决定。

```
chapters 表 ──── 当前分支的工作视图（界面、生成、导出都看这张表）
      ▲
      │ 切换时按指针恢复
      │
branch_chapters(branch_id, chapter_number, source_revision)  ──►  chapter_revisions
```

### 11.2 指针规则

- **保存章节**时：把新 revision 记录到**当前分支**的指针上。
- **切换分支**时：
  1. 先把 `chapters` 表当前内容记回**原分支**的指针——
     - 若原分支是主线且主线指针缺失，则补记（兼容旧项目）；
     - 若原分支是非主线，则**只记录与主线不一致的章节**（说明该分支确实改过）；
  2. 再按**目标分支**的指针恢复各章；目标分支没有指针的章节**回退到主线指针**；
  3. 目标分支下既无指针、又无可用 revision 的章节，**恢复为计划态空章**（防止其它分支的新建/改写内容泄漏进来）。

结果就是：**分支上没动过的章节一直跟随主线的最新内容；一旦动过，就只在当前分支生效。**

### 11.3 使用方式

**项目工具 → 分支管理**：

- **新建分支**：输入名称与"基础章节"（记录分叉点，仅作说明用途）。
- **切换到选中**：切换前会自动保存快照。
- **删除分支**：主线（id=1）不可删除；当前分支需先切换走才能删除。

侧栏顶部会显示当前分支名。新建分支时、切换分支前都会自动保存项目快照。

> 旧项目首次打开时会自动补记主线指针（`save_branch` / `switch_branch` 中的兜底逻辑）。

---

## 12. 快照与恢复

### 12.1 何时自动快照

| 时机 | 标签 |
|---|---|
| 项目创建 | `项目创建` |
| 确认项目设定 | `确认项目设定` |
| 确认章节 | `确认第N章` |
| AI 生成候选 | `AI候选第N章` |
| AI 助手添加设定 | `AI助手添加设定` |
| 设定提取确认 | `第N章设定提取确认` |
| 重建剧情状态 | `重建剧情状态` |
| 新建分支 / 切换分支前 | `新建分支 X` / `切换分支前 X` |
| 执行快照恢复前 | `恢复前自动备份` |

### 12.2 快照内容

`full_state()` 导出：`meta`、`chapters`、`canon_facts`、`entities`、`relationships`、`events`、`foreshadows`、`summaries`、`knowledge`、`arcs`、`intents`、`style`。

### 12.3 查看与恢复

**项目工具 → 项目快照**：左侧列表（ID / 标签 / 相关章节 / 创建时间），选中后下方显示该快照的完整 JSON。点【从选中快照恢复】会：

1. 先自动保存一份"恢复前自动备份"；
2. 逐章 `save_chapter` 写回（**产生新 revision，不覆盖历史**）；
3. 清空并重灌 Canon、实体、关系、事件、伏笔、摘要、认知、弧线、作者意图、文风；
4. 恢复 `meta`（`schema_version` 与 `active_branch_id` 除外）；
5. 再写一条 `从快照恢复` 快照并记录日志。

> 恢复是**破坏性**操作，会覆盖当前内容（但可通过"恢复前自动备份"再回退）。

---

## 13. 修改安全模型

### 13.1 白名单操作引擎

`OperationEngine`（`manager.py`）是唯一的结构化写入通道。允许的操作：

```
set_meta, create_canon_fact, update_canon_fact, delete_canon_fact,
create_entity, update_entity, delete_entity,
create_relationship, create_event, create_foreshadow,
set_intent, set_style, replace_text, mark_stale, create_snapshot
```

- **高风险操作**（`delete_canon_fact`、`delete_entity`）必须显式传 `allow_destructive=True`，否则抛 `PermissionError`。
- `replace_text` 要求目标文本**在章内唯一匹配**，否则拒绝修改。
- 一次应用成功后会自动保存快照 `用户确认 AI 修改`。
- `preview()` 可在执行前生成人类可读的操作清单（含原因、置信度、冲突、待确认问题）。

### 13.2 分层确认

| 阶段 | 数据状态 | 谁能推进 |
|---|---|---|
| 项目初始化 | `scope='draft'` | 作者点【确认项目设定】 |
| 章节正文 | `generated` | 作者点【确认章节】 |
| 状态提取 | `state_proposals` 等待中 | 作者在【状态提案】接受 |
| 设定提取 | 候选清单 | 作者勾选后【加入 Canon】 |
| 重写 | Diff 预览 | 作者【接受修改】 |

---

## 14. 导入与导出

### 14.1 备份（`.novelforge`）

**文件 → 备份项目**（`Ctrl+Shift+B`）把项目目录打包成 zip（排除 `backups/` 与 `__pycache__`），存到 `<项目>/backups/backup_<ISO时间>.novelforge`。

### 14.2 导入

| 入口 | 行为 |
|---|---|
| **文件 → 导入备份(.novelforge)** | 选备份文件 → 选目标目录 → 解压并打开（含 zip-slip 路径校验） |
| **文件 → 导入 JSON** | 选 JSON → 选目标目录 → 重建项目（章节、Canon、实体、关系、事件、伏笔、摘要、认知、弧线、意图、文风、meta） |

### 14.3 导出

| 格式 | 说明 |
|---|---|
| **TXT** | 书名 + 各章"第N章 标题" + 正文 |
| **Markdown** | 书名作 `#`，章作 `##` |
| **JSON** | `full_state()` 全量导出（可用于导入） |
| **EPUB** | EPUB 3.0。可选**仅导出已确认章节**；可选 PNG/JPG/JPEG 封面；含 nav.xhtml 目录、style.css、正确的 mimetype（未压缩存储） |

---

## 15. 运行日志与任务中心

### 15.1 运行日志

`logs` 表记录关键事件，**项目工具 → 运行日志** 可查看最近 300 条（时间 / 级别 / 事件 / 消息 / 详情）。

已埋点的事件：`open_project`、`create_project`、`backup`、`export`、`confirm_chapter`、`task_finish`（成功 info / 失败 error）、`switch_branch`、`delete_branch`、`import`、`snapshot_restore`。

### 15.2 任务与进度

- **全局进度面板**（顶部）：7 段步骤指示（准备/理解/规划/执行/检查/提交/完成）+ 百分比 + 阶段 + 详情 + 【取消任务】。
- **任务中心**（侧栏 🔔 或项目工具）：回看最近任务（任务/状态/进度/阶段/开始/结束）。
- **完成通知**：音效 + 系统托盘通知 + 任务栏闪烁。

### 15.3 通知配置

- 音效：Windows 用 `winsound`（异步），其它平台用 `QSoundEffect`，失败回退 `QApplication.beep()`。
- 音频文件：`assets/sounds/completed.wav`、`confirm.wav`、`error.wav`、`cancelled.wav`。
- 系统通知：系统托盘可用时通过 `QSystemTrayIcon.showMessage` 发送。

### 15.4 取消与重试

- 每次 AI 调用前检查取消标志；重试的退避等待期间也可取消（避免 UI 僵死）。
- 单个任务运行期间会阻止启动新任务（提示"已有 AI 任务运行中"）。
- API 失败按 `retry_times`（默认 3）重试。

---

## 16. 全部设置项

配置文件：**`~/.novelforge/config.json`**（首次保存时自动创建）。

### 16.1 可在界面（项目 → AI 设置）修改

| 界面字段 | 配置键 | 默认值 | 说明 |
|---|---|---|---|
| API Key | `api_key` | `''` | DeepSeek API Key |
| Base URL | `base_url` | `https://api.deepseek.com` | — |
| Model | `model` | `deepseek-flash` | 也可填 `deepseek-v4-pro` |
| Thinking | `thinking` | `True` | 是否开启思考模式 |
| Reasoning effort | `reasoning_effort` | `high` | `low` / `high` / `max` |
| Max output tokens | `max_tokens` | `24000` | 单次调用输出上限（含推理 token），范围 1~393216 |
| 前文最少回顾章数 | `review_count` | `1` | 代码强制最小 1 |
| Context 字符预算 | `context_char_budget` | `140000` | 打包后总上限 |
| 生成后自动 AI 审校 | `auto_audit` | `True` | 控制流水线第 ③ 步 |
| 生成后自动状态提取 | `auto_extract` | `True` | 控制第 ④ 步 |
| 重要操作自动备份 | `auto_backup` | `True` | — |
| 任务完成音效 | `notify_sound` | `True` | — |
| 系统任务通知 | `notify_system` | `True` | — |
| 通知音量 | `notify_volume` | `0.7` | 0~1 |

### 16.2 仅存在于配置文件（界面暂未暴露）

| 配置键 | 默认值 | 说明 |
|---|---|---|
| `temperature` | `0.75` | **仅在非思考模式生效**（思考模式下会被忽略） |
| `top_p` | `1.0` | 思考模式生效范围被钳制到 0.95~1.0 |
| `recent_chapter_char_budget` | `60000` | 「最近 N 章已确认原文」段落上限 |
| `summary_char_budget` | `36000` | 「中长期摘要」段落上限 |
| `auto_summary` | `True` | 流水线第 ⑤ 步（界面无开关，如需关闭请改配置文件） |
| `auto_save_seconds` | `8` | 编辑器自动保存间隔（秒） |
| `retry_times` | `3` | API 重试次数 |
| `timeout_seconds` | `180` | 单次请求超时 |
| `strict_fact_check` | `True` | 预留开关 |
| `health_check_after_confirm` | `True` | 预留开关 |
| `last_project` | `''` | 上次打开的项目路径（启动时自动打开） |

> 改配置文件后需重启程序生效。

---

## 17. 目录结构

```
NovelForge_2.4/
├─ main.py                    # 入口：from novelforge.ui import run_app
├─ requirements.txt
├─ run_windows.bat            # 安装依赖 + 启动
├─ build_windows.bat          # PyInstaller 打包
├─ README.md
├─ assets/
│  └─ sounds/                 # completed / confirm / error / cancelled .wav
├─ docs/
│  ├─ ARCHITECTURE.md
│  └─ USER_GUIDE.md
├─ novelforge/
│  ├─ __init__.py             # __version__
│  ├─ config.py               # AppConfig（~/.novelforge/config.json）
│  ├─ database.py             # SCHEMA + ProjectDB（全部读写方法）
│  ├─ project.py              # Project 创建/备份/导入 + restore_full_state
│  ├─ api.py                  # DeepSeekClient（请求组装、重试、JSON 解析）
│  ├─ prompts.py              # DEFAULT_PROMPTS + SYSTEM_ENGINE + PromptBuilder
│  ├─ context.py              # ContextEngine（上下文打包与预算）
│  ├─ manager.py              # OperationEngine（白名单写入引擎）
│  ├─ state.py                # StateManager（提案审核 / 动态状态重建）
│  ├─ checker.py              # 本地规则检查
│  ├─ exporter.py             # TXT / Markdown / JSON / EPUB 导出
│  ├─ notification.py         # 音效 + 系统通知
│  └─ ui.py                   # 全部界面、对话框、主窗口、任务线程
└─ tests/
   ├─ conftest.py             # 把项目根加入 sys.path
   └─ test_core.py            # 19 个核心用例
```

### 17.1 项目目录布局（运行时生成）

```
<你的项目目录>/
├─ project.sqlite3            # 主数据库（WAL）
├─ project.sqlite3-wal
├─ project.sqlite3-shm
├─ backups/                   # .novelforge 备份
├─ exports/                   # 默认导出位置
├─ assets/                    # 封面等素材
└─ logs/                      # 预留目录
```

---

## 18. 测试

```bash
python -m pytest tests/ -q
```

`tests/test_core.py` 当前共 **19 个用例**：

| # | 用例 | 覆盖点 |
|---|---|---|
| 1 | `test_project_creation_and_draft_population` | 建项 → draft 写入 → 晋升 Canon |
| 2 | `test_real_mutation_updates_entity_and_original_text` | 结构化改写实体 + 唯一匹配文本替换 + revision |
| 3 | `test_context_pack_without_scenes` | 上下文打包（且确认已无 Scene 段） |
| 4 | `test_setting_extract_prompt_exists_and_classifies_long_term_settings` | 设定提取提示词约束 |
| 5 | `test_rewrite_prompts_keep_modes_separate` | 两种重写模式互不混淆 |
| 6 | `test_api_thinking_payload_matches_current_config_contract` | 思考模式请求体契约 |
| 7 | `test_state_rebuild_clears_dynamic_foreshadows` | 动态状态重建 |
| 8 | `test_epub_cover_and_exports` | EPUB（mimetype / 仅已确认 / 封面）+ TXT/MD/JSON |
| 9 | `test_manual_canon_setting_crud` | Canon 增删改查 |
| 10 | `test_assistant_can_return_setting_candidates_without_claiming_direct_write` | 助手不越权 |
| 11 | `test_config_has_last_project_field` | `last_project` 字段 |
| 12 | `test_save_log_and_read` | 运行日志 |
| 13 | `test_volume_rename_and_intent_delete` | 卷重命名 / 意图删除 |
| 14 | `test_search_finds_chapter_and_canon` | 全文搜索 |
| 15 | `test_branch_switch_isolates_content` | 分支内容隔离 |
| 16 | `test_branch_new_chapter_not_leaked_to_main` | 分支新章不泄漏到主线 |
| 17 | `test_snapshot_restore` | 快照恢复 |
| 18 | `test_checker_ignores_dialogue_first_person` | 规则检查不误判对白 |
| 19 | `test_revision_snapshot_keeps_plan_and_status` | revision 保存计划/状态/POV |

> 测试全部使用 `tmp_path` 临时目录，不会污染真实项目。

---

## 19. 构建与打包

### 19.1 Windows 打包

双击 `build_windows.bat`，等价于：

```bat
py -m pip install -r requirements.txt
py -m pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --name NovelForge --add-data "assets;assets" main.py
```

产物在 `dist/NovelForge/`。注意 `--add-data` 把音效资源一起打包——`notification.py` 通过 `Path(__file__).parents[1]/'assets'/'sounds'` 定位音效目录。

### 19.2 其它平台

```bash
python -m pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --name NovelForge --add-data "assets:assets" main.py
```

（注意 Linux/macOS 的 `--add-data` 分隔符是 `:`。）

---

## 20. DeepSeek 配置与成本提示

### 20.1 官方单价（元 / 百万 token）

参考 [DeepSeek 官方定价页](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)：

| | 输入·缓存命中 | 输入·缓存未命中 | 输出 |
|---|---|---|---|
| `deepseek-v4-pro` 空闲 | ¥0.15 | ¥4.5 | ¥13.5 |
| `deepseek-v4-pro` 高峰 | ¥0.30 | ¥9.0 | ¥27.0 |
| `deepseek-flash` 空闲 | ¥0.02 | ¥1 | ¥4 |
| `deepseek-flash` 高峰 | ¥0.04 | ¥2 | ¥8 |

- **高峰时段**：北京时间周一至周五 9:00–12:00、14:00–18:00（不含法定节假日）；**其余时间全部半价**。
- 思考模式的**推理 token 计入 `completion_tokens`**，因此既计费、也占用 `max_tokens`。
- 中文 ≈ **0.6 token / 字**。

### 20.2 本项目的成本设计

- **上下文缓存友好**：如第 9.2 节所述，生成流水线各步骤共享同一个 `system + Context` 前缀，可命中缓存，输入单价从 ¥4.5/M 降到 ¥0.15/M。
- **想要更省**：把 `reasoning_effort` 调到 `low`、或关闭 Thinking；关闭 `auto_audit` / `auto_extract` / `auto_summary`（后两者需改配置文件）；批量任务放在**空闲时段**运行。

### 20.3 想要每章更长？

1. **Max output tokens** 从 `24000` 提到 `48000`（`max_tokens` 同时是稳定性保障——太小会导致 JSON 被截断、解析失败）。
2. 适当降低 `reasoning_effort`，把配额留给正文。
3. 在【本章计划】或生成时的【本次额外要求】里写明目标字数，例如：
   > 本章正文不少于 4000 字。必须写足场景过程、对白、动作与细节，不得用概述带过。

### 20.4 请求体契约

`api.py` 组装的实际请求：

```jsonc
// 思考模式
{
  "model": "deepseek-flash",
  "messages": [{"role":"system","content":"..."},{"role":"user","content":"..."}],
  "stream": false,
  "max_tokens": 24000,
  "response_format": {"type": "json_object"},     // 仅 JSON 模式
  "reasoning_effort": "high",
  "extra_body": {"thinking": {"type": "enabled"}},
  "top_p": 1.0                                     // 被钳制到 >= 0.95
}

// 非思考模式
{
  "model": "deepseek-flash",
  "messages": [...],
  "stream": false,
  "max_tokens": 24000,
  "extra_body": {"thinking": {"type": "disabled"}},
  "temperature": 0.75,
  "top_p": 1.0
}
```

`parse_json()` 具备容错：先尝试直接解析，再尝试提取 ` ```json ` 代码块，最后尝试截取首个 `{...}` / `[...]`。

---

## 21. 常见问题

**Q：生成章节报 `'PromptBuilder' object has no attribute 'get'`？**
这是 2.4 早期版本的缺陷，已修复（`prompt()` 取代误写的 `get()`）。请使用当前版本。

**Q：保存章节报 `Incorrect number of bindings supplied`？**
`branch_chapters` 插入语句的参数数量缺陷，已修复。

**Q：我在【本章计划】里写的要求 AI 没照做？**
2.4 早期版本的计划文本没有进入生成流程，已修复。现在若仍未生效，请检查：① 是否选中了正确的章节；② 打开【AI Context】页签确认计划文本确实出现在上下文中。

**Q：AI 老是不按我的设定写？**
按优先级排查：
1. 【AI Context】里该设定是否真的存在——不存在就先在世界工作区补 Canon；
2. 该设定是否为 `hard` 锁定级别；
3. Context 是否因超预算被整体截断（调大 `context_char_budget`）；
4. 用【设定影响分析】确认没有冲突；
5. 用【AI重写】或【设定提取】修正。

**Q：章节太短 / 被截断？**
见 20.3。核心是提高 `max_tokens`。

**Q：程序启动报错或界面空白？**
先确认 PySide6 已安装（`python -m pip install -r requirements.txt`）。若为源码运行，注意 `assets/sounds` 需与 `novelforge/` 同级。

**Q：想换模型？**
AI 设置 → Model，可填 `deepseek-flash`（快、便宜）或 `deepseek-v4-pro`（强、贵）。

**Q：旧项目能用吗？**
可以。启动时会自动迁移补齐新列，并补建"主线"分支兜底。旧库里的 `scenes` 表会保留但不再使用。

**Q：AI 任务卡住了？**
点进度面板的【取消任务】；重试退避期间也能取消。超时由 `timeout_seconds`（默认 180 秒）控制。

---

## 22. 已知限制

- **文档滞后**：`docs/USER_GUIDE.md` 与 `docs/ARCHITECTURE.md` 仍包含 2.4 已移除的 Scene 描述，尚未同步。
- **动态状态是全局的**：分支（多结局）目前只隔离**章节内容**，Canon 与动态状态（事件、认知、关系、伏笔）在所有分支间共享。
- **快照恢复覆盖范围**：只恢复快照中存在的章节；当前项目比快照多出的章节会保留原样。
- **`chapters.plan` 会被覆盖**：生成完成后，AI 产出的章节蓝图会写入该字段，覆盖作者手写原文（正文与历史版本仍可从 revision 找回）。
- **界面未暴露的设置**：`temperature`、`top_p`、`auto_summary`、检索与预算类参数需直接编辑 `~/.novelforge/config.json`。
- **单任务模型**：同一时间只能运行一个 AI 任务。
- **规则检查较简单**：仅 POV 泄漏、伏笔逾期、短语重复三类，误报请以 AI 审校为准。
- **无自动更新**：需手动替换程序文件。

---

## 附：帮助中心

除本文档外，程序内置**帮助与教程**（菜单栏"帮助"，或各工作区的 `?` 按钮），支持关键字搜索（Canon、进度、EPUB……），内容覆盖：快速开始、AI 助手、小说、项目初始化、AI 生成章节、Canon 与确认、影响分析、分支、快照与日志、导入与搜索、任务通知、检查、状态提案、人物与认知、时间线、伏笔、AI Context、项目设置、EPUB、帮助中心。
