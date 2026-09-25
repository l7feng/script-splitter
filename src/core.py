# -*- coding: utf-8 -*-
"""
剧本双语拆分 · 核心引擎

从「中外混排」的 .docx 剧本中拆出：
  - 中文版（场景/动作/情绪 + 中文台词，给剪辑看）
  - 外语版（角色 + 外语台词，给字幕用）
  - 双语对照版（中文台词下紧跟外语原文，校对用）
  - 三栏对照 CSV（默认产物）
  - 外语台词 srt / 缺翻译清单 / 台词统计

设计要点
  1. 直接改写原 docx 的 XML，保留原文档结构，再套用排版模板
  2. 纯规则解析，不调任何模型，零第三方依赖
  3. 本模块不 import tkinter，可在无头环境/CLI 下使用
"""
import os
import re
import csv
import zipfile
import xml.etree.ElementTree as ET

from dataclasses import replace

from styles import get_template, list_templates  # noqa: F401
import beautify as BF

WNS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
W = '{%s}' % WNS

# ---------------------------------------------------------------- 字符与正则

RE_HAN = re.compile(r'[\u4e00-\u9fff]')
RE_LAT = re.compile(r'[A-Za-z\u00C0-\u00FF\u0100-\u017F]')
RE_LAT_WORD = re.compile(r'[A-Za-z\u00C0-\u00FF\u0100-\u017F]{2,}')
RE_WORD = re.compile(r"[a-z\u00e0-\u00ff\u0100-\u017f']+")

RE_EP = re.compile(r'^第\s*\d+\s*集')
RE_SCENE = re.compile(r'^\d+\s*[-–]\s*\d+')
RE_FULL_PAREN = re.compile(r'^[（(](.+)[）)]$', re.S)
RE_DIALOG = re.compile(r'^([^：:\n]{1,150})[：:](.+)$', re.S)
RE_BRACKET = re.compile(r'[（(\[]([^）)\]]*)[）)\]][。.！!？?]*')
RE_MARK = re.compile(r"^(VO|OS|V\.O\.|O\.S\.|CONT'D|CONT|OFF|画外|旁白)$", re.I)
RE_CJK_PUNCT = re.compile(r'[。！？，、；：…“”‘’（）《》]')

META_WORDS = ('场景提示', '人物', '动作', '音效', '画面', '本集钩子', '转场', '备注',
              '镜头', '特写', '闪回', '闪前', '字幕', '音乐', '旁白', '切出', '切入',
              '切', '淡入', '淡出', '叠化', '定格', '黑场', '黑屏', '标题卡', '字幕卡',
              '插入', '空镜', '外景', '内景', '时间', '地点', '道具', '服装', '化妆')
RE_PREFIX = re.compile(r'^(?:%s)\s*[:：]' % '|'.join(META_WORDS))

PT_MARKERS = set("""
não você é para uma um do da em nós ele ela está muito também então mãe pai
obrigado obrigada sim mas por seu sua meu minha tem vou aqui isso dos das
no na os as eu tu com que de se o a está são foi era tudo nada agora depois
porque quanto como onde quem quando senhor senhora chefe doutor doutora
""".split())

EN_MARKERS = set("""
the you is are and of to in it that this what why how my your with for on at
was were have has do does not me him her us them yes no dont doesnt im ive
they we he she can will would could should there here about gonna wanna
""".split())

LANG_NAME = {'pt': '葡语', 'en': '英语'}


def score_lang(text):
    words = RE_WORD.findall((text or '').lower())
    return (sum(1 for w in words if w in PT_MARKERS),
            sum(1 for w in words if w in EN_MARKERS))


def detect_doc_lang(records, fallback='pt'):
    pt = en = 0
    for r in records:
        p, e = score_lang(r['foreign'])
        pt += p
        en += e
    if pt == 0 and en == 0:
        return fallback
    return 'pt' if pt >= en else 'en'


# ---------------------------------------------------------------- 文本判定

def is_zh(s):
    if not s:
        return False
    han = len(RE_HAN.findall(s))
    lat = len(RE_LAT.findall(s))
    return han >= 2 and han > lat * 0.4


