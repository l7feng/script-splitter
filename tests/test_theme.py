# -*- coding: utf-8 -*-
"""theme.py token 三层契约测试（S1 起，随阶段扩充）。

跑法（需带 tkinter 的 Python，托管 3.13 无 tkinter）：
    D:\\My-Temporary\\py312\\python.exe tests\\test_theme.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))

import theme  # noqa: E402

HEX_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


def test_semantic_keys_complete():
    """每套模式 tokens() 必须含全部语义键且为合法 hex。"""
    for mode in theme.MODE_ORDER:
        tok = theme.tokens(mode)
        missing = [k for k in theme._SEMANTIC_MAP if k not in tok]
        assert not missing, '%s 缺语义键: %s' % (mode, missing)
        for k, v in tok.items():
            assert HEX_RE.match(v), '%s.%s 非法色值: %r' % (mode, k, v)
    print('OK 语义键齐全且合法（%d 套模式 × %d 键）'
          % (len(theme.MODE_ORDER), len(theme._SEMANTIC_MAP)))


def test_alias_same_value():
    """兼容红线：COLOR 别名必须与 PALETTES 原值 / tokens() 同值。"""
    for mode in theme.MODE_ORDER:
        alias = theme._alias_color(mode)
        tok = theme.tokens(mode)
        for prim_key, hexval in theme.PALETTES[mode].items():
            assert alias[prim_key] == hexval, '%s COLOR[%s] 与色板不同值' % (mode, prim_key)
        for sem_key, prim_key in theme._SEMANTIC_MAP.items():
            assert alias[prim_key] == tok[sem_key], \
                '%s 别名[%s] 与语义键 %s 不同值' % (mode, prim_key, sem_key)
    print('OK COLOR 别名与语义键同值（防两套真相）')


def test_semantic_map_covers_palette():
    """映射表必须覆盖色板全部键：不留死键、不留孤儿 primitive。"""
    mapped = set(theme._SEMANTIC_MAP.values())
    for mode in theme.MODE_ORDER:
        pal_keys = set(theme.PALETTES[mode].keys())
        orphan = pal_keys - mapped
        dead = mapped - pal_keys
        assert not orphan, '%s 存在未被语义层引用的 primitive: %s' % (mode, orphan)
        assert not dead, '语义映射指向不存在的 primitive: %s' % (dead)
    print('OK 语义映射与色板一一对应')


def test_no_primitive_poke_in_component():
    """层级卫生：component 层源码禁止直戳 PALETTES（防回潮）。"""
    src = open(os.path.join(ROOT, 'src', 'theme.py'), encoding='utf-8').read()
    # 截取 component 区（setup_theme 起到文件尾），检查其中不出现 PALETTES[ 直引
    comp_zone = src[src.index('def setup_theme'):]
    assert 'PALETTES[' not in comp_zone, 'component 层出现 PALETTES[ 直引（应走 tokens()）'
    print('OK component 层无 primitive 直引')


def test_setup_theme_smoke():
    """真实构建一次 Style + 刷新别名（需 tkinter）。"""
    try:
        import tkinter as tk
    except ImportError:
        print('SKIP 本机无 tkinter，跳过 GUI 冒烟')
        return
    root = tk.Tk()
    root.withdraw()
    th = theme.setup_theme(root, 'orange', mode='warm')
    assert th['accent'] == theme.THEMES['orange']['accent']
    assert theme.COLOR['bg'] == theme.PALETTES['warm']['bg']
    assert theme.tokens()['surface.window'] == theme.COLOR['bg']
    assert theme.current_mode() == 'warm'
    btn = theme.make_button(root, text='t', accent=True)
    assert btn.cget('bg') == th['accent']
    root.destroy()
    print('OK setup_theme/make_button 真实构建')


def main():
    test_semantic_keys_complete()
    test_alias_same_value()
    test_semantic_map_covers_palette()
    test_no_primitive_poke_in_component()
    test_setup_theme_smoke()
    print('theme token 契约测试全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
