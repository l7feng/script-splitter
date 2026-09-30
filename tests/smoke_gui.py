# -*- coding: utf-8 -*-
"""GUI 冒烟测试：构建界面、走一遍控件，不实际执行拆分。

用打包环境的 Python 跑（托管 Python 3.13 没有 tkinter）：
    D:\\Ai-Files\\Agent-Preset\\pt-build-env\\Scripts\\python.exe tests\\smoke_gui.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))

import gui  # noqa: E402


def main():
    print('HAS_DND =', gui.HAS_DND)
    root = gui.TkinterDnD.Tk() if gui.HAS_DND else gui.tk.Tk()
    root.withdraw()                      # 不真的弹窗，只验证构建过程
    app = gui.App(root)
    root.update_idletasks()

    # 走一遍默认状态
    print('默认格式勾选:', {k: v.get() for k, v in app.fmt_vars.items()})
    assert app.fmt_vars['csv'].get() is True, 'CSV 必须默认勾选'
    assert app.only_body_var.get() is True, '默认只处理分集正文'
    assert app.strip_var.get() is True, '默认清除修订痕迹'
    assert app.lang_var.get() == 'auto', '默认自动识别语种'
    assert app.tpl_var.get() == 'cn', '默认中文短剧排版模板'
    assert app.beautify_var.get() and app.toc_var.get() and app.hf_var.get(), \
        '默认开启美化 / 目录 / 页眉页脚'
    assert 'bilingual_docx' in app.fmt_vars and 'missing' in app.fmt_vars \
        and 'stats' in app.fmt_vars, '新增三种导出格式必须出现在界面里'
    print('排版模板:', gui.TEMPLATES)

    # 模拟一次日志输出
    app.log_line('冒烟测试：日志控件正常')
    root.update_idletasks()

    # 设置面板构建冒烟（S2：界面模式 swatch 行 + 强调色 swatch 行）
    app._open_settings()
    dlgs = [w for w in root.winfo_children() if w.winfo_class() == 'Toplevel']
    assert dlgs, '设置面板必须能构建'
    for d in dlgs:
        d.destroy()
    root.update_idletasks()
    print('设置面板构建冒烟通过')

    # 模拟载入文件后的输出目录推导
    sample = r'D:\Ai-Files\\Agent-Preset\《Falcão的90日新娘》删减标注版v6.docx'
    out = app._default_out(sample)
    print('推导输出目录:', out)
    assert out.endswith('_split')

    root.destroy()
    print('GUI 冒烟测试通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