def is_foreign(s):
    if not s:
        return False
    han = len(RE_HAN.findall(s))
    lat = len(RE_LAT.findall(s))
    return len(RE_LAT_WORD.findall(s)) >= 3 and lat > han * 1.2


def is_zhish(s):
    """括号内容是否属于中文翻译。

    比 is_zh 宽松：允许夹带外文人名/术语，
    只要中文占比够高、或出现中文标点即判为翻译。
    例：(Bia Nogueira！好巧啊。)  中文只有 3 字但有中文标点 → 翻译
    """
    if not s:
        return False
    if is_zh(s):
        return True
    han = len(RE_HAN.findall(s))
    if han < 2:
        return False
    return bool(RE_CJK_PUNCT.search(s))


def clean_action(action):
    parts = re.findall(r'[（(]([^）)]*)[）)]', action or '')
    keep = [p.strip() for p in parts if RE_MARK.match((p or '').strip())]
    return ''.join('(%s)' % p for p in keep)


def split_dialogue(text):
    m = RE_DIALOG.match(text.strip())
    left, right = m.group(1).strip(), m.group(2).strip()
    lp = re.match(r'^([^（(]+)(.*)$', left, re.S)
    speaker = lp.group(1).strip() if lp else left
    action = lp.group(2).strip() if lp else ''
    foreign, zh = '', ''
    last = None
    for last in RE_BRACKET.finditer(right):
        pass
    if last and is_zhish(last.group(1)):
        zh = last.group(1).strip()
        foreign = (right[:last.start()] + right[last.end():]).strip()
    else:
        foreign = right
    if foreign and is_zh(foreign) and not is_foreign(foreign):
        zh, foreign = foreign, ''
    return speaker, action, foreign, zh


def build_speakers(texts, min_freq=2):
    from collections import Counter
    cnt = Counter()
    for t in texts:
        m = RE_DIALOG.match(t)
        if not m:
            continue
        nm = re.match(r'^[^（(]+', m.group(1).strip())
        if not nm:
            continue
        nm = nm.group(0).strip()
        if not nm or len(nm) > 20 or re.search(r'[。，、；！？]', nm):
            continue
        cnt[nm] += 1
    return {k for k, v in cnt.items() if v >= min_freq}


def looks_like_dialogue(t, speakers=frozenset()):
    m = RE_DIALOG.match(t)
    if not m:
        return False
    left, right = m.group(1).strip(), m.group(2).strip()
    nm = re.match(r'^[^（(]+', left)
    nm = nm.group(0).strip() if nm else left
    name_hit = nm in speakers
    paren_end = left.endswith('）') or left.endswith(')')
    last = None
    for last in RE_BRACKET.finditer(right):
        pass
    if last and is_zhish(last.group(1)):
        head = (right[:last.start()] + right[last.end():]).strip()
        han = len(RE_HAN.findall(head))
        lat = len(RE_LAT.findall(head))
        strong_foreign = len(RE_LAT_WORD.findall(head)) >= 4 and lat > han * 3
        if head == '' or is_foreign(head) or (lat >= 2 and lat > han):
            return name_hit or paren_end or strong_foreign
    han = len(RE_HAN.findall(right))
    lat = len(RE_LAT.findall(right))
    strong = is_foreign(right) and han <= lat * 0.35
    return ((name_hit or paren_end) and (strong or is_zh(right))) or (strong and han == 0)


def classify(text, in_body, speakers=frozenset()):
    t = text.strip()
    if not t:
        return 'blank'
    if RE_EP.match(t):
        return 'episode'
    if RE_SCENE.match(t):
        return 'scene_no'
    if RE_PREFIX.match(t):
        return 'meta'
    m = RE_FULL_PAREN.match(t)
    if m and is_zh(m.group(1)):
        return 'paren_zh'
    if not in_body:
        return 'front_matter'
    if looks_like_dialogue(t, speakers):
        return 'dialogue'
    return 'narration'


# ---------------------------------------------------------------- XML 操作

def para_text(p):
    return ''.join((t.text or '') for t in p.iter(W + 't'))


