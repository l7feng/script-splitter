# -*- coding: utf-8 -*-
"""script-splitter 共享视觉主题与设置持久化

只被 GUI 层引用；core 保持零 tkinter 依赖。

■ token 三层结构（2026-09-30 S1 重排，参考 pt-audio-toolkit 27 号 Token 三层设计表）
  第 1 层 primitive  PALETTES[mode]       色板原值——设计师选的原始值，改名=破坏兼容
  第 2 层 semantic   tokens()             语义键 → primitive 映射（唯一真相）
  第 3 层 component  setup_theme / make_button 等组件代码，只准消费语义层
  兼容红线：COLOR 扁平 dict 保留为 primitive 键别名（与语义键同值），
  gui.py 旧代码零改动照跑；tests/test_theme.py 断言别名同值。

■ 设计基线（2026-09-28 第三轮 · Claude 暖色像素风，S1 原值保留）
- 底主题 'clam'，全局浅色·米白暖调；按钮像素直角（tk.Button relief=solid）。
- 强调色可在 6 档预设间切换（THEME_ORDER），默认暖陶土。
- 运行设置持久化到 %APPDATA%/script-splitter/settings.json
"""
import json
import os
import tkinter as tk
from tkinter import ttk

# ---------------------------------------------------------------- 间距常量
PAD_X = 12          # 区块（LabelFrame）外边距
PAD_Y = 8
INNER_X = 8         # 区块内行/列边距
INNER_Y = 8

# ================================================================ 第 1 层 primitive
# 每套界面模式一块色板（2026-09-30 S2 起三套：warm / cool / night）。
# 键名即 primitive 键名，与旧 COLOR 键一一对应（改名=破坏兼容，禁止）。
PALETTES = {
    'warm': {
        'bg':          '#f5f2ec',  # 应用背景 暖米白
        'panel_bg':    '#faf8f3',  # 日志区底色（更浅暖白）
        'panel_fg':    '#3a352d',  # 日志文字
        'text':        '#2e2a24',  # 主文字 暖近黑
        'hint':        '#6f685e',  # 提示灰（S3 对比度修正 #8c857a→#6f685e，4.9:1 达 AA）
        'border':      '#e3ddd0',  # 边框 暖灰
        'entry_bg':    '#fffdf8',  # 输入框底 近白暖
        'btn':         '#ece7dd',  # 普通像素按钮底
        'btn_active':  '#ddd5c8',  # 普通按钮按下/悬停底
        'danger':      '#b4543e',  # 危险/不可逆 暖红
        'danger_active': '#9c4632',
        'ok':          '#477a4e',  # 成功/完成 暖绿（S3 加深，4.75:1 AA）
        'warn':        '#8f6516',  # 警告 暖黄（S3 加深，4.90:1 AA）
        'info':        '#3a6ea5',  # 信息 蓝
    },
    # 冷调浅（2026-09-30 S2）：窗底 ΔL(warm)=18.7、ΔR=29 —— 吃 34 号 D1 教训，
    # 初选 nord 底 #eceff4 与暖米白 ΔL 仅 3.6（切了像没切），故拉到明显冷灰蓝。
    'cool': {
        'bg':          '#d8e1ec',
        'panel_bg':    '#e6edf5',
        'panel_fg':    '#2f3640',
        'text':        '#2b3440',
        'hint':        '#4d5a68',
        'border':      '#c2cedd',
        'entry_bg':    '#f4f8fc',
        'btn':         '#ccd8e6',
        'btn_active':  '#b9c9db',
        'danger':      '#a8503f',
        'danger_active': '#8f4234',
        'ok':          '#35704a',
        'warn':        '#8a6315',
        'info':        '#3a6ea5',
    },
    # 暖夜深（2026-09-30 S2）：暖棕黑家族（非纯黑冷灰），对齐用户暖调审美；
    # 与 warm ΔL=213、与 cool ΔL=195，深浅互切一眼可辨。
    'night': {
        'bg':          '#201c18',
        'panel_bg':    '#262019',
        'panel_fg':    '#d8cfc2',
        'text':        '#ece5da',
        'hint':        '#a89c8d',
        'border':      '#3e372f',
        'entry_bg':    '#2b251f',
        'btn':         '#363029',
        'btn_active':  '#463e35',
        'danger':      '#d4706a',
        'danger_active': '#c05b55',
        'ok':          '#85b47a',
        'warn':        '#d9a441',
        'info':        '#8aa3c0',
    },
}
DEFAULT_MODE = 'warm'
MODE_ORDER = ['warm', 'cool', 'night']
MODE_LABELS = {'warm': '暖米白', 'cool': '冷调浅', 'night': '暖夜'}

