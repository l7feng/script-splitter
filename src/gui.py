# -*- coding: utf-8 -*-
"""剧本双语拆分 · 图形界面（双击 exe 打开，支持拖拽 .docx 进来）"""
import os
import sys
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import run  # noqa: E402
from styles import list_templates  # noqa: E402
from theme import (setup_theme, initial_geometry, save_geometry, COLOR,
                   PAD_X, PAD_Y, INNER_X, INNER_Y,
                   THEMES, THEME_ORDER, PALETTES, MODE_ORDER, MODE_LABELS,
                   load_settings, save_settings,
                   DEFAULT_SETTINGS, DEFAULT_THEME, DEFAULT_MODE,
                   make_button, restyle_accent_button,
                   register_palette_hook)  # noqa: E402

VERSION = '0.2.0'

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

TEMPLATES = list_templates()

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except Exception:
    HAS_DND = False


class App:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.busy = False
        self._last_out_dir = None
        self.settings = load_settings()
        root.title('剧本双语拆分工具 v%s' % VERSION)
        root.geometry('780x720')
        root.minsize(700, 660)

        self.path_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.lang_var = tk.StringVar(value='auto')
        self.only_body_var = tk.BooleanVar(value=True)
        self.strip_var = tk.BooleanVar(value=True)
        self.tpl_var = tk.StringVar(value=TEMPLATES[0][0])
        self.beautify_var = tk.BooleanVar(value=True)
        self.toc_var = tk.BooleanVar(value=True)
        self.hf_var = tk.BooleanVar(value=True)
        self.fmt_vars = {k: tk.BooleanVar(value=d) for k, _, d in FORMATS}

        # 记住上次选项：用持久化的上次选择覆盖默认
        if self.settings.get('remember_options'):
            lo = self.settings.get('last_options', {}) or {}
            self.lang_var.set(lo.get('lang', 'auto'))
            self.only_body_var.set(lo.get('only_body', True))
            self.strip_var.set(lo.get('strip_rev', True))
            tpl = lo.get('tpl') or TEMPLATES[0][0]
            if tpl not in [k for k, _ in TEMPLATES]:
                tpl = TEMPLATES[0][0]
            self.tpl_var.set(tpl)
            self.beautify_var.set(lo.get('beautify', True))
            self.toc_var.set(lo.get('toc', True))
            self.hf_var.set(lo.get('hf', True))
            saved_fmts = lo.get('fmts', {}) or {}
            for k in self.fmt_vars:
                self.fmt_vars[k].set(saved_fmts.get(k, self.fmt_vars[k].get()))

        # 应用主题强调色 + 界面模式 + 置顶
        # hook 先登记再 setup_theme：首建时日志控件尚未创建，回调内部自判空
        register_palette_hook(self._apply_palette)
        self._hint_labels = []
        setup_theme(self.root, self.settings.get('theme', DEFAULT_THEME),
                    mode=self.settings.get('mode', DEFAULT_MODE))
        try:
            self.root.attributes('-topmost', bool(self.settings.get('topmost')))
        except Exception:
            pass

        self._build()
        if HAS_DND:
            self._enable_dnd()
        self._pump()

    # ---------------------------------------------------------------- UI
    def _build(self):
        pad = {'padx': PAD_X, 'pady': PAD_Y}
        frm = ttk.Frame(self.root)
        frm.pack(fill='both', expand=True)

        # 文件选择
        box = ttk.LabelFrame(frm, text='剧本文件')
        box.pack(fill='x', **pad)
        row = ttk.Frame(box)
        row.pack(fill='x', padx=8, pady=8)
        ttk.Entry(row, textvariable=self.path_var).pack(side='left', fill='x', expand=True)
        make_button(row, text='浏览…', command=self.browse).pack(side='left', padx=6)
        tip = '把 .docx 拖到窗口里即可' if HAS_DND else '（未安装拖拽支持，请点浏览）'
        tip_lbl = ttk.Label(box, text=tip, foreground=COLOR['hint'])
        tip_lbl.pack(anchor='w', padx=10, pady=(0, 8))
        self._hint_labels.append(tip_lbl)

        # 选项
        opt = ttk.LabelFrame(frm, text='选项')
        opt.pack(fill='x', **pad)
        r1 = ttk.Frame(opt)
        r1.pack(fill='x', padx=8, pady=6)
        ttk.Label(r1, text='外语语种：').pack(side='left')
        for v, t in (('auto', '自动识别'), ('pt', '葡萄牙语'), ('en', '英语')):
            ttk.Radiobutton(r1, text=t, value=v, variable=self.lang_var).pack(side='left', padx=8)
        r2 = ttk.Frame(opt)
        r2.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Checkbutton(r2, text='只处理分集正文（跳过大纲 / 人物小传）',
                        variable=self.only_body_var).pack(side='left')
        ttk.Checkbutton(r2, text='清除删除线与修订痕迹',
                        variable=self.strip_var).pack(side='left', padx=16)

        # 排版
        tb = ttk.LabelFrame(frm, text='排版（作用于 docx）')
        tb.pack(fill='x', **pad)
        r5 = ttk.Frame(tb)
        r5.pack(fill='x', padx=8, pady=6)
        ttk.Label(r5, text='模板：').pack(side='left')
        for k, label in TEMPLATES:
            ttk.Radiobutton(r5, text=label, value=k, variable=self.tpl_var).pack(side='left', padx=8)
        r6 = ttk.Frame(tb)
        r6.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Checkbutton(r6, text='美化排版（清空行 / 字体字号 / 行距）',
                        variable=self.beautify_var).pack(side='left')
        ttk.Checkbutton(r6, text='插入目录（打开后 Ctrl+A 再 F9）',
                        variable=self.toc_var).pack(side='left', padx=14)
        ttk.Checkbutton(r6, text='页眉页脚（剧名 + 页码）',
                        variable=self.hf_var).pack(side='left')

        # 导出格式
        fb = ttk.LabelFrame(frm, text='导出格式（默认 CSV）')
        fb.pack(fill='x', **pad)
        g = ttk.Frame(fb)
        g.pack(fill='x', padx=8, pady=6)
        for i, (k, label, _d) in enumerate(FORMATS):
            ttk.Checkbutton(g, text=label, variable=self.fmt_vars[k]).grid(
                row=i // 2, column=i % 2, sticky='w', padx=6, pady=2)

        # 输出目录
        ob = ttk.LabelFrame(frm, text='输出目录')
        ob.pack(fill='x', **pad)
        r3 = ttk.Frame(ob)
        r3.pack(fill='x', padx=8, pady=8)
        ttk.Entry(r3, textvariable=self.out_var).pack(side='left', fill='x', expand=True)
        make_button(r3, text='选择…', command=self.pick_out).pack(side='left', padx=6)

        # 运行
        r4 = ttk.Frame(frm)
        r4.pack(fill='x', padx=12, pady=4)
        self.btn = make_button(r4, text='开始拆分', command=self.start, accent=True)
        self.btn.pack(side='left')
        make_button(r4, text='打开输出目录', command=self.open_out).pack(side='left', padx=6)
        self.prog = ttk.Progressbar(r4, mode='indeterminate')
        self.prog.pack(side='left', fill='x', expand=True, padx=10)
        make_button(r4, text='⚙ 设置', command=self._open_settings).pack(side='right', padx=6)

        # 日志
        lb = ttk.LabelFrame(frm, text='运行日志')
        lb.pack(fill='both', expand=True, **pad)
        self.log = tk.Text(lb, height=12, wrap='word', relief='flat',
                            background=COLOR['panel_bg'],
                            foreground=COLOR['panel_fg'])
        self.log.pack(fill='both', expand=True, padx=INNER_X, pady=INNER_Y)
        self.log.tag_configure('ok', foreground=COLOR['ok'])
        self.log.tag_configure('fail', foreground=COLOR['danger'])
        self.log.tag_configure('warn', foreground=COLOR['warn'])
        self.log.tag_configure('info', foreground=COLOR['info'])
        self.log.tag_configure('hint', foreground=COLOR['hint'], justify='center')
        self.log.configure(state='disabled')
        # S3 ②空态：启动时给引导占位文案（首条真日志到达时清除）
        self._log_placeholder = True
        self.log.configure(state='normal')
        self.log.insert('end', '—— 把 .docx 拖进窗口，或点「浏览…」选择剧本 ——\n', 'hint')
        self.log.configure(state='disabled')
        self._apply_palette()               # 建完后补刷一次（首建时 hook 曾跳过）

    def _apply_palette(self):
        """换界面模式后热刷新 ttk 管不到的原生控件（日志 Text / 提示 Label）。"""
        from theme import tokens
        tok = tokens()
        try:
            self.log.configure(background=tok['surface.log'],
                               foreground=tok['text.log'])
            self.log.tag_configure('ok', foreground=tok['feedback.ok'])
            self.log.tag_configure('fail', foreground=tok['feedback.danger'])
            self.log.tag_configure('warn', foreground=tok['feedback.warn'])
            self.log.tag_configure('info', foreground=tok['feedback.info'])
        except Exception:
            pass                      # 首建阶段日志控件可能尚未创建
        for w in getattr(self, '_hint_labels', []):
            try:
                w.configure(foreground=tok['text.hint'])
            except Exception:
                pass

    def _enable_dnd(self):
        try:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.on_drop)
        except Exception:
            pass

    def on_drop(self, event):
        p = event.data.strip().strip('{}')
        if p.lower().endswith('.docx'):
            self._on_file_chosen(p)
        else:
            messagebox.showwarning('格式不支持', '目前只支持 .docx 文件')

    # ---------------------------------------------------------------- 动作
    def _default_out(self, path):
        """与源文件同目录时的默认输出目录（兜底用）。"""
        return os.path.join(os.path.dirname(path),
                            os.path.splitext(os.path.basename(path))[0] + '_split')

    def _compute_out(self, src):
        """输出目录：设了默认输出目录则落在那里，否则与源文件同目录。"""
        do = (self.settings.get('default_output') or '').strip()
        stem = os.path.splitext(os.path.basename(src))[0] + '_split'
        if do:
            return os.path.join(do, stem)
        return os.path.join(os.path.dirname(src), stem)

    def _on_file_chosen(self, p):
        self.path_var.set(p)
        self.out_var.set(self._compute_out(p))
        self.log_line('已载入：%s' % p)

    def browse(self):
        p = filedialog.askopenfilename(title='选择剧本',
                                       filetypes=[('Word 文档', '*.docx'), ('所有文件', '*.*')])
        if p:
            self._on_file_chosen(p)

    def pick_out(self):
        d = filedialog.askdirectory(title='选择输出目录')
        if d:
            self.out_var.set(d)

    def log_line(self, s):
        # S3 ②空态：首条真日志到达时清掉占位文案
        if getattr(self, '_log_placeholder', False):
            self._log_placeholder = False
            self.log.delete('1.0', 'end')
        self.log.configure(state='normal')
        # S3 ④tag 路由补全：warn/info 色此前已定义但从未被用到
        if '失败' in s or s.startswith('[失败]'):
            tag = 'fail'
        elif '警告' in s or '跳过' in s:
            tag = 'warn'
        elif s.startswith('输出目录：'):
            tag = 'info'
        elif '完成' in s or s.startswith('——'):
            tag = 'ok'
        else:
            tag = ''
        self.log.insert('end', s + '\n', tag)
        self.log.see('end')
        self.log.configure(state='disabled')

    def _pump(self):
        """唯一的队列消费者：日志消息 + 结束信号都在这里处理"""
        try:
            while True:
                item = self.q.get_nowait()
                if item == '__DONE__':
                    self.busy = False
                    self.btn.configure(state='normal', text='开始拆分')
                    self.prog.stop()
                    if (self.settings.get('auto_open_output')
                            and self._last_out_dir
                            and os.path.isdir(self._last_out_dir)):
                        self.root.after(500, lambda: self._open_dir(self._last_out_dir))
                    continue
                self.log_line(item)
        except queue.Empty:
            pass
        self.root.after(120, self._pump)

    def start(self):
        if self.busy:
            return
        src = self.path_var.get().strip()
        if not src:
            messagebox.showinfo('提示', '请先选择或拖入一个 .docx 剧本')
            return
        if not os.path.isfile(src):
            messagebox.showerror('错误', '文件不存在：%s' % src)
            return
        fmts = [k for k, _l, _d in FORMATS if self.fmt_vars[k].get()]
        if not fmts:
            messagebox.showinfo('提示', '至少勾选一种导出格式')
            return
        self.busy = True
        self.btn.configure(state='disabled', text='处理中…')
        self.prog.start(12)
        out = self.out_var.get().strip() or None

        def work():
            try:
                outs, records, lang = run(
                    src, out_dir=out, formats=fmts,
                    only_body=self.only_body_var.get(),
                    strip_rev=self.strip_var.get(),
                    lang=self.lang_var.get(),
                    template=self.tpl_var.get(),
                    beautify=self.beautify_var.get(),
                    toc=self.toc_var.get(),
                    hf=self.hf_var.get(),
                    log=lambda s: self.q.put(s))
                if outs:
                    self._last_out_dir = os.path.dirname(outs[0])
                self.q.put('—— 完成 ——')
                for o in outs:
                    self.q.put('  %s' % o)
                self.q.put('输出目录：%s' % os.path.dirname(outs[0]))
                self.q.put('__DONE__')
            except Exception as e:
                self.q.put('[失败] %s: %s' % (type(e).__name__, e))
                self.q.put('__DONE__')

        threading.Thread(target=work, daemon=True).start()

    def open_out(self):
        d = self.out_var.get().strip()
        if d and os.path.isdir(d):
            os.startfile(d)

    def _open_dir(self, d):
        try:
            os.startfile(d)
        except Exception:
            pass

    # ---------------------------------------------------------------- 设置
    def _pick_dir(self, parent, var):
        d = filedialog.askdirectory(title='选择默认输出目录', parent=parent)
        if d:
            var.set(d)

    def _apply_default_output(self):
        """若还没选文件，把默认输出目录填进输出框。"""
        cur = (self.settings.get('default_output') or '').strip()
        if cur and not self.path_var.get().strip():
            self.out_var.set(cur)

    def _persist_options(self):
        """关窗时把当前选项写入设置（仅当开启记住）。"""
        if not self.settings.get('remember_options'):
            return
        self.settings['last_options'] = {
            'lang': self.lang_var.get(),
            'only_body': self.only_body_var.get(),
            'strip_rev': self.strip_var.get(),
            'tpl': self.tpl_var.get(),
            'beautify': self.beautify_var.get(),
            'toc': self.toc_var.get(),
            'hf': self.hf_var.get(),
            'fmts': {k: v.get() for k, v in self.fmt_vars.items()},
        }
        save_settings(self.settings)

    def _open_settings(self):
        """打开设置面板（Toplevel）。主题色实时预览，确定后持久化并热刷新。"""
        from tkinter import Toplevel
        from copy import deepcopy

        dlg = Toplevel(self.root)
        dlg.title('设置')
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.minsize(440, 400)
        try:
            dlg.attributes('-topmost', bool(self.settings.get('topmost')))
        except Exception:
            pass

        state = {'theme': self.settings.get('theme', DEFAULT_THEME),
                 'mode': self.settings.get('mode', DEFAULT_MODE)}
        cur = dict(self.settings)
        cur['last_options'] = dict(self.settings.get('last_options', {}))

        body = ttk.Frame(dlg, padding=(14, 12))
        body.pack(fill='both', expand=True)

        # —— 主题色 ——
        sf = ttk.LabelFrame(body, text='主题色（主按钮强调色）')
        sf.pack(fill='x', pady=(0, 10))
        row = ttk.Frame(sf)
        row.pack(fill='x', padx=8, pady=6)
        swatches = {}

        def highlight():
            for k, w in swatches.items():
                sel = (k == state['theme'])
                w.configure(relief='solid' if sel else 'flat',
                            borderwidth=3 if sel else 1,
                            highlightthickness=1 if sel else 0,
                            highlightbackground=COLOR['text'] if sel else COLOR['border'])

        def select(key):
            state['theme'] = key
            setup_theme(self.root, key, mode=state['mode'])   # 实时刷新主窗强调色
            restyle_accent_button(sample)      # 面板示例按钮同步预览
            highlight()

        for key, lbl, a, aa, at in THEME_ORDER:
            w = tk.Label(row, text=lbl, bg=a, fg=at, width=4,
                         relief='flat', borderwidth=1, highlightthickness=0,
                         cursor='hand2')
            w.pack(side='left', padx=4)
            w.bind('<Button-1>', lambda e, k=key: select(k))
            swatches[key] = w
        highlight()

        sample = make_button(sf, text='示例：开始拆分', accent=True)
        sample.pack(padx=8, pady=(2, 8))

        # —— 界面模式（S2 双轴之一：底色系）——
        mf = ttk.LabelFrame(body, text='界面模式（底色系，实时预览）')
        mf.pack(fill='x', pady=(0, 10))
        mrow = ttk.Frame(mf)
        mrow.pack(fill='x', padx=8, pady=6)
        mswatches = {}

        def highlight_mode():
            for k, w in mswatches.items():
                sel = (k == state['mode'])
                w.configure(relief='solid' if sel else 'flat',
                            borderwidth=3 if sel else 1,
                            highlightthickness=1 if sel else 0,
                            highlightbackground=COLOR['text'] if sel else COLOR['border'])

        def select_mode(key):
            state['mode'] = key
            setup_theme(self.root, state['theme'], mode=key)   # hook 自动热刷新
            highlight_mode()

        for key in MODE_ORDER:
            pal = PALETTES[key]
            w = tk.Label(mrow, text=MODE_LABELS.get(key, key),
                         bg=pal['bg'], fg=pal['text'], width=8,
                         relief='flat', borderwidth=1, highlightthickness=0,
                         cursor='hand2')
            w.pack(side='left', padx=4)
            w.bind('<Button-1>', lambda e, k=key: select_mode(k))
            mswatches[key] = w
        highlight_mode()

        # —— 默认输出目录 ——
        of = ttk.LabelFrame(body, text='默认输出目录（留空=与源文件同目录）')
        of.pack(fill='x', pady=(0, 10))
        orow = ttk.Frame(of)
        orow.pack(fill='x', padx=8, pady=8)
        out_var = tk.StringVar(value=cur.get('default_output') or '')
        ttk.Entry(orow, textvariable=out_var).pack(side='left', fill='x', expand=True)
        make_button(orow, text='选择…',
                   command=lambda: self._pick_dir(dlg, out_var)).pack(side='left', padx=6)

        # —— 行为开关 ——
        bf = ttk.LabelFrame(body, text='行为')
        bf.pack(fill='x', pady=(0, 4))
        top_var = tk.BooleanVar(value=bool(cur.get('topmost')))
        rem_var = tk.BooleanVar(value=bool(cur.get('remember_options')))
        aoo_var = tk.BooleanVar(value=bool(cur.get('auto_open_output')))
        ttk.Checkbutton(bf, text='窗口始终置顶', variable=top_var).pack(anchor='w', padx=8, pady=3)
        ttk.Checkbutton(bf, text='记住上次选项（语种 / 格式 / 排版）', variable=rem_var).pack(anchor='w', padx=8)
        ttk.Checkbutton(bf, text='完成后自动打开输出目录', variable=aoo_var).pack(anchor='w', padx=8, pady=3)

        # —— 底部按钮 ——
        btn_row = ttk.Frame(body)
        btn_row.pack(fill='x', pady=(12, 0))

        def on_ok():
            cur['theme'] = state['theme']
            cur['mode'] = state['mode']
            cur['topmost'] = top_var.get()
            cur['remember_options'] = rem_var.get()
            cur['auto_open_output'] = aoo_var.get()
            cur['default_output'] = out_var.get().strip()
            save_settings(cur)
            self.settings = cur
            setup_theme(self.root, cur['theme'], mode=cur['mode'])
            try:
                self.root.attributes('-topmost', bool(cur['topmost']))
            except Exception:
                pass
            self._apply_default_output()
            self.log_line('设置已保存')
            dlg.destroy()

        def on_reset():
            newd = deepcopy(DEFAULT_SETTINGS)
            cur.clear()
            cur.update(newd)
            cur['last_options'] = deepcopy(DEFAULT_SETTINGS['last_options'])
            state['theme'] = cur['theme']
            state['mode'] = cur.get('mode', DEFAULT_MODE)
            setup_theme(self.root, cur['theme'], mode=state['mode'])
            top_var.set(bool(cur['topmost']))
            rem_var.set(bool(cur['remember_options']))
            aoo_var.set(bool(cur['auto_open_output']))
            out_var.set(cur.get('default_output') or '')
            highlight()
            highlight_mode()
            self.log_line('已恢复默认设置（点确定生效）')

        make_button(btn_row, text='恢复默认', command=on_reset).pack(side='left')
        make_button(btn_row, text='取消', command=dlg.destroy).pack(side='right', padx=6)
        make_button(btn_row, text='确定', command=on_ok, accent=True).pack(side='right')


def main():
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    # S3 ⑧窗口图标（像素风 ico，生成脚本 tools/_gen_icon.py；缺失则静默跳过）
    try:
        root.iconbitmap(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.ico'))
    except Exception:
        pass
    app = App(root)
    # 也支持「把 .docx 拖到 exe 图标上」：Windows 会把路径塞进 argv
    dropped = [a for a in sys.argv[1:] if a.lower().endswith('.docx')]
    if dropped:
        app._on_file_chosen(dropped[0])
    initial_geometry(root)
    root.protocol('WM_DELETE_WINDOW',
                  lambda: (app._persist_options(), save_geometry(root), root.destroy()))
    root.mainloop()


if __name__ == '__main__':
    main()