def replace_range(p, a, b, new):
    nodes, pos = [], 0
    for t in p.iter(W + 't'):
        s = t.text or ''
        nodes.append((t, pos, pos + len(s)))
        pos += len(s)
    if not nodes:
        return
    done = False
    for t, s, e in nodes:
        if e <= a or s >= b:
            continue
        cur = t.text or ''
        pre = cur[:max(0, a - s)]
        post = cur[max(0, b - s):]
        if not done:
            t.text = pre + new + post
            done = True
        else:
            t.text = pre + post
    if not done:
        t = nodes[-1][0]
        t.text = (t.text or '') + new


def strip_revisions(body):
    def walk(node):
        for child in list(node):
            walk(child)
        for child in list(node):
            if child.tag == W + 'ins':
                idx = list(node).index(child)
                for r in list(child):
                    node.insert(idx, r)
                    idx += 1
                node.remove(child)
            elif child.tag == W + 'del':
                node.remove(child)
            elif child.tag == W + 'r':
                rpr = child.find(W + 'rPr')
                if rpr is not None and (rpr.find(W + 'strike') is not None
                                        or rpr.find(W + 'dstrike') is not None):
                    node.remove(child)
    walk(body)
    for rpr in list(body.iter(W + 'rPr')):
        for c in list(rpr):
            if c.tag == W + 'rPrChange':
                rpr.remove(c)


def load(path, strip=True):
    z = zipfile.ZipFile(path)
    xml = z.read('word/document.xml').decode('utf-8')

    # 扫描根元素的开始标签，登记所有 xmlns 前缀
    end = xml.find('<w:body')
    if end < 0:
        end = xml.find('<body')
    if end < 0:
        end = min(len(xml), 20000)
    head = xml[:end]
    if not head:
        head = xml[:20000]
    for m in re.finditer(r'xmlns:([A-Za-z0-9]+)="([^"]+)"', head):
        ET.register_namespace(m.group(1), m.group(2))

    # 关键：必须让 WNS 绑定到有名字的前缀（w），绝不能绑到默认命名空间。
    # 一旦用默认命名空间，ElementTree 会把属性序列化成 val="..." 而不是
    # w:val="..."，Word 会判定文件损坏并提示修复。
    ET.register_namespace('w', WNS)

    root = ET.fromstring(xml)
    # mc:Ignorable 会引用序列化时被丢弃的未使用前缀（w15/wp14 等），
    # 留着会让 Word 报「引用了未声明的命名空间」，直接去掉（该属性是可选的）
    for k in list(root.attrib):
        if k.endswith('}Ignorable'):
            del root.attrib[k]

    body = root.find(W + 'body')
    if strip:
        strip_revisions(body)
    return z, root, body


# ---------------------------------------------------------------- 解析

def analyze(path, only_body=True, strip_rev=True):
    """返回 ops = [(段落元素, 动作, payload, 段落角色)]"""
    z, root, body = load(path, strip_rev)
    paras = body.findall(W + 'p')
    texts = [para_text(p).strip() for p in paras]
    speakers = build_speakers(texts)

    ops, records = [], []
    ep, scene = '', ''
    in_body = not only_body
    last_dlg = None

    for p in paras:
        raw = para_text(p)
        text = raw.strip()
        if RE_EP.match(text):
            in_body = True
        kind = classify(text, in_body, speakers)

        if kind == 'blank':
            ops.append((p, 'keep', None, 'blank'))
            continue
        if kind == 'episode':
            ep = text
            ops.append((p, 'keep', None, 'episode'))
            continue
        if kind == 'scene_no':
            scene = text
            ops.append((p, 'keep', None, 'scene'))
            continue
        if kind == 'front_matter':
            ops.append((p, 'skip', None, 'front'))
            continue
        if kind in ('meta', 'narration'):
            ops.append((p, 'zh_only', None, 'meta' if kind == 'meta' else 'action'))
            continue
        if kind == 'paren_zh':
            inner = RE_FULL_PAREN.match(text).group(1).strip()
            if last_dlg is not None and not last_dlg['zh']:
                last_dlg['zh'] = inner
                ops.append((p, 'drop', None, 'other'))
            elif last_dlg is not None and last_dlg['zh'] == inner:
                ops.append((p, 'drop', None, 'other'))       # 源文档写了两遍，去重
            else:
                ops.append((p, 'zh_only', None, 'action'))
            continue
        if kind == 'dialogue':
            speaker, action, foreign, zh = split_dialogue(text)
            m = RE_DIALOG.match(text)
            right_start = len(text) - len(m.group(2))
            lead = len(raw) - len(raw.lstrip())
            rec = dict(ep=ep, scene=scene, speaker=speaker, action=action,
                       foreign=foreign, zh=zh, lead=lead,
                       right=(lead + right_start, lead + len(text)))
            records.append(rec)
            last_dlg = rec
            ops.append((p, 'split', rec, 'dialogue'))
            continue
        ops.append((p, 'keep', None, 'other'))

    return z, root, body, ops, records


