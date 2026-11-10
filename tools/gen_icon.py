# -*- coding: utf-8 -*-
"""生成应用图标 src/app.ico（多分辨率 32bpp）。

配色对齐新液态玻璃暗色主题：暖陶圆角渐变底 + 深棕 S，右上角一抹极淡青灰光斑，
顶部一道玻璃高光；与界面顶栏品牌块同源。
尺寸：16 / 24 / 32 / 48 / 64 / 128 / 256。

用法（开发期，需 Pillow）：
    python tools/gen_icon.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ICO = os.path.join(ROOT, 'src', 'app.ico')

S = 256
TOP = (214, 167, 128)     # 暖陶上亮
BOT = (198, 149, 108)     # 暖陶下稳（--accent #C8956C）
FG = (27, 20, 16, 255)    # 深棕（--accent-text）
SIZES = [16, 24, 32, 48, 64, 128, 256]


def render():
    # 暖陶竖向渐变底
    base = Image.new('RGBA', (S, S))
    px = base.load()
    for y in range(S):
        t = y / (S - 1)
        c = tuple(int(TOP[i] + (BOT[i] - TOP[i]) * t) for i in range(3)) + (255,)
        for x in range(S):
            px[x, y] = c

    mask = Image.new('L', (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=58, fill=255)
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    img.paste(base, (0, 0), mask)

    # 顶部玻璃高光
    hi = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(hi).rounded_rectangle([12, 10, S - 13, S // 2], radius=46,
                                          fill=(255, 255, 255, 24))
    img.paste(hi, (0, 0), hi)

    # 右上角一抹极淡青灰柔光斑（呼应界面 blob1，小尺寸下不脏）
    gl = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(gl).ellipse([160, -60, 300, 90], fill=(91, 138, 146, 26))
    img.paste(gl, (0, 0), gl)

    # S 字（深棕，粗体雅黑）
    font_path = r'C:\Windows\Fonts\msyhbd.ttc'
    if not os.path.isfile(font_path):
        font_path = r'C:\Windows\Fonts\msyh.ttc'
    font = ImageFont.truetype(font_path, 162)
    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), 'S', font=font)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    x = (S - w) / 2 - bb[0]
    y = (S - h) / 2 - bb[1] - 5
    d.text((x, y), 'S', font=font, fill=FG)
    return img


def main():
    img = render()
    os.makedirs(os.path.dirname(SRC_ICO), exist_ok=True)
    img.save(SRC_ICO, format='ICO', sizes=[(n, n) for n in SIZES])
    print('写入 %s（%d 帧，%d bytes）'
          % (SRC_ICO, len(SIZES), os.path.getsize(SRC_ICO)))


if __name__ == '__main__':
    main()
