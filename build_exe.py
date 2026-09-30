# -*- coding: utf-8 -*-
"""打包 GUI 为 exe（onedir 模式，启动快）

用法：用打包环境的 Python 直接跑（不要用 PowerShell 包装，会把 PyInstaller 的
stderr 当错误中断）：
    D:\\My-Temporary\\pt-build-env\\Scripts\\python.exe build_exe.py
"""
import datetime
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = r'D:\Ai-Files\Agent-Preset\build-env\Scripts\python.exe'
EXE_ROOT = r'D:\Ai-Files\Agent-Preset\exe'

with open(os.path.join(ROOT, 'VERSION'), encoding='utf-8') as f:
    VERSION = f.read().strip()
DATE = datetime.datetime.now().strftime('%Y%m%d')

DIST = os.path.join(EXE_ROOT, 'script-splitter-v%s-%s' % (VERSION, DATE))
WORK = os.path.join(ROOT, 'build', 'work')
SPEC = os.path.join(ROOT, 'build')

NAME = 'script-splitter'  # 2026-09-27 由「剧本双语拆分工具」改英文：上 GitHub 需全 ASCII；GUI 标题仍为中文
ENTRY = os.path.join(ROOT, 'src', 'gui.py')


def main():
    if not os.path.isfile(PY):
        print('[失败] 打包解释器不存在: %s' % PY)
        return 1
    os.makedirs(DIST, exist_ok=True)

    cmd = [
        PY, '-m', 'PyInstaller',
        '--noconfirm', '--clean',
        '--onedir', '--windowed',
        '--name', NAME,
        '--icon', os.path.join(ROOT, 'src', 'app.ico'),   # 复盘修复：exe 文件本体图标
        '--paths', os.path.join(ROOT, 'src'),
        '--hidden-import', 'core',
        '--hidden-import', 'styles',
        '--hidden-import', 'beautify',
        '--hidden-import', 'theme',
        '--hidden-import', 'tkinterdnd2',
        '--collect-data', 'tkinterdnd2',
        # 复盘修复：窗口 iconbitmap 依赖 app.ico 随包（冻结后 __file__ 在 _internal）
        '--add-data', os.path.join(ROOT, 'src', 'app.ico') + os.pathsep + '.',
        '--distpath', DIST,
        '--workpath', WORK,
        '--specpath', SPEC,
        ENTRY,
    ]
    print('打包命令:\n  %s\n' % ' '.join(cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        print('\n[失败] PyInstaller 退出码 %d' % r.returncode)
        return r.returncode

    exe = os.path.join(DIST, NAME, NAME + '.exe')
    print('\n完成: %s' % exe)
    print('存在: %s' % os.path.isfile(exe))
    return 0 if os.path.isfile(exe) else 1


if __name__ == '__main__':
    sys.exit(main())
