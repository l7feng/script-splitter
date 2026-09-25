# -*- coding: utf-8 -*-
"""校验美化后的 docx 是否结构合法：XML 可解析、目录域、标题样式、分页符、页眉页脚、空行"""
import sys
import os
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

PARTS = ['word/document.xml', 'word/styles.xml', '[Content_Types].xml',
         'word/_rels/document.xml.rels']


def check(path):
    print('\n' + '=' * 70)
    print('文件: %s' % os.path.basename(path))
    print('-' * 70)
    ok = True
    if not os.path.isfile(path):
        print('  [FAIL] 文件不存在')
        return False

    z = zipfile.ZipFile(path)
    bad = z.testzip()
    if bad:
        print('  [FAIL] zip 损坏: %s' % bad)
        return False
    names = z.namelist()

    # 1. 各部分 XML 可解析
    for n in PARTS + ['word/header1.xml', 'word/footer1.xml']:
        if n not in names:
            print('  [--] 缺少部件: %s' % n)
            continue
        try:
            ET.fromstring(z.read(n))
        except Exception as e:
            print('  [FAIL] %s 解析失败: %s' % (n, e))
            ok = False
    print('  [OK] 所有 XML 部件可解析')

    doc = z.read('word/document.xml').decode('utf-8')
    root = ET.fromstring(doc)
    body = root.find(W + 'body')
    paras = body.findall(W + 'p')

    # 2. 目录域
    n_toc = doc.count('TOC \\o')
    n_begin = doc.count('fldCharType="begin"')
    print('  [%s] 目录域: TOC 指令 x%d, 域起始 x%d' % ('OK' if n_toc else '--', n_toc, n_begin))

    # 3. 标题样式
    styles = z.read('word/styles.xml').decode('utf-8') if 'word/styles.xml' in names else ''
    h1 = 'w:styleId="Heading1"' in styles
    h2 = 'w:styleId="Heading2"' in styles
    n_h1 = sum(1 for p in paras
               if (p.find('%spPr/%spStyle' % (W, W)) is not None)
               and p.find('%spPr/%spStyle' % (W, W)).get(W + 'val') == 'Heading1')
    n_h2 = sum(1 for p in paras
               if (p.find('%spPr/%spStyle' % (W, W)) is not None)
               and p.find('%spPr/%spStyle' % (W, W)).get(W + 'val') == 'Heading2')
    print('  [%s] 标题样式注入 H1=%s H2=%s；用到 H1 的段落 %d 个、H2 %d 个'
          % ('OK' if (h1 and h2) else 'FAIL', h1, h2, n_h1, n_h2))
    ok = ok and h1 and h2

    # 4. 分页符
    n_pb = sum(1 for p in paras if p.find('%spPr/%spageBreakBefore' % (W, W)) is not None)
    print('  [%s] 分页符(pageBreakBefore): %d 个' % ('OK' if n_pb else '--', n_pb))

    # 5. 页眉页脚
    sect = body.find(W + 'sectPr')
    has_hf = False
    if sect is not None:
        has_hf = (sect.find(W + 'headerReference') is not None
                  and sect.find(W + 'footerReference') is not None)
    rels = z.read('word/_rels/document.xml.rels').decode('utf-8') \
        if 'word/_rels/document.xml.rels' in names else ''
    ct = z.read('[Content_Types].xml').decode('utf-8')
    rel_ok = 'header1.xml' in rels and 'footer1.xml' in rels
    ct_ok = 'header1.xml' in ct and 'footer1.xml' in ct
    print('  [%s] 页眉页脚: sectPr引用=%s rels=%s ContentTypes=%s PAGE域=%s'
          % ('OK' if (has_hf and rel_ok and ct_ok) else '--', has_hf, rel_ok, ct_ok,
             'PAGE' in (z.read('word/footer1.xml').decode('utf-8')
                        if 'word/footer1.xml' in names else '')))

    # 6. 空行
    blank = 0
    for p in paras:
        txt = ''.join(t.text or '' for t in p.iter(W + 't')).strip()
        if not txt:
            blank += 1
    print('  [%s] 剩余空段落: %d（目录域占位段会算进去，<=3 视为正常）'
          % ('OK' if blank <= 3 else 'WARN', blank))

    # 7. 修订痕迹（注意排除 w:instrText，它是目录域的合法元素）
    import re as _re
    for tag in ('ins', 'del', 'strike', 'dstrike', 'rPrChange'):
        n = len(_re.findall(r'<w:%s[ />]' % tag, doc))
        if n:
            print('  [WARN] 残留修订标记 w:%s x%d' % (tag, n))

    # 8. 前 25 段预览
    print('  --- 前 25 段 ---')
    shown = 0
    for p in paras:
        txt = ''.join(t.text or '' for t in p.iter(W + 't')).strip()
        if not txt:
            continue
        st = p.find('%spPr/%spStyle' % (W, W))
        tag = (st.get(W + 'val') or st.get('val')) if st is not None else ''
        print('   [%s] %s' % (tag or '  ', txt[:56]))
        shown += 1
        if shown >= 25:
            break
    return ok


if __name__ == '__main__':
    r = True
    for p in sys.argv[1:]:
        r = check(p) and r
    print('\n结果: %s' % ('全部通过' if r else '存在问题'))
    raise SystemExit(0 if r else 1)
