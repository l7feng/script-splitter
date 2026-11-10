# -*- coding: utf-8 -*-
"""剧本双语拆分 · 桌面 Web 壳（pywebview + 内嵌本地页面）。

架构：Python 后端复用 core / styles / beautify 业务逻辑；界面是 src/web 下的
本地 HTML/CSS/JS（液态玻璃暗色主题），经内置 http 服务喂给 WebView2 内嵌窗口。
Python 原生能力（文件/目录对话框、拆分执行、打开目录）通过 js_api 暴露给前端。

无头 / 批处理仍走 cli.py；本模块只负责图形界面壳，不 import tkinter。
"""
import functools
import http.server
import json
import os
import socket
import socketserver
import sys
import threading
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import run  # noqa: E402
from styles import list_templates  # noqa: E402
from options import FORMATS, LANGS  # noqa: E402

import webview  # noqa: E402

APP_NAME = '剧本双语拆分工具'
PORT_BASE = 26810
PORT_RANGE = 20
PING_PATH = '/__app_ping__'
PING_BODY = b'script-splitter-web-v1'


# ─────────────────────────────────────────────────────────
# 路径与持久化
# ─────────────────────────────────────────────────────────
def _resource_root():
    """页面 / 资源根目录：冻结后在 _MEIPASS，开发时在 src/。"""
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        return meipass
    return os.path.dirname(os.path.abspath(__file__))


def web_root():
    return os.path.join(_resource_root(), 'web')


def data_dir():
    override = os.environ.get('SCRIPT_SPLITTER_DATA_ROOT')
    if override:
        os.makedirs(override, exist_ok=True)
        return override
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    d = os.path.join(base, 'ScriptSplitter')
    os.makedirs(d, exist_ok=True)
    return d


def _settings_path():
    return os.path.join(data_dir(), 'settings.json')