# ================================================================ 第 2 层 semantic
# 语义键 → primitive 键映射（token 唯一真相表）。
# component 层（setup_theme / make_button）只准经 tokens() 取色，禁止直戳 PALETTES。
_SEMANTIC_MAP = {
    'surface.window':         'bg',
    'surface.log':            'panel_bg',
    'text.log':               'panel_fg',
    'text.primary':           'text',
    'text.hint':              'hint',
    'border.default':         'border',
    'surface.input':          'entry_bg',
    'surface.btn':            'btn',
    'surface.btn.active':     'btn_active',
    'feedback.danger':        'danger',
    'feedback.danger.hover':  'danger_active',
    'feedback.ok':            'ok',
    'feedback.warn':          'warn',
    'feedback.info':          'info',
}

# 当前生效模式（setup_theme 时刷新；COLOR 别名随之刷新）
_CURRENT_MODE = DEFAULT_MODE


def tokens(mode=None):
    """返回语义键 dict：{'text.primary': '#...', ...}。mode 缺省=当前生效模式。"""
    pal = PALETTES[mode or _CURRENT_MODE]
    return {sem: pal[prim] for sem, prim in _SEMANTIC_MAP.items()}


def _alias_color(mode):
    """COLOR 兼容别名：primitive 键 → 当前模式色值（与 tokens() 同值）。"""
    pal = PALETTES[mode]
    return dict(pal)


# ---------------------------------------------------------------- COLOR 兼容别名
# 旧代码（gui.py）继续按 COLOR['bg'] 式取值；setup_theme 每次刷新整表。
# 值永远 == tokens()[对应语义键]，tests/test_theme.py 断言同值防两套真相。
COLOR = _alias_color(DEFAULT_MODE)

# ---------------------------------------------------------------- 多套强调色预设（浅色底不变）
# 顺序即设置面板里的展示顺序；每项 = (key, 中文名, accent, accent_active, accent_text)
# 默认 DEFAULT_THEME='orange' 调成 Claude 暖陶土。
THEME_ORDER = [
    ('blue',   '蓝',   '#3a6ea5', '#2f5a89', '#ffffff'),
    ('cyan',   '青',   '#2f8f8f', '#267676', '#ffffff'),
    ('green',  '绿',   '#5a8a5f', '#487a4d', '#ffffff'),
    ('orange', '橙',   '#cc785c', '#b5674c', '#fffdf9'),   # Claude 暖陶土（默认）
    ('purple', '紫',   '#8a6fb0', '#745a99', '#ffffff'),
    ('red',    '红',   '#b4543e', '#9c4632', '#fffdf9'),
]
THEMES = {k: {'label': lbl, 'accent': a, 'accent_active': aa, 'accent_text': at}
          for k, lbl, a, aa, at in THEME_ORDER}
DEFAULT_THEME = 'orange'

# 当前生效的强调色（setup_theme 时刷新，供像素按钮取色）
_CURRENT = {
    'accent': THEMES[DEFAULT_THEME]['accent'],
    'accent_active': THEMES[DEFAULT_THEME]['accent_active'],
    'accent_text': THEMES[DEFAULT_THEME]['accent_text'],
}

# ---------------------------------------------------------------- 热刷新机制（S2）
# 像素按钮注册表：make_button 创建即登记，setup_theme 时全部热刷新；
# 控件销毁（如设置弹窗关闭）后下次刷新自动摘除。
_PIXEL_BUTTONS = []   # [(tk.Button, accent: bool), ...]
# palette hook：换模式后由 gui 层补刷 ttk 管不到的原生控件（日志 Text / 提示 Label 等）
_PALETTE_HOOKS = []


def register_palette_hook(fn):
    """登记一个换模式回调（重复登记忽略）。回调内自行判空（控件可能未建）。"""
    if fn not in _PALETTE_HOOKS:
        _PALETTE_HOOKS.append(fn)


def _restyle_registered_buttons():
    """setup_theme 后热刷新全部登记的像素按钮；死的摘除。"""
    tok = tokens()
    alive = []
    for w, accent in _PIXEL_BUTTONS:
        try:
            if not w.winfo_exists():
                continue
            alive.append((w, accent))
            if accent:
                restyle_accent_button(w)
            else:
                w.configure(bg=tok['surface.btn'], fg=tok['text.primary'],
                            activebackground=tok['surface.btn.active'],
                            activeforeground=tok['text.primary'])
        except Exception:
            pass
    _PIXEL_BUTTONS[:] = alive


