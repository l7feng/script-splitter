# -*- coding: utf-8 -*-
"""前端选项纯数据注册表（不依赖 tkinter / Web 框架，CLI 与 GUI 共用）。

每项格式：(key, 显示名, 默认勾选)。
"""

# 外语语种：key 对齐 core.run 的 lang 取值
LANGS = [
    ('auto', '自动识别'),
    ('pt', '葡萄牙语'),
    ('en', '英语'),
]

# 导出格式：key 对齐 core.run 的 formats 取值
FORMATS = [
    ('csv', '三栏对照 CSV（集/场/角色/外语/中文）', True),
    ('zh_docx', '中文版 .docx（完整剧本，套排版模板）', False),
    ('foreign_docx', '外语版 .docx（台词本，上字幕用）', False),
    ('bilingual_docx', '双语对照版 .docx（中文 + 外语原文）', False),
    ('foreign_txt', '外语版 .txt', False),
    ('zh_txt', '中文版 .txt', False),
    ('srt', '外语台词 .srt（上字幕）', False),
    ('missing', '缺翻译清单 .txt', False),
    ('stats', '台词统计表 .csv（角色 / 分集）', False),
]

FORMAT_KEYS = [k for k, _, _ in FORMATS]
LANG_KEYS = [k for k, _ in LANGS]
