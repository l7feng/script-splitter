/* 剧本双语拆分 · 前端逻辑（pywebview 桥接） */
'use strict';

const $ = (id) => document.getElementById(id);
let STATE = { settings: {}, lastOut: '', busy: false };

const api = () => (window.pywebview && window.pywebview.api) || null;

// ── 本地偏好（折叠状态 / 日志坞开合） ─────────────────────
const store = {
  get(key, fallback) {
    try {
      const v = localStorage.getItem(key);
      return v === null ? fallback : JSON.parse(v);
    } catch (e) { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {}
  },
};

// ── 日志 ──────────────────────────────────────────────
function refreshLogMeta() {
  const log = $('log');
  const lines = [...log.querySelectorAll('.line:not(.hint)')];
  const last = lines[lines.length - 1];
  const preview = $('logPreview');
  const dot = $('logDot');
  const count = $('logCount');

  if (!last) {
    preview.textContent = '暂无日志';
    dot.className = 'log-dot';
    count.hidden = true;
    return;
  }
  preview.textContent = last.textContent.trim();
  const level = [...last.classList].find((c) => ['ok', 'fail', 'warn', 'info'].includes(c));
  dot.className = 'log-dot' + (level ? ' ' + level : '');
  count.hidden = false;
  count.textContent = lines.length + ' 条';
}

function appendLog(text, level) {
  const log = $('log');
  const ph = log.querySelector('.hint');
  if (ph) ph.remove();
  const div = document.createElement('div');
  div.className = 'line' + (level ? ' ' + level : '');
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  refreshLogMeta();
}

function clearLog() {
  $('log').innerHTML = '';
  refreshLogMeta();
}

function showPlaceholder() {
  $('log').innerHTML = '<div class="line hint">—— 选择 .docx 剧本，点「开始拆分」——</div>';
  refreshLogMeta();
}

// ── 卡片折叠 ───────────────────────────────────────────
function setCardCollapsed(card, collapsed) {
  card.classList.toggle('collapsed', collapsed);
  const head = card.querySelector('.card-head');
  if (head) head.setAttribute('aria-expanded', String(!collapsed));
}

function initCollapsibles() {
  const saved = store.get('ss.cards', {});
  document.querySelectorAll('.collapsible').forEach((card) => {
    const key = card.dataset.card;
    setCardCollapsed(card, !!saved[key]);
    const head = card.querySelector('.card-head');
    head.addEventListener('click', () => {
      const next = !card.classList.contains('collapsed');
      setCardCollapsed(card, next);
      saved[key] = next;
      store.set('ss.cards', saved);
    });
  });
}

// ── 日志坞开合 ────────────────────────────────────────
function setLogOpen(open) {
  $('logPanel').hidden = !open;
  $('logBar').setAttribute('aria-expanded', String(open));
  $('logChev').style.transform = open ? 'rotate(0deg)' : 'rotate(-90deg)';
  store.set('ss.logOpen', open);
  if (open) {
    const log = $('log');
    log.scrollTop = log.scrollHeight;
  }
}

function initLogDock() {
  setLogOpen(!!store.get('ss.logOpen', false));
  $('logBar').addEventListener('click', () => setLogOpen($('logPanel').hidden));
  $('clearLog').addEventListener('click', clearLog);
}

// ── 表单渲染 ──────────────────────────────────────────
function renderRadios(containerId, name, items, current) {
  const box = $(containerId);
  box.innerHTML = '';
  for (const [key, label] of items) {
    const lab = document.createElement('label');
    const r = document.createElement('input');
    r.type = 'radio'; r.name = name; r.value = key;
    if (key === current) r.checked = true;
    lab.appendChild(r);
    lab.appendChild(document.createTextNode(label));
    box.appendChild(lab);
  }
}

function renderFormats(formats, savedFmts) {
  const box = $('fmtList');
  box.innerHTML = '';
  for (const [key, label, def] of formats) {
    const lab = document.createElement('label');
    lab.className = 'check';
    const c = document.createElement('input');
    c.type = 'checkbox'; c.value = key;
    c.checked = (savedFmts && typeof savedFmts[key] === 'boolean') ? savedFmts[key] : def;
    lab.appendChild(c);
    lab.appendChild(document.createTextNode(label));
    box.appendChild(lab);
  }
}

function collectFormats() {
  return [...document.querySelectorAll('#fmtList input:checked')].map((c) => c.value);
}

// ── 主题 ──────────────────────────────────────────────
function applyTheme(t) {
  document.body.dataset.theme = t;
  $('themeToggle').textContent = t === 'dark' ? '◐ 浅色' : '◑ 暗色';
}

async function toggleTheme() {
  const next = document.body.dataset.theme === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  const a = api();
  if (a && a.save_settings) { try { await a.save_settings({ theme: next }); } catch (e) {} }
}

// ── 初始化 ────────────────────────────────────────────
async function init() {
  const a = api();
  if (!a) return;
  let info;
  try { info = await a.app_info(); } catch (e) { appendLog('初始化失败: ' + e, 'fail'); return; }

  STATE.settings = info.settings || {};
  $('appVersion').textContent = 'v' + info.version;

  const s = STATE.settings;
  renderRadios('langRow', 'lang', info.langs, s.lang || 'auto');
  renderRadios('tplRow', 'template', info.templates, s.template || info.templates[0][0]);
  renderFormats(info.formats, s.fmts);

  $('onlyBody').checked = s.only_body !== false;
  $('stripRev').checked = s.strip_rev !== false;
  $('beautify').checked = s.beautify !== false;
  $('toc').checked = s.toc !== false;
  $('hf').checked = s.hf !== false;
  if (s.out_dir) $('outDir').value = s.out_dir;

  applyTheme(s.theme || 'dark');
  showPlaceholder();
}

// ── 收集选项 ──────────────────────────────────────────
function collectOpts() {
  const lang = document.querySelector('input[name="lang"]:checked');
  const tpl = document.querySelector('input[name="template"]:checked');
  return {
    path: $('filePath').value.trim(),
    out_dir: $('outDir').value.trim() || null,
    lang: lang ? lang.value : 'auto',
    only_body: $('onlyBody').checked,
    strip_rev: $('stripRev').checked,
    template: tpl ? tpl.value : 'cn',
    beautify: $('beautify').checked,
    toc: $('toc').checked,
    hf: $('hf').checked,
    formats: collectFormats(),
  };
}

function setBusy(busy) {
  STATE.busy = busy;
  $('startBtn').disabled = busy;
  $('progress').hidden = !busy;
}

// ── 动作 ──────────────────────────────────────────────
async function pickFile() {
  const a = api(); if (!a) return;
  const p = await a.pick_file();
  if (p) $('filePath').value = p;
}

async function pickDir() {
  const a = api(); if (!a) return;
  const p = await a.pick_dir();
  if (p) $('outDir').value = p;
}

async function runSplit() {
  const a = api(); if (!a || STATE.busy) return;
  const opts = collectOpts();
  if (!opts.path) { appendLog('请先选择剧本 .docx 文件', 'warn'); return; }
  if (!opts.formats.length) { appendLog('请至少勾选一种导出格式', 'warn'); return; }

  setBusy(true);
  clearLog();
  appendLog('开始处理: ' + opts.path, 'info');
  try {
    await a.run_split(opts);
  } catch (e) {
    appendLog('启动失败: ' + e, 'fail');
    setBusy(false);
  }
}

async function openOut() {
  const a = api(); if (!a) return;
  const dir = STATE.lastOut || $('outDir').value.trim();
  if (!dir) { appendLog('还没有可打开的输出目录', 'warn'); return; }
  await a.open_path(dir);
}

// ── Python 回调入口 ──────────────────────────────────
window.__onLog = (line, level) => appendLog(line, level);
window.__onDone = (res) => {
  setBusy(false);
  STATE.lastOut = res.out_dir || '';
  if (res.outputs && res.outputs.length) {
    appendLog('完成，共输出 %d 个文件：'.replace('%d', res.outputs.length), 'ok');
    for (const o of res.outputs) appendLog('  ' + o);
  } else {
    appendLog('处理完成，未生成文件', 'warn');
  }
  if (res.missing) appendLog('提示：%d 条台词缺中文翻译'.replace('%d', res.missing), 'warn');
};
window.__onError = (msg) => {
  setBusy(false);
  appendLog('失败: ' + msg, 'fail');
};

// ── 绑定静态事件 ───────────────────────────────────────
function bindStatic() {
  $('browseFile').addEventListener('click', pickFile);
  $('browseDir').addEventListener('click', pickDir);
  $('startBtn').addEventListener('click', runSplit);
  $('openOut').addEventListener('click', openOut);
  $('themeToggle').addEventListener('click', toggleTheme);
  initCollapsibles();
  initLogDock();
}

boot();
async function boot() {
  bindStatic();
  if (window.pywebview && window.pywebview.api) { await init(); return; }
  window.addEventListener('pywebviewready', init);
  // 兜底轮询：个别 WebView 版本事件时序不同
  const t = setInterval(() => {
    if (window.pywebview && window.pywebview.api) { clearInterval(t); init(); }
  }, 120);
}