def apply(p, action, payload, mode, foreign_clean=True):
    """就地改写段落；返回 False 表示该段要删除。mode: zh | foreign | bilingual"""
    raw = para_text(p)
    if action == 'keep':
        return True
    if action in ('drop', 'skip'):
        return False
    if action == 'zh_only':
        return mode != 'foreign'
    if action == 'split':
        rec = payload
        if mode == 'foreign':
            if not rec['foreign']:
                return False
            if foreign_clean:
                new = '%s%s：%s' % (rec['speaker'], clean_action(rec['action']), rec['foreign'])
                replace_range(p, 0, len(raw), new)
            else:
                replace_range(p, rec['right'][0], rec['right'][1], rec['foreign'])
            return True
        replace_range(p, rec['right'][0], rec['right'][1], rec['zh'] or '[待补中文]')
        return True
    return True


def dump_body(body):
    return [t for t in (para_text(p).strip() for p in body.findall(W + 'p')) if t]


# ---------------------------------------------------------------- 美化

def _apply_styles(body, alive, tmpl, mode, suppress_first_break=False):
    st = tmpl['styles']
    first_ep = True
    for p, role, payload in alive:
        spec = st.get(role) or st.get('action')
        if spec is None:
            continue
        if role == 'episode':
            if first_ep:
                first_ep = False
                if suppress_first_break and spec.page_break_before:
                    spec = replace(spec, page_break_before=False)
        if role == 'dialogue' and payload is not None:
            full = para_text(p)
            spk = payload['speaker']
            # 段落文本可能已被整体重写（外语版），所以按实际文本定位角色名
            i0 = full.find(spk) if spk else -1
            if i0 < 0:
                i0 = payload['lead']
            i1 = i0 + len(spk)
            parts = []
            if i0:
                parts.append((full[:i0], st['dialogue']))
            parts.append((full[i0:i1], st['speaker']))
            parts.append((full[i1:], st['dialogue']))
            BF.set_para_props(p, st['dialogue'])
            BF.rebuild_paragraph(p, parts)
            continue
        if role == 'foreign':
            continue                       # 建段时已套好样式
        pstyle = 'Heading1' if role == 'episode' else ('Heading2' if role == 'scene' else None)
        BF.style_paragraph(p, spec, pstyle)


def _insert_foreign_lines(body, alive, tmpl):
    """双语对照版：在每条对白下插入一行外语原文"""
    spec = tmpl['styles'].get('foreign')
    added = []
    for p, role, payload in list(alive):
        if role != 'dialogue' or payload is None or not payload['foreign']:
            continue
        idx = list(body).index(p)
        np = BF.make('p')
        BF.set_para_props(np, spec)
        np.append(BF.make_run(payload['foreign'], spec))
        body.insert(idx + 1, np)
        added.append((np, 'foreign', None))
    alive.extend(added)


