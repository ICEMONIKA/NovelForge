# NovelForge 2.4

NovelForge 2.4 是自然语言优先的桌面长篇小说 IDE。它不再使用此前不稳定的“总管 Agent 自动执行”模式，而是采用 **AI 分析 + 明确工具 + 用户确认** 的可控流程。

核心流程：

`自然语言建项 → AI自动整理 → 工作区确认 → 章节标题/本章计划 → 前文交接 → Scene规划 → 正文 → AI审校 → 状态提取 → 作者确认`

核心 AI：

- 项目整理 AI：把一份自然语言资料整理成世界、人物、关系、时间线、伏笔、总纲、文风等。
- AI 助手：可查询和分析；当作者明确要求添加长期设定时，可以生成“添加设定”结果，点击“应用 AI 设定”后写入 Canon。
- Scene 规划 AI：正文之前建立 Scene Blueprint，正文之后保存 Scene 实际结果和偏差。
- 章节生成 AI：严格读取 Canon、故事状态和至少一章前文。
- 章节检查 AI：检查人物、时间线、Canon、知识边界、伏笔、Scene、POV、因果和文风。
- 设定提取 AI：从指定章节提取应该长期记住的新设定；逐条确认后加入 Canon。
- 重写 AI：完全重写 / 保证当前逻辑的局部重写，两种模式都先进入 Diff。
- 影响分析 AI：分析某个设定变化可能影响哪些章节和故事数据，但不自动修改。
- 状态提取 AI：从正文提取人物、关系、事件、知识和伏笔状态。

项目数据采用 Canon、动态状态、人物知识、时间线、伏笔、Scene、章节 revision 等分层存储。AI 的推测不会自动变成正式 Canon。

其他内置能力：启动时自动打开上次项目；多分支（多结局）写作与切换；重要操作自动快照、可浏览和恢复；全书全文搜索；导入 .novelforge 备份 / JSON；卷管理、文风 Profile 与作者意图直接编辑；运行日志；设定变更影响分析。

界面使用深色背景和亮色高亮。AI 长任务拥有全局醒目进度面板、完成音效、系统通知和任务中心。

## 运行

```bash
python -m pip install -r requirements.txt
python main.py
```

Windows 可双击 `run_windows.bat`；`build_windows.bat` 可以使用 PyInstaller 构建桌面程序。

## DeepSeek

默认 Base URL：`https://api.deepseek.com`

默认模型：`deepseek-flash`

API Key、模型、Thinking、Reasoning effort、输出长度、前文回顾等可以在“项目 → AI 设置”修改。
