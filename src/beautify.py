# -*- coding: utf-8 -*-
"""
docx 排版美化：样式套用、空白行清理、自动分页、目录域、页眉页脚

本模块只做「排版」，不参与内容解析。
"""
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import replace

WNS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
W = '{%s}' % WNS
XMLSPACE = '{http://www.w3.org/XML/1998/namespace}space'

REL_HDR = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/header'
REL_FTR = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer'

RID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


# ---------------------------------------------------------------- 基础构造

def make(tag, **attrs):
    e = ET.Element(W + tag)
    for k, v in attrs.items():
        if v is None:
            continue
        e.set(W + k, str(v))
    return e


def _run_rpr(spec):
    rpr = make('rPr')
    rpr.append(make('rFonts', ascii=spec.font_lat, hAnsi=spec.font_lat, eastAsia=spec.font_zh))
    if spec.bold:
        rpr.append(make('b'))
    if spec.all_caps:
        rpr.append(make('caps'))
    if spec.color:
        rpr.append(make('color', val=spec.color))
    rpr.append(make('sz', val=int(spec.size * 2)))
    rpr.append(make('szCs', val=int(spec.size * 2)))
    return rpr


def make_run(text, spec):
    r = make('r')
    r.append(_run_rpr(spec))
    t = make('t')
    t.text = text
    t.set(XMLSPACE, 'preserve')
    r.append(t)
    return r


def set_para_props(p, spec, pstyle=None):
    """按 OOXML schema 顺序写入 pPr"""
    ppr = p.find(W + 'pPr')
    if ppr is None:
        ppr = make('pPr')
        p.insert(0, ppr)
    else:
        for tag in ('pStyle', 'pageBreakBefore', 'spacing', 'ind', 'jc', 'outlineLvl'):
            for e in ppr.findall(W + tag):
                ppr.remove(e)

    pos = 0
    if pstyle:
        ppr.insert(pos, make('pStyle', val=pstyle))
        pos += 1
    if spec.page_break_before:
        ppr.insert(pos, make('pageBreakBefore'))
        pos += 1
    ppr.insert(pos, make('spacing',
                         before=int(spec.before * 20),
                         after=int(spec.after * 20),
                         line=int(spec.line * 240),
                         lineRule='auto'))
    pos += 1
    ind = {}
    if spec.indent_left:
        ind['left'] = int(spec.indent_left * 1440)
    if spec.indent_right:
        ind['right'] = int(spec.indent_right * 1440)
    if spec.indent_first:
        ind['firstLineChars'] = int(spec.indent_first * 100)
    if ind:
        ppr.insert(pos, make('ind', **ind))
        pos += 1
    ppr.insert(pos, make('jc', val=spec.align))
    pos += 1
    if pstyle:
        lvl = 0 if pstyle == 'Heading1' else 1
        ppr.insert(pos, make('outlineLvl', val=lvl))
    return ppr


def style_paragraph(p, spec, pstyle=None):
    """整段统一套用一种样式（不对角色名做单独加粗）"""
    set_para_props(p, spec, pstyle)
    for r in p.findall(W + 'r'):
        for old in r.findall(W + 'rPr'):
            r.remove(old)
        r.insert(0, _run_rpr(spec))
    return p


def rebuild_paragraph(p, parts):
    """parts = [(text, spec), ...] 重建段落的所有 run（用于角色名加粗等混合样式）"""
    for r in list(p.findall(W + 'r')):
        p.remove(r)
    for text, spec in parts:
        if text:
            p.append(make_run(text, spec))
    return p


def remove_blank_paragraphs(body):
    """删除空白段落（用段间距代替空行）"""
    n = 0
    for p in list(body.findall(W + 'p')):
        txt = ''.join(t.text or '' for t in p.iter(W + 't')).strip()
        if not txt and p.find(W + 'r') is None:
            body.remove(p)
            n += 1
        elif not txt:
            body.remove(p)
            n += 1
    return n


# ---------------------------------------------------------------- 目录

def make_toc(title='目录', spec=None):
    """生成 Word 自动目录（TOC 域）。打开后 Ctrl+A → F9 更新出页码"""
    out = []
    if spec is not None:
        # 目录标题不能继承集标题的「段前分页」，否则文档最前面会多出一张空白页
        if getattr(spec, 'page_break_before', False):
            spec = replace(spec, page_break_before=False)
        tp = make('p')
        set_para_props(tp, spec)
        tp.append(make_run(title, spec))
        out.append(tp)

    fp = make('p')                              # 域段落
    r1 = make('r')
    r1.append(make('fldChar', fldCharType='begin', dirty='true'))
    fp.append(r1)
    r2 = make('r')
    it = make('instrText')
    it.set(XMLSPACE, 'preserve')
    it.text = r' TOC \o "1-2" \h \z \u '
    r2.append(it)
    fp.append(r2)
    r3 = make('r')
    r3.append(make('fldChar', fldCharType='separate'))
    fp.append(r3)
    r4 = make('r')
    t = make('t')
    t.text = '打开后按 Ctrl+A 再按 F9 生成目录'
    r4.append(t)
    fp.append(r4)
    r5 = make('r')
    r5.append(make('fldChar', fldCharType='end'))
    fp.append(r5)
    out.append(fp)
    return out


def insert_toc(body, template, has_title=True):
    """在文档最前面插入目录域。注意：不再额外加尾部分页，
    交给第一条集标题自带的 pageBreakBefore 来分开目录页与正文，
    避免出现「目录后一张空白页」。"""
    st = template['styles']
    spec = st.get('episode')
    paras = make_toc(spec=spec if has_title else None)
    pos = 0
    for p in paras:
        body.insert(pos, p)
        pos += 1
    return len(paras)


