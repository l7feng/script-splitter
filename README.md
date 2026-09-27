# script-splitter · 剧本双语拆分工具

从中外混排的 `.docx` 剧本中拆出**中文版**和**纯外语版**，并顺手把排版美化好。

> 痛点：短剧剪辑看剧本时，葡萄牙语（或英语）台词和中文翻译混排在同一份文档里，读起来跳来跳去很累。

- **中文版** = 场景 + 动作 + 中文台词 → 给剪辑 / 导演看剧情和情绪
- **外语版** = 角色 + 纯外语台词 → 给后期 / 字幕组上字幕

当前版本 **v0.2.0**（2026-09-26）。

## 特性

- **离线、零第三方依赖**：纯规则解析，不调任何模型。核心只用标准库 `zipfile` + `xml.etree`，直接改写 docx 的 XML，**完整保留原排版**。
- **清除「删减标注」痕迹**：删除线内容移除、`w:del` 移除、`w:ins` 提升为正文、清 `w:rPrChange`。
- **语种自动识别**：葡萄牙语 / 英语（特征词计分 + 整篇统计兜底）。
- **排版模板化**：`cn` 中文短剧阅读版 / `hollywood` 好莱坞标准格式。新增风格 = 加一个 dict，引擎不用动。
- **排版美化**：清空白行、字体字号行距分层、角色名加粗、每集分页符、Word 自动目录域、页眉剧名 + 页脚页码。

## 用法

### exe（推荐）

双击 `script-splitter.exe`（界面标题仍为中文「剧本双语拆分工具」），或把 `.docx` 拖到窗口 / exe 图标上 → 勾选导出格式 → 开始拆分。
输出目录默认与源文件同级的 `<文件名>_split\`。

### 命令行

```bash
python src/cli.py 剧本.docx                          # 默认导出三栏对照 CSV
python src/cli.py 剧本.docx -f csv,zh_docx,foreign_docx,bilingual_docx,missing,stats
python src/cli.py 剧本.docx -t hollywood             # 好莱坞排版模板
python src/cli.py *.docx --all --lang en             # 批量；处理整篇；指定英语
```

格式：`csv` / `zh_docx` / `foreign_docx` / `bilingual_docx` / `zh_txt` / `foreign_txt` / `srt` / `missing` / `stats`

## 目录

```
src/core.py      解析引擎：docx XML 读写、段落分类、对白拆解、语种识别
src/styles.py    排版模板注册表（cn / hollywood）
src/beautify.py  排版层：样式套用、清空白行、TOC 域、页边距、页眉页脚
src/cli.py       命令行入口
src/gui.py       图形界面（tkinter，支持拖拽）
tests/           结构校验 + GUI 冒烟测试
```

> 需求 / 方案 / 进度三份过程文档已移出仓库，收在个人知识库 `4-项目/14-剧本双语拆分工具/`；本仓库只保留代码与本说明。

**分层铁律**：`core.py` / `styles.py` / `beautify.py` 都不 import tkinter（保证 CLI 与无头环境可用）。

## 构建 exe

```bash
D:\My-Temporary\pt-build-env\Scripts\python.exe build_exe.py
```

需要 Python 3.12 + tkinter + PyInstaller（托管 Python 3.13 缺 tkinter，不要用）。

## 实测

样例 `《Falcão的90日新娘》删减标注版v6.docx`：**53 集 / 85 场 / 769 条对白 / 40 个角色**。

## 已知限制

- **srt 时间轴是占位轴**（每条 2 秒递增）——剧本 docx 本身没有时间码，需要带轴字幕才能对齐。
- 少数台词缺中文翻译时会标 `[待补中文]`，并单独导出缺翻译清单，不静默丢弃。
