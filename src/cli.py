# -*- coding: utf-8 -*-
"""剧本双语拆分 · 命令行入口（供批处理 / 无头环境使用）"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import run  # noqa: E402
from styles import template_keys  # noqa: E402

ALL_FORMATS = ('csv', 'srt', 'zh_docx', 'foreign_docx', 'bilingual_docx',
               'zh_txt', 'foreign_txt', 'missing', 'stats')


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='从中外混排的 .docx 剧本中拆出中文版 / 外语版 / 对照表',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例:\n'
               '  python cli.py 剧本.docx\n'
               '  python cli.py 剧本.docx -f csv,srt,zh_docx\n'
               '  python cli.py 剧本.docx --all --lang en')
    ap.add_argument('input', nargs='+', help='一个或多个 .docx 剧本')
    ap.add_argument('-o', '--out', default=None, help='输出目录（默认与源文件同级的 _split）')
    ap.add_argument('-f', '--formats', default='csv',
                    help='导出格式，逗号分隔：%s（默认 csv）' % ','.join(ALL_FORMATS))
    ap.add_argument('-a', '--all', action='store_true',
                    help='处理整篇（默认只处理分集正文，跳过大纲/人物小传）')
    ap.add_argument('--keep-revisions', action='store_true',
                    help='保留删除线内容与修订痕迹（默认清除）')
    ap.add_argument('-l', '--lang', default='auto', choices=['auto', 'pt', 'en'],
                    help='外语语种（默认 auto 自动识别）')
    ap.add_argument('--srt-gap', type=int, default=2000, help='srt 占位轴每条时长(毫秒)')

    g = ap.add_argument_group('排版（仅作用于 docx）')
    g.add_argument('-t', '--template', default='cn', choices=template_keys(),
                   help='排版模板（默认 cn 中文短剧；hollywood 好莱坞标准）')
    g.add_argument('--no-beautify', action='store_true', help='不排版（保留原文格式）')
    g.add_argument('--no-toc', action='store_true', help='不插入目录域')
    g.add_argument('--no-header-footer', action='store_true', help='不加页眉页脚')
    args = ap.parse_args(argv)

    formats = [x.strip() for x in args.formats.split(',') if x.strip()]
    bad = [x for x in formats if x not in ALL_FORMATS]
    if bad:
        ap.error('未知格式: %s' % ','.join(bad))

    ok = 0
    for src in args.input:
        if not os.path.isfile(src):
            print('[跳过] 文件不存在: %s' % src)
            continue
        print('\n=== %s ===' % os.path.basename(src))
        try:
            outs, records, lang = run(
                src, out_dir=args.out, formats=formats,
                only_body=not args.all, strip_rev=not args.keep_revisions,
                lang=args.lang, srt_gap=args.srt_gap,
                template=args.template, beautify=not args.no_beautify,
                toc=not args.no_toc, hf=not args.no_header_footer)
            for o in outs:
                print('  输出: %s' % o)
            ok += 1
        except Exception as e:
            print('  [失败] %s: %s' % (type(e).__name__, e))
    print('\n完成 %d/%d' % (ok, len(args.input)))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
