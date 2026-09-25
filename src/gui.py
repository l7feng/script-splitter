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

        self._build()
        if HAS_DND:
            self._enable_dnd()
        self._pump()

    # ---------------------------------------------------------------- UI
    def _build(self):
        pad = {'padx': 12, 'pady': 6}
        frm = ttk.Frame(self.root)
        frm.pack(fill='both', expand=True)

        # 文件选择
        box = ttk.LabelFrame(frm, text='剧本文件')
        box.pack(fill='x', **pad)
        row = ttk.Frame(box)
        row.pack(fill='x', padx=8, pady=8)
        ttk.Entry(row, textvariable=self.path_var).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='浏览…', command=self.browse).pack(side='left', padx=6)
        tip = '把 .docx 拖到窗口里即可' if HAS_DND else '（未安装拖拽支持，请点浏览）'
        ttk.Label(box, text=tip, foreground='#888780').pack(anchor='w', padx=10, pady=(0, 8))

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
        ttk.Button(r3, text='选择…', command=self.pick_out).pack(side='left', padx=6)

        # 运行
        r4 = ttk.Frame(frm)
        r4.pack(fill='x', padx=12, pady=4)
        self.btn = ttk.Button(r4, text='开始拆分', command=self.start)
        self.btn.pack(side='left')
        ttk.Button(r4, text='打开输出目录', command=self.open_out).pack(side='left', padx=6)
        self.prog = ttk.Progressbar(r4, mode='indeterminate')
        self.prog.pack(side='left', fill='x', expand=True, padx=10)

        # 日志
        lb = ttk.LabelFrame(frm, text='运行日志')
        lb.pack(fill='both', expand=True, **pad)
        self.log = tk.Text(lb, height=12, wrap='word', relief='flat')
        self.log.pack(fill='both', expand=True, padx=8, pady=8)
        self.log.configure(state='disabled')

    def _enable_dnd(self):
        try:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.on_drop)
        except Exception:
            pass

    def on_drop(self, event):
        p = event.data.strip().strip('{}')
        if p.lower().endswith('.docx'):
            self.path_var.set(p)
            self.out_var.set(self._default_out(p))
            self.log_line('已载入：%s' % p)
        else:
            messagebox.showwarning('格式不支持', '目前只支持 .docx 文件')

    # ---------------------------------------------------------------- 动作
    def _default_out(self, path):
        return os.path.join(os.path.dirname(path),
                            os.path.splitext(os.path.basename(path))[0] + '_split')

    def browse(self):
        p = filedialog.askopenfilename(title='选择剧本',
                                       filetypes=[('Word 文档', '*.docx'), ('所有文件', '*.*')])
        if p:
            self.path_var.set(p)
            self.out_var.set(self._default_out(p))

    def pick_out(self):
        d = filedialog.askdirectory(title='选择输出目录')
        if d:
            self.out_var.set(d)

    def log_line(self, s):
        self.log.configure(state='normal')
        self.log.insert('end', s + '\n')
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


def main():
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    app = App(root)
    # 也支持「把 .docx 拖到 exe 图标上」：Windows 会把路径塞进 argv
    dropped = [a for a in sys.argv[1:] if a.lower().endswith('.docx')]
    if dropped:
        app.path_var.set(dropped[0])
        app.out_var.set(app._default_out(dropped[0]))
        app.log_line('已载入：%s' % dropped[0])
    root.mainloop()


if __name__ == '__main__':
    main()