# ---------------------------------------------------------------- 样式表注入

def _style_xml(sid, name, spec, outline):
    return (
        '<w:style w:type="paragraph" w:styleId="%s">'
        '<w:name w:val="%s"/>'
        '<w:qFormat/>'
        '<w:pPr><w:outlineLvl w:val="%d"/></w:pPr>'
        '<w:rPr><w:rFonts w:ascii="%s" w:hAnsi="%s" w:eastAsia="%s"/>'
        '%s<w:color w:val="%s"/><w:sz w:val="%d"/><w:szCs w:val="%d"/></w:rPr>'
        '</w:style>'
    ) % (sid, name, outline, spec.font_lat, spec.font_lat, spec.font_zh,
         '<w:b/>' if spec.bold else '', spec.color or '000000',
         int(spec.size * 2), int(spec.size * 2))


def build_heading_styles(template):
    st = template['styles']
    out = []
    if 'episode' in st:
        out.append(_style_xml('Heading1', 'heading 1', st['episode'], 0))
    if 'scene' in st:
        out.append(_style_xml('Heading2', 'heading 2', st['scene'], 1))
    return ''.join(out)


# ---------------------------------------------------------------- 页面设置 / 页眉页脚

HDR_TPL = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:hdr xmlns:w="%s"><w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
           '<w:r><w:rPr><w:sz w:val="16"/><w:color w:val="808080"/></w:rPr>'
           '<w:t xml:space="preserve">%s</w:t></w:r></w:p></w:hdr>')

FTR_TPL = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:ftr xmlns:w="%s"><w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
           '<w:r><w:rPr><w:sz w:val="16"/></w:rPr><w:t xml:space="preserve">— </w:t></w:r>'
           '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
           '<w:r><w:rPr><w:sz w:val="16"/></w:rPr>'
           '<w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
           '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
           '<w:r><w:rPr><w:sz w:val="16"/></w:rPr><w:t xml:space="preserve"> —</w:t></w:r>'
           '</w:p></w:ftr>')


def apply_margins_and_hf(body, template, title, with_hf=True):
    """设置页边距，并在 sectPr 上挂页眉/页脚引用"""
    m = template.get('margins', {})
    sect = body.find(W + 'sectPr')
    if sect is None:
        sect = make('sectPr')
        body.append(sect)

    if with_hf:
        for tag in ('headerReference', 'footerReference'):
            for e in sect.findall(W + tag):
                sect.remove(e)
        hr = make('headerReference', type='default')
        hr.set(RID, 'rIdHdr1')
        fr = make('footerReference', type='default')
        fr.set(RID, 'rIdFtr1')
        sect.insert(0, fr)
        sect.insert(0, hr)

    pg = sect.find(W + 'pgMar')
    if pg is None:
        pg = make('pgMar')
        sect.append(pg)
    in_to_twip = lambda x: int(float(x) * 1440)
    pg.set(W + 'left', str(in_to_twip(m.get('left', 1.0))))
    pg.set(W + 'right', str(in_to_twip(m.get('right', 1.0))))
    pg.set(W + 'top', str(in_to_twip(m.get('top', 1.0))))
    pg.set(W + 'bottom', str(in_to_twip(m.get('bottom', 1.0))))
    pg.set(W + 'header', str(in_to_twip(0.5)))
    pg.set(W + 'footer', str(in_to_twip(0.5)))
    return sect


def patch_zip_for_hf(z, title, out_path, root):
    """写盘时补上 header1.xml / footer1.xml / rels / Content_Types"""
    import zipfile as _zf
    rels_xml = z.read('word/_rels/document.xml.rels').decode('utf-8')
    if 'header1.xml' not in rels_xml:
        maxid = max([int(m) for m in re.findall(r'Id="rId(\d+)"', rels_xml)] or [0])
        add = ('<Relationship Id="rIdHdr1" Type="%s" Target="header1.xml"/>'
               '<Relationship Id="rIdFtr1" Type="%s" Target="footer1.xml"/>') % (
            'http://schemas.openxmlformats.org/officeDocument/2006/relationships/header',
            'http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer')
        # rId 冲突时顺延
        if ('rIdHdr1' in rels_xml) or ('rIdFtr1' in rels_xml):
            add = ('<Relationship Id="rId%d" Type="%s" Target="header1.xml"/>'
                   '<Relationship Id="rId%d" Type="%s" Target="footer1.xml"/>') % (
                maxid + 1, REL_HDR, maxid + 2, REL_FTR)
        rels_xml = rels_xml.replace('</Relationships>', add + '</Relationships>')

    ct = z.read('[Content_Types].xml').decode('utf-8')
    if 'header1.xml' not in ct:
        add = ('<Override PartName="/word/header1.xml" ContentType="application/vnd'
               '.openxmlformats-officedocument.wordprocessingml.header+xml"/>'
               '<Override PartName="/word/footer1.xml" ContentType="application/vnd'
               '.openxmlformats-officedocument.wordprocessingml.footer+xml"/>')
        # 兼容 <Types ...> 与带前缀的 </Types:xxx> 两种写法
        if '</Types>' in ct:
            ct = ct.replace('</Types>', add + '</Types>')
        else:
            m = re.search(r'</(\w+:)?Types>', ct)
            if m:
                ct = ct[:m.start()] + add + ct[m.start():]

    hdr = HDR_TPL % (WNS, _esc(title))
    ftr = FTR_TPL % (WNS,)

    return dict(rels=rels_xml.encode('utf-8'),
                content_types=ct.encode('utf-8'),
                header=hdr.encode('utf-8'),
                footer=ftr.encode('utf-8'))


def _esc(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