def load_settings():
    try:
        with open(_settings_path(), encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(patch):
    cur = load_settings()
    cur.update(patch or {})
    try:
        with open(_settings_path(), 'w', encoding='utf-8') as f:
            json.dump(cur, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return cur


def read_version():
    for candidate in (os.path.join(_resource_root(), 'VERSION'),
                      os.path.join(os.path.dirname(_resource_root()), 'VERSION')):
        try:
            with open(candidate, encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            continue
    return '0.2.0'


VERSION = read_version()


# ─────────────────────────────────────────────────────────
# 内置页面服务
# ─────────────────────────────────────────────────────────
class _Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        http.server.SimpleHTTPRequestHandler.end_headers(self)

    def do_GET(self):
        if self.path.split('?')[0] == PING_PATH:
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            body = PING_BODY
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        http.server.SimpleHTTPRequestHandler.do_GET(self)


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def start_page_server(root):
    handler = functools.partial(_Handler, directory=root)
    for i in range(PORT_RANGE):
        port = PORT_BASE + i
        try:
            srv = _Server(('127.0.0.1', port), handler)
        except OSError:
            continue
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv, port
    raise OSError('端口 %d~%d 全被占用' % (PORT_BASE, PORT_BASE + PORT_RANGE - 1))


def page_url(port):
    return 'http://127.0.0.1:%d/index.html' % port


# ─────────────────────────────────────────────────────────
# 暴露给前端的原生能力
# ─────────────────────────────────────────────────────────
def _level(msg):
    if any(w in msg for w in ('失败', '错误', '异常', 'Traceback')):
        return 'fail'
    if any(w in msg for w in ('缺中文', '提示', '缺翻译')):
        return 'warn'
    if any(w in msg for w in ('完成', '输出', '识别到', '排版')):
        return 'ok'
    return 'info'


class Api:
    def __init__(self):
        self._win = None
        self._last_out = None

    def bind_window(self, win):
        self._win = win

    def _push(self, fn, *args):
        win = webview.active_window() or self._win
        if win is None:
            return
        try:
            payload = json.dumps(args, ensure_ascii=False)
            win.evaluate_js('window.%s.apply(null, %s)' % (fn, payload))
        except Exception:
            pass

    # ── 初始信息 ──
    def app_info(self):
        s = load_settings()
        return {
            'version': VERSION,
            'templates': list_templates(),
            'formats': FORMATS,
            'langs': LANGS,
            'settings': {
                'theme': s.get('theme', 'dark'),
                'lang': s.get('lang', 'auto'),
                'only_body': s.get('only_body', True),
                'strip_rev': s.get('strip_rev', True),
                'template': s.get('template'),
                'beautify': s.get('beautify', True),
                'toc': s.get('toc', True),
                'hf': s.get('hf', True),
                'fmts': s.get('fmts', {}),
                'out_dir': s.get('out_dir', ''),
            },
        }

    # ── 对话框 ──
    def pick_file(self):
        win = self._win or webview.active_window()
        try:
            res = win.create_file_dialog(
                webview.OPEN_DIALOG,
                file_types=('Word 文档 (*.docx)', '*.docx'),
                allow_multiple=False)
            if isinstance(res, (list, tuple)):
                return res[0] if res else ''
            return res or ''
        except Exception as e:
            self._push('__onLog', '文件选择失败: %s' % e, 'fail')
            return ''

    def pick_dir(self):
        win = self._win or webview.active_window()
        try:
            res = win.create_file_dialog(webview.FOLDER_DIALOG)
            if isinstance(res, (list, tuple)):
                return res[0] if res else ''
            return res or ''
        except Exception as e:
            self._push('__onLog', '目录选择失败: %s' % e, 'fail')
            return ''

    # ── 拆分（后台线程，日志/结果经回调推送） ──
    def run_split(self, opts):
        threading.Thread(target=self._worker, args=(opts,), daemon=True).start()
        return {'started': True}

    def _worker(self, opts):
        path = (opts.get('path') or '').strip()
        if not path:
            self._push('__onError', '未选择剧本文件')
            return
        if not os.path.isfile(path):
            self._push('__onError', '文件不存在: %s' % path)
            return

        # 记住上次选项
        save_settings({
            'lang': opts.get('lang', 'auto'),
            'only_body': bool(opts.get('only_body', True)),
            'strip_rev': bool(opts.get('strip_rev', True)),
            'template': opts.get('template', 'cn'),
            'beautify': bool(opts.get('beautify', True)),
            'toc': bool(opts.get('toc', True)),
            'hf': bool(opts.get('hf', True)),
            'fmts': {k: True for k in (opts.get('formats') or [])},
            'out_dir': opts.get('out_dir') or '',
        })

        def log_cb(msg):
            self._push('__onLog', msg, _level(msg))

        try:
            outputs, records, _lang = run(
                path,
                out_dir=opts.get('out_dir') or None,
                formats=opts.get('formats') or ['csv'],
                only_body=bool(opts.get('only_body', True)),
                strip_rev=bool(opts.get('strip_rev', True)),
                lang=opts.get('lang', 'auto'),
                template=opts.get('template', 'cn'),
                beautify=bool(opts.get('beautify', True)),
                toc=bool(opts.get('toc', True)),
                hf=bool(opts.get('hf', True)),
                log=log_cb,
            )
            miss = sum(1 for r in records if not r['zh'])
            out_dir = os.path.dirname(outputs[0]) if outputs else os.path.dirname(path)
            self._last_out = out_dir
            self._push('__onDone', {
                'out_dir': out_dir,
                'outputs': outputs,
                'missing': miss,
            })
        except Exception as e:
            self._push('__onError', '%s: %s' % (type(e).__name__, e))

    def open_path(self, path):
        path = (path or '').strip()
        if not path:
            return False
        try:
            os.startfile(path)  # noqa: S606
            return True
        except Exception:
            try:
                import subprocess
                subprocess.Popen(['explorer', path])
                return True
            except Exception:
                return False

    def save_settings(self, patch):
        save_settings(patch or {})
        return {'ok': True}


# ─────────────────────────────────────────────────────────
# 启动
# ─────────────────────────────────────────────────────────
def find_edge():
    for p in (r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
              r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'):
        if os.path.isfile(p):
            return p
    return None


def run_browser_app(url):
    exe = find_edge()
    if not exe:
        print('[失败] 未找到 Edge，无法启动应用窗口')
        return False
    import subprocess
    profile = os.path.join(data_dir(), 'edge-profile')
    os.makedirs(profile, exist_ok=True)
    subprocess.Popen([
        exe, '--app=' + url,
        '--user-data-dir=' + profile,
        '--window-size=1120,780',
        '--no-first-run', '--no-default-browser-check',
    ])
    return True


def main():
    root = web_root()
    html = os.path.join(root, 'index.html')
    if not os.path.isfile(html):
        print('[失败] 找不到页面文件: %s' % html)
        return 1

    _srv, port = start_page_server(root)
    url = page_url(port)
    print('[server] %s' % url)

    api = Api()
    window = webview.create_window(
        '%s  v%s' % (APP_NAME, VERSION),
        url=url,
        js_api=api,
        width=1120,
        height=780,
        min_size=(960, 640),
        background_color='#162023',
        text_select=True,
    )
    api.bind_window(window)

    storage = os.path.join(data_dir(), 'webview-data')
    os.makedirs(storage, exist_ok=True)
    try:
        webview.start(private_mode=False, storage_path=storage,
                      gui='edgechromium',
                      icon=os.path.join(_resource_root(), 'app.ico'))
    except Exception as e:
        print('[fallback] pywebview 启动失败 (%s)，转 Edge --app' % e)
        return 0 if run_browser_app(url) else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