def _fire_palette_hooks():
    for fn in tuple(_PALETTE_HOOKS):
        try:
            fn()
        except Exception:
            pass

# ---------------------------------------------------------------- 窗口几何
MIN_W, MIN_H = 900, 620
FIRST_MAX_W, FIRST_MAX_H = 1180, 842   # 首次自适应封顶（比例 ≈1.40，对齐 PT）

# ---------------------------------------------------------------- 设置持久化
DEFAULT_SETTINGS = {
    'theme': DEFAULT_THEME,
    'mode': DEFAULT_MODE,              # 界面模式（warm/cool/night）
    'topmost': False,                  # 窗口始终置顶
    'remember_options': True,          # 记住上次选项（语种/格式/排版）
    'auto_open_output': True,          # 完成后自动打开输出目录
    'default_output': '',              # 默认输出目录（空=与源文件同目录）
    'last_options': {                  # 记住的上次选项快照
        'lang': 'auto',
        'only_body': True,
        'strip_rev': True,
        'tpl': '',
        'beautify': True,
        'toc': True,
        'hf': True,
        'fmts': {},
    },
}


def _app_dir():
    base = os.environ.get('APPDATA') or os.path.expanduser('~')
    return os.path.join(base, 'script-splitter')


def _window_path():
    return os.path.join(_app_dir(), 'window.json')


def _settings_path():
    return os.path.join(_app_dir(), 'settings.json')


def load_settings():
    """读取设置并与默认值合并；非法 theme 回退默认。"""
    d = {k: v for k, v in DEFAULT_SETTINGS.items()}
    d['last_options'] = dict(DEFAULT_SETTINGS['last_options'])
    try:
        with open(_settings_path(), encoding='utf-8') as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            for k, v in saved.items():
                if k == 'last_options' and isinstance(v, dict):
                    d['last_options'].update(v)
                else:
                    d[k] = v
    except Exception:
        pass
    if d.get('theme') not in THEMES:
        d['theme'] = DEFAULT_THEME
    if d.get('mode') not in PALETTES:
        d['mode'] = DEFAULT_MODE
    return d