def build_doc_body(path, mode, only_body=True, strip_rev=True, foreign_clean=True,
                   template='cn', beautify=True, toc=True, hf=True, title=''):
    z, root, body, ops, records = analyze(path, only_body, strip_rev)
    alive = []
    for p, action, payload, role in ops:
        if apply(p, action, payload, mode, foreign_clean):
            alive.append((p, role, payload))
        else:
            body.remove(p)

    heading_styles = None
    with_hf = False
    if beautify:
        tmpl = get_template(template)
        if mode == 'bilingual':
            _insert_foreign_lines(body, alive, tmpl)
        BF.remove_blank_paragraphs(body)
        _apply_styles(body, alive, tmpl, mode, suppress_first_break=not toc)
        if toc:
            BF.insert_toc(body, tmpl, has_title=True)
        BF.apply_margins_and_hf(body, tmpl, title or '剧本', with_hf=hf)
        heading_styles = BF.build_heading_styles(tmpl)
        with_hf = hf
    return z, root, body, records, heading_styles, with_hf


def write_docx(z, root, out_path, heading_styles=None, with_hf=False, title=''):
    xmlout = (b"<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n"
              + ET.tostring(root, encoding='utf-8'))
    parts = BF.patch_zip_for_hf(z, title, out_path, root) if with_hf else None
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zo:
        for item in z.infolist():
            data = z.read(item.filename)
            if item.filename == 'word/document.xml':
                data = xmlout
            elif item.filename == 'word/settings.xml':
                data = re.sub(rb'<w:trackChanges[^>]*/>', b'', data)
            elif item.filename == 'word/styles.xml' and heading_styles:
                data = data.decode('utf-8').replace(
                    '</w:styles>', heading_styles + '</w:styles>').encode('utf-8')
            elif parts and item.filename == 'word/_rels/document.xml.rels':
                data = parts['rels']
            elif parts and item.filename == '[Content_Types].xml':
                data = parts['content_types']
            zo.writestr(item, data)
        if parts:
            zo.writestr('word/header1.xml', parts['header'])
            zo.writestr('word/footer1.xml', parts['footer'])
    return out_path


# ---------------------------------------------------------------- 导出

def ts(ms):
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    return '%02d:%02d:%02d,%03d' % (h, m, s, ms % 1000)


def export_csv(records, out_path):
    with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['集', '场', '角色', '外语台词', '中文台词'])
        for r in records:
            w.writerow([r['ep'], r['scene'], r['speaker'], r['foreign'], r['zh']])
    return out_path


def export_srt(records, out_path, gap_ms=2000):
    lines, n, t = [], 0, 0
    for r in records:
        if not r['foreign']:
            continue
        n += 1
        lines.append(str(n))
        lines.append('%s --> %s' % (ts(t), ts(t + gap_ms)))
        lines.append(r['foreign'])
        lines.append('')
        t += gap_ms + 200
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return out_path


def export_missing(records, out_path):
    miss = [r for r in records if not r['zh']]
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('缺中文翻译清单（共 %d 条）\n' % len(miss))
        f.write('=' * 60 + '\n\n')
        for i, r in enumerate(miss, 1):
            f.write('%d. [%s｜%s] %s\n' % (i, r['ep'], r['scene'], r['speaker']))
            f.write('   外语：%s\n' % r['foreign'])
            f.write('   中文：\n\n')
    return out_path


def export_stats(records, out_path):
    from collections import Counter, OrderedDict
    by_char = Counter(r['speaker'] for r in records)
    by_ep = OrderedDict()
    for r in records:
        d = by_ep.setdefault(r['ep'] or '(未分集)', {'lines': 0, 'scenes': set()})
        d['lines'] += 1
        if r['scene']:
            d['scenes'].add(r['scene'])
    total = len(records)
    with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['角色台词统计'])
        w.writerow(['角色', '台词数', '占比'])
        for k, v in by_char.most_common():
            w.writerow([k, v, '%.1f%%' % (v / total * 100) if total else '0%'])
        w.writerow([])
        w.writerow(['每集统计'])
        w.writerow(['集', '台词数', '场景数'])
        for k, v in by_ep.items():
            w.writerow([k, v['lines'], len(v['scenes'])])
        w.writerow([])
        w.writerow(['合计', total, sum(len(v['scenes']) for v in by_ep.values())])
    return out_path


