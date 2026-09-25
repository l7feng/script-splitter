# -*- coding: utf-8 -*-
"""
排版样式模板库

新增一种排版风格 = 在 TEMPLATES 里注册一个 dict，无需改动引擎代码。

每个模板是一个 dict，键为「段落角色」：
    episode  集标题
    scene    场号（1-1 地点 内 日）
    meta     场景提示 / 人物 / 动作 等以「xxx：」开头的元信息行
    action   普通叙述与动作描写
    speaker  对白行里的角色名（对白行内单独加粗）
    dialogue 对白行里的台词
    foreign  双语对照版里紧跟中文的外语原文行
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StyleSpec:
    font_zh: str = '宋体'          # 中文字体（w:eastAsia）
    font_lat: str = 'Times New Roman'  # 西文字体（w:ascii / w:hAnsi）
    size: float = 12              # 字号（磅）
    bold: bool = False
    color: Optional[str] = None   # 如 '808080'
    align: str = 'left'           # left / center / right / both
    line: float = 1.5             # 行距倍数
    before: float = 0             # 段前（磅）
    after: float = 0              # 段后（磅）
    indent_left: float = 0        # 左缩进（英寸）
    indent_right: float = 0       # 右缩进（英寸）
    indent_first: float = 0       # 首行缩进（字符）
    space_between: bool = True    # 是否允许自动段间距
    page_break_before: bool = False
    all_caps: bool = False
    heading_level: int = 0        # >0 时对应用 Word Heading 级别（供目录使用）


def _cn(**kw):
    """中文短剧阅读版：左对齐，靠字号/加粗/间距分层"""
    base = dict(font_zh='宋体', font_lat='Times New Roman', size=12, line=1.5)
    base.update(kw)
    return StyleSpec(**base)


def _hw(**kw):
    """好莱坞标准格式：Courier 12 磅等宽，角色名居中，对白左右缩进"""
    base = dict(font_zh='宋体', font_lat='Courier New', size=12, line=1.0, align='left')
    base.update(kw)
    return StyleSpec(**base)


# 剧本标准页边距（英寸）：左 1.5 右 1.0 上下 1.0
HOLLYWOOD_MARGIN = dict(left=1.5, right=1.0, top=1.0, bottom=1.0)
CN_MARGIN = dict(left=1.0, right=1.0, top=1.0, bottom=1.0)


TEMPLATES = {
    'cn': {
        'label': '中文短剧阅读版',
        'margins': CN_MARGIN,
        'styles': {
            'episode': _cn(font_zh='黑体', size=18, bold=True, align='center',
                           line=2.0, before=24, after=12, page_break_before=True,
                           heading_level=1),
            'scene': _cn(font_zh='黑体', size=13, bold=True, before=14, after=6,
                         heading_level=2),
            'meta': _cn(size=12, before=4, after=4, color='555555'),
            'action': _cn(size=12, before=2, after=2, line=1.6, indent_first=2),
            'speaker': _cn(font_zh='黑体', size=12, bold=True),
            'dialogue': _cn(size=12, before=2, after=6, line=1.5),
            'foreign': _cn(size=10.5, color='808080', indent_left=0.3, after=6),
        },
    },
    'hollywood': {
        'label': '好莱坞标准格式',
        'margins': HOLLYWOOD_MARGIN,
        'styles': {
            'episode': _hw(font_zh='黑体', size=16, bold=True, align='center',
                           before=24, after=12, page_break_before=True, heading_level=1),
            'scene': _hw(bold=True, all_caps=True, before=12, after=12, heading_level=2),
            'meta': _hw(before=0, after=6),
            'action': _hw(before=0, after=12),
            'speaker': _hw(align='center', indent_left=2.0, all_caps=True),
            'dialogue': _hw(indent_left=1.0, indent_right=1.5, after=12),
            'foreign': _hw(size=10.5, color='808080', indent_left=1.2, after=12),
        },
    },
}


def get_template(key):
    return TEMPLATES.get(key) or TEMPLATES['cn']


def list_templates():
    """[(key, label), ...] —— 供 GUI 下拉/单选使用"""
    return [(k, v['label']) for k, v in TEMPLATES.items()]


def template_keys():
    """[key, ...] —— 供 CLI choices 使用"""
    return list(TEMPLATES.keys())


def template_label(key):
    return (TEMPLATES.get(key) or TEMPLATES['cn'])['label']