def save_settings(d):
    """写入设置（异常静默）。"""
    try:
        os.makedirs(_app_dir(), exist_ok=True)
        with open(_settings_path(), 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------- 主题样式（component 层）
def setup_theme(root, theme_name=DEFAULT_THEME, mode=None):
    """配置全局 ttk 暖底 + 记录当前强调色（供像素按钮取色）。

    theme_name 决定强调色；mode 决定色板（缺省=沿用当前模式）。
    component 层纪律：本函数只准经 tokens() 取色。
    """
    global _CURRENT, _CURRENT_MODE
    if mode is not None and mode in PALETTES:
        _CURRENT_MODE = mode
    mode = _CURRENT_MODE
    tok = tokens(mode)
    # ⚠ 就地更新而非重绑定：gui.py 是 `from theme import COLOR`（快照引用），
    #   重绑定会让旧引用永远停在 warm——S2 夜色目检实锤过这个坑。
    COLOR.clear()
    COLOR.update(_alias_color(mode))

    s = ttk.Style()
    try:
        s.theme_use('clam')
    except Exception:
        pass

    th = THEMES.get(theme_name, THEMES[DEFAULT_THEME])
    _CURRENT = {'accent': th['accent'],
                'accent_active': th['accent_active'],
                'accent_text': th['accent_text']}

    # 应用整体暖底
    try:
        root.configure(background=tok['surface.window'])
    except Exception:
        pass

    s.configure('TLabel', background=tok['surface.window'], foreground=tok['text.primary'])
    s.configure('TFrame', background=tok['surface.window'])
    # ⚠ 规范样式名是 TLabelframe（winfo_class 决定，小写 l）；
    #   曾误写 TLabelFrame（大写）= 幽灵样式名，配置静默不生效。
    s.configure('TLabelframe', background=tok['surface.window'], foreground=tok['text.primary'],
                bordercolor=tok['border.default'], relief='groove',
                lightcolor=tok['border.default'], darkcolor=tok['border.default'])
    s.configure('TLabelframe.Label', background=tok['surface.window'],
                foreground=tok['text.primary'])
    s.configure('TCheckbutton', background=tok['surface.window'],
                foreground=tok['text.primary'],
                indicatorbackground=tok['surface.input'],
                indicatorforeground=th['accent'])
    s.configure('TRadiobutton', background=tok['surface.window'],
                foreground=tok['text.primary'],
                indicatorbackground=tok['surface.input'],
                indicatorforeground=th['accent'])
    s.configure('TEntry', fieldbackground=tok['surface.input'],
                foreground=tok['text.primary'],
                insertcolor=tok['text.primary'], bordercolor=tok['border.default'])
    s.configure('TCombobox', fieldbackground=tok['surface.input'],
                foreground=tok['text.primary'])
    s.map('TCheckbutton', background=[('active', tok['surface.window'])],
          indicatorbackground=[('selected', th['accent'])])
    s.map('TRadiobutton', background=[('active', tok['surface.window'])],
          indicatorbackground=[('selected', th['accent'])])
    # S3 ①Entry focus 态：聚焦边框走强调色（clam 支持 bordercolor 状态映射）
    s.map('TEntry',
          bordercolor=[('focus', th['accent']), ('!focus', tok['border.default'])],
          lightcolor=[('focus', th['accent']), ('!focus', tok['border.default'])],
          darkcolor=[('focus', th['accent']), ('!focus', tok['border.default'])])
    # S3 ⑤进度条：直角像素风（槽=输入底色、条=强调色、无立体边）
    s.configure('Horizontal.TProgressbar',
                troughcolor=tok['surface.input'], background=th['accent'],
                bordercolor=tok['surface.window'],
                lightcolor=tok['surface.input'], darkcolor=tok['surface.input'],
                thickness=10)
    _restyle_registered_buttons()       # 热刷新登记过的像素按钮
    _fire_palette_hooks()               # gui 层补刷 ttk 管不到的原生控件
    return th


def current_mode():
    """当前生效的界面模式 key（供设置面板回显）。"""
    return _CURRENT_MODE


def _blend(c1, c2, t):
    """hex 混色：t=0 → c1，t=1 → c2。供禁用态派生色用。"""
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    return '#%02x%02x%02x' % (round(r1 + (r2 - r1) * t),
                              round(g1 + (g2 - g1) * t),
                              round(b1 + (b2 - b1) * t))


def make_button(master, text='', command=None, accent=False, **kw):
    """像素风直角按钮（取消圆润苹果按钮）。accent=True 用强调色填充。"""
    tok = tokens()
    if accent:
        bg = _CURRENT['accent']
        fg = _CURRENT['accent_text']
        abg = _CURRENT['accent_active']
        font = ('', 10, 'bold')
    else:
        bg = tok['surface.btn']
        fg = tok['text.primary']
        abg = tok['surface.btn.active']
        font = ('', 10)
    kw.setdefault('bg', bg)
    kw.setdefault('fg', fg)
    kw.setdefault('activebackground', abg)
    kw.setdefault('activeforeground', fg)
    # S3 ③禁用态：禁用时文字向底色混 55%，不再依赖系统默认的失控灰
    kw.setdefault('disabledforeground', _blend(fg, bg, 0.55))
    kw.setdefault('relief', 'solid')          # 直角硬边（像素风）
    kw.setdefault('borderwidth', 1)
    kw.setdefault('highlightthickness', 0)
    kw.setdefault('overrelief', 'solid')      # 悬停不变形
    kw.setdefault('padx', 12)
    kw.setdefault('pady', 5)
    kw.setdefault('cursor', 'hand2')
    kw.setdefault('font', font)
    btn = tk.Button(master, text=text, command=command, **kw)
    _PIXEL_BUTTONS.append((btn, accent))   # 登记进热刷新注册表
    return btn


def restyle_accent_button(widget):
    """主题切换时热刷新一个强调色像素按钮的配色。"""
    try:
        widget.configure(bg=_CURRENT['accent'],
                         fg=_CURRENT['accent_text'],
                         activebackground=_CURRENT['accent_active'],
                         activeforeground=_CURRENT['accent_text'])
    except Exception:
        pass


# ---------------------------------------------------------------- 窗口几何
def initial_geometry(root):
    """首次按屏幕自适应（封顶），之后使用记住的尺寸。统一 minsize。"""
    geom = None
    try:
        with open(_window_path(), encoding='utf-8') as f:
            geom = json.load(f).get('window')
    except Exception:
        pass

    if geom:
        try:
            root.geometry(geom)
        except Exception:
            geom = None

    if not geom:
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w = min(int(sw * 0.62), FIRST_MAX_W)
        h = min(int(sh * 0.78), FIRST_MAX_H)
        w = max(w, MIN_W)
        h = max(h, MIN_H)
        root.geometry('%dx%d' % (w, h))

    root.minsize(MIN_W, MIN_H)


def save_geometry(root):
    """关窗时写回当前尺寸。"""
    path = _window_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, encoding='utf-8') as f:
                d = json.load(f)
        except Exception:
            d = {}
        d['window'] = root.geometry()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