def export_docx(path, out_path, mode, only_body=True, strip_rev=True, foreign_clean=True,
                template='cn', beautify=True, toc=True, hf=True, title=''):
    z, root, body, records, hs, whf = build_doc_body(
        path, mode, only_body, strip_rev, foreign_clean, template, beautify, toc, hf, title)
    return write_docx(z, root, out_path, hs, whf, title)


def export_txt(path, out_path, mode, only_body=True, strip_rev=True, foreign_clean=True):
    z, root, body, ops, records = analyze(path, only_body, strip_rev)
    for p, action, payload, role in ops:
        if not apply(p, action, payload, mode, foreign_clean):
            body.remove(p)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(dump_body(body)))
    return out_path


def clean_title(base):
    """从文件名推出一个干净的剧名，供页眉使用。
    《Falcão的90日新娘》删减标注版v6 → Falcão的90日新娘
    """
    t = os.path.splitext(os.path.basename(base or ''))[0]
    t = re.sub(r'[《》【】\[\]]', '', t)
    t = re.sub(r'(删减|标注|修订|校对|标注版|删减版|最终|定稿|完结).*$', '', t)
    t = re.sub(r'_?v\d+.*$', '', t, flags=re.I)
    t = t.strip(' _-—')
    return t or (base or '剧本')


def run(path, out_dir=None, base=None, formats=('csv',), only_body=True,
        strip_rev=True, lang='auto', srt_gap=2000, template='cn', beautify=True,
        toc=True, hf=True, log=print):
    """
    主入口。
    formats: csv / srt / zh_docx / foreign_docx / bilingual_docx /
             zh_txt / foreign_txt / missing / stats
    """
    if out_dir is None:
        out_dir = os.path.join(os.path.dirname(path),
                               os.path.splitext(os.path.basename(path))[0] + '_split')
    os.makedirs(out_dir, exist_ok=True)
    if base is None:
        base = os.path.splitext(os.path.basename(path))[0]

    z, root, body, ops, records = analyze(path, only_body, strip_rev)
    doc_lang = lang if lang in ('pt', 'en') else detect_doc_lang(records)
    lname = LANG_NAME[doc_lang]
    log('识别到 %d 条对白，主外语 = %s' % (len(records), lname))

    outputs = []
    if 'csv' in formats:
        outputs.append(export_csv(records, os.path.join(out_dir, base + '_三栏对照.csv')))
    if 'srt' in formats:
        outputs.append(export_srt(records, os.path.join(out_dir, base + '_%s台词.srt' % lname), srt_gap))
    if 'missing' in formats:
        outputs.append(export_missing(records, os.path.join(out_dir, base + '_缺翻译清单.txt')))
    if 'stats' in formats:
        outputs.append(export_stats(records, os.path.join(out_dir, base + '_台词统计.csv')))

    tpl_label = get_template(template)['label']
    title = clean_title(base)
    if 'zh_docx' in formats:
        outputs.append(export_docx(path, os.path.join(out_dir, base + '_中文版.docx'),
                                   'zh', only_body, strip_rev, True, template,
                                   beautify, toc, hf, base))
        log('中文版排版：%s' % tpl_label)
    if 'foreign_docx' in formats:
        outputs.append(export_docx(path, os.path.join(out_dir, base + '_%s版.docx' % lname),
                                   'foreign', only_body, strip_rev, True, template,
                                   beautify, toc, hf, base))
    if 'bilingual_docx' in formats:
        outputs.append(export_docx(path, os.path.join(out_dir, base + '_双语对照版.docx'),
                                   'bilingual', only_body, strip_rev, True, template,
                                   beautify, toc, hf, base))
    if 'zh_txt' in formats:
        outputs.append(export_txt(path, os.path.join(out_dir, base + '_中文版.txt'),
                                  'zh', only_body, strip_rev))
    if 'foreign_txt' in formats:
        outputs.append(export_txt(path, os.path.join(out_dir, base + '_%s版.txt' % lname),
                                  'foreign', only_body, strip_rev))

    miss = sum(1 for r in records if not r['zh'])
    if miss:
        log('提示：%d 条台词缺中文翻译，已标记 [待补中文]' % miss)
    return outputs, records, doc_lang
