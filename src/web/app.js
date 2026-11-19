/* 剧本双语拆分 · 前端逻辑（pywebview 桥接）
   结构：命令栏（选文件 / 开始）/ 设置区（拆分·排版·导出·输出）/ 检查器 / 日志坞。 */
'use strict';

const $ = (id) => document.getElementById(id);
const api = () => (window.pywebview && window.pywebview.api) || null;

const STATE = {
  info: null,
  settings: {},
  busy: false,
  lastOut: '',
  outputs: [],
};

const FALLBACK = {
  lang: { auto: '自动识别', pt: '葡萄牙语', en: '英语' },
  template: { cn: '中文短剧阅读版', hollywood: '好莱坞标准格式' },
};

// ── 本地偏好（日志坞开合） ────────────────────────────────
const store = {
  get(key, fallback) {
    try {
      const v = localStorage.getItem(key);
      return v === null ? fallback : JSON.parse(v);
    } catch (e) { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* 存储不可用仍可操作 */ }
  },
};

// ── 小工具 ───────────────────────────────────────────────
function basename(p) {
  const s = String(p || '').replace(/[\\/]+$/, '');
  const i = Math.max(s.lastIndexOf('\\'), s.lastIndexOf('/'));
  return i >= 0 ? s.slice(i + 1) : s;
}

function splitName(p) {
  const base = basename(p);
  const i = base.lastIndexOf('.');
  if (i <= 0) return { name: base, ext: '' };
  return { name: base.slice(0, i), ext: base.slice(i + 1).toUpperCase() };
}

function labelFor(kind, key) {
  const info = STATE.info;
  const items = info && (kind === 'lang' ? info.langs : info.templates);
  if (items) {
    const hit = items.find((it) => it[0] === key);
    if (hit) return hit[1];
  }
  return (FALLBACK[kind] && FALLBACK[kind][key]) || key;
}

function checkedValue(name, fallback) {
  const el = document.querySelector('input[name="' + name + '"]:checked');
  return el ? el.value : fallback;
}

function shortLabel(text) {
  return String(text || '').split(/（|\(/)[0].trim();
}

// ── 日志 ─────────────────────────────────────────────────
function refreshLogMeta() {
  const log = $('log');
  const lines = [...log.querySelectorAll('.line:not(.hint)')];
  const last = lines[lines.length - 1];

  $('logMeta').textContent = lines.length + ' 行';

  if (!last) {
    $('logPreview').textContent = '暂无日志';
    $('logDot').className = 'log-dot';
    $('logCount').hidden = true;
    return;
  }
  $('logPreview').textContent = last.textContent.trim();
  const level = [...last.classList].find((c) => ['ok', 'fail', 'warn', 'info'].includes(c));
  $('logDot').className = 'log-dot' + (level ? ' ' + level : '');
  $('logCount').hidden = false;
  $('logCount').textContent = lines.length + ' 条';
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

// ── 日志坞开合 ───────────────────────────────────────────
function setLogOpen(open) {
  $('logPanel').hidden = !open;
  $('logBar').setAttribute('aria-expanded', String(open));
  $('logChev').style.transform = open ? 'rotate(0deg)' : 'rotate(-90deg)';
  store.set('ss.logOpen', open);
  if (open) $('log').scrollTop = $('log').scrollHeight;
}

// ── 主题 / 强调色 ────────────────────────────────────────
const ACCENTS = ['gold', 'blue'];   // 只保留金色与冷蓝；旧设置里的其他值回退为冷蓝

function applyTheme(theme) {
  document.body.dataset.theme = theme;
  $('themeToggle').textContent = theme === 'dark' ? '浅色' : '暗色';
  $('themeToggle').title = theme === 'dark' ? '切换到浅色' : '切换到暗色';
}

function applyAccent(accent) {
  const next = ACCENTS.includes(accent) ? accent : 'blue';
  document.body.dataset.accent = next;
  document.querySelectorAll('.theme-swatch').forEach((sw) => {
    sw.setAttribute('aria-pressed', String(sw.dataset.accent === next));
  });
  return next;
}

async function savePatch(patch) {
  const a = api();
  if (!a || !a.save_settings) return;
  try { await a.save_settings(patch); } catch (e) { /* 偏好写入失败不影响主流程 */ }
}

function toggleTheme() {
  const next = document.body.dataset.theme === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  savePatch({ theme: next });
}

function pickAccent(accent) {
  applyAccent(accent);
  savePatch({ accent });
}

// ── 表单渲染 ─────────────────────────────────────────────
function renderRadios(containerId, name, items, current) {
  const box = $(containerId);
  box.innerHTML = '';
  items.forEach(([key, label]) => {
    const lab = document.createElement('label');
    lab.className = 'chip';
    const r = document.createElement('input');
    r.type = 'radio';
    r.name = name;
    r.value = key;
    if (key === current) r.checked = true;
    const dot = document.createElement('i');
    dot.className = 'chip-dot';
    dot.setAttribute('aria-hidden', 'true');
    const span = document.createElement('span');
    span.textContent = label;
    lab.append(r, dot, span);
    box.appendChild(lab);
  });
  syncChips();
}

function applyFormats(formats, savedFmts) {
  const box = $('fmtList');
  box.innerHTML = '';
  formats.forEach(([key, label, def]) => {
    const lab = document.createElement('label');
    lab.className = 'fmt-row';
    const c = document.createElement('input');
    c.type = 'checkbox';
    c.value = key;
    c.checked = (savedFmts && typeof savedFmts[key] === 'boolean') ? savedFmts[key] : !!def;
    const code = document.createElement('code');
    code.textContent = key;
    const span = document.createElement('span');
    span.textContent = shortLabel(label);
    span.title = label;
    lab.append(c, code, span);
    box.appendChild(lab);
  });
}

function syncChips() {
  document.querySelectorAll('.chip').forEach((chip) => {
    const input = chip.querySelector('input');
    chip.classList.toggle('is-on', !!(input && input.checked));
  });
}

function collectFormats() {
  return [...document.querySelectorAll('#fmtList input:checked')].map((c) => c.value);
}

// ── 派生显示 ─────────────────────────────────────────────
function derivedOutDir() {
  const explicit = $('outDir').value.trim();
  if (explicit) return explicit;
  const file = $('filePath').value.trim();
  if (!file) return '同级 _split';
  const dir = file.replace(/[\\/][^\\/]+$/, '');
  const name = basename(file).replace(/\.docx$/i, '');
  return (dir ? dir + '\\' : '') + name + '_split';
}

function refreshDerived() {
  const file = $('filePath').value.trim();
  const fmt = collectFormats();
  const total = document.querySelectorAll('#fmtList input').length;
  const langKey = checkedValue('lang', 'auto');
  const tplKey = checkedValue('template', 'cn');
  const langLabel = labelFor('lang', langKey);
  const tplLabel = labelFor('template', tplKey);

  $('fileSummary').textContent = file ? basename(file) : '未选择文件';
  $('ddFile').textContent = file ? basename(file) : '—';
  $('ddFile').title = file;

  const out = derivedOutDir();
  $('ddOut').textContent = out === '同级 _split' ? out : basename(out);
  $('ddOut').title = out;

  $('ddLang').textContent = langLabel;
  $('ddTpl').textContent = tplLabel;
  $('ddFmt').textContent = fmt.length + ' 项';
  $('fmtCount').textContent = fmt.length + ' / ' + total;
  $('fmtSummary').textContent = fmt.length === 0
    ? '未选格式'
    : (fmt.length === 1 ? fmt[0].replace(/_docx$/, '').toUpperCase() : fmt.length + ' 项导出');
  $('optionSummary').textContent = langLabel + ' · ' + shortLabel(tplLabel);
}

// ── 运行状态 ─────────────────────────────────────────────
function setPhase(code, text, note, tone) {
  $('runPhase').textContent = code;
  $('runLine').textContent = text;
  $('runLine').className = 'run-line' + (tone ? ' is-' + tone : '');
  if (note !== undefined) $('runNote').textContent = note;
}

function setBusy(busy) {
  STATE.busy = busy;
  $('startBtn').disabled = busy;
  $('startBtn').textContent = busy ? '处理中…' : '开始拆分';
  $('progress').hidden = !busy;
}

// ── 结果列表 ─────────────────────────────────────────────
function renderResults(list) {
  const ul = $('resultList');
  ul.innerHTML = '';
  STATE.outputs = list || [];
  $('resultCount').textContent = String(STATE.outputs.length);

  if (!STATE.outputs.length) {
    const li = document.createElement('li');
    li.className = 'result-empty';
    li.textContent = '暂无输出';
    ul.appendChild(li);
    return;
  }

  STATE.outputs.forEach((p) => {
    const li = document.createElement('li');
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'result-row';
    btn.title = '打开 ' + p;

    const { name, ext } = splitName(p);
    const nameEl = document.createElement('span');
    nameEl.className = 'name';
    nameEl.textContent = name;
    btn.appendChild(nameEl);

    if (ext) {
      const extEl = document.createElement('span');
      extEl.className = 'ext';
      extEl.textContent = ext;
      btn.appendChild(extEl);
    }

    btn.addEventListener('click', () => openPath(p));
    li.appendChild(btn);
    ul.appendChild(li);
  });
}

async function openPath(path) {
  const a = api();
  if (!a || !a.open_path) return;
  const ok = await a.open_path(path);
  if (!ok) appendLog('无法打开: ' + path, 'fail');
}

// ── 选择文件 / 目录 ─────────────────────────────────────
async function pickFile() {
  const a = api();
  if (!a || !a.pick_file) return;
  const p = await a.pick_file();
  if (!p) return;
  $('filePath').value = p;
  STATE.lastOut = '';
  $('warnLine').hidden = true;
  renderResults([]);
  refreshDerived();
  if (!STATE.busy) {
    setPhase('READY', '已选择剧本', basename(p) + ' · 就绪', null);
    $('statusText').textContent = '已选择 ' + basename(p);
  }
}

async function pickDir() {
  const a = api();
  if (!a || !a.pick_dir) return;
  const p = await a.pick_dir();
  if (!p) return;
  $('outDir').value = p;
  refreshDerived();
}

// ── 收集选项 ─────────────────────────────────────────────
function collectOpts() {
  return {
    path: $('filePath').value.trim(),
    out_dir: $('outDir').value.trim() || null,
    lang: checkedValue('lang', 'auto'),
    only_body: $('onlyBody').checked,
    strip_rev: $('stripRev').checked,
    template: checkedValue('template', 'cn'),
    beautify: $('beautify').checked,
    toc: $('toc').checked,
    hf: $('hf').checked,
    formats: collectFormats(),
  };
}

// ── 开始拆分 ─────────────────────────────────────────────
async function runSplit() {
  const a = api();
  if (!a || STATE.busy) return;

  const opts = collectOpts();
  if (!opts.path) {
    setPhase('WAIT', '缺少剧本', '先点「浏览…」选择 .docx 剧本。', 'warn');
    appendLog('请先选择剧本 .docx 文件', 'warn');
    setLogOpen(true);
    return;
  }
  if (!opts.formats.length) {
    setPhase('WAIT', '缺少导出格式', '至少勾选一种导出格式。', 'warn');
    appendLog('请至少勾选一种导出格式', 'warn');
    setLogOpen(true);
    return;
  }

  STATE.lastOut = '';
  $('warnLine').hidden = true;
  renderResults([]);
  clearLog();
  setBusy(true);
  setLogOpen(true);
  setPhase('RUN', '正在拆分…', '解析 docx · 识别语种 · 生成导出文件', 'run');
  $('statusText').textContent = '正在拆分 ' + basename(opts.path);
  appendLog('开始处理: ' + opts.path, 'info');

  try {
    await a.run_split(opts);
  } catch (e) {
    setBusy(false);
    setPhase('ERR', '启动失败', String(e), 'err');
    appendLog('启动失败: ' + e, 'fail');
    $('statusText').textContent = '启动失败';
  }
}

async function openOut() {
  const a = api();
  if (!a || !a.open_path) return;
  const dir = STATE.lastOut || (($('outDir').value.trim()) || '');
  if (!dir) {
    appendLog('还没有可打开的输出目录', 'warn');
    setPhase('READY', '就绪', '先跑一次拆分，或手动指定输出目录。', 'warn');
    setLogOpen(true);
    return;
  }
  await a.open_path(dir);
}

// ── Python 回调入口 ─────────────────────────────────────
window.__onLog = (line, level) => appendLog(line, level);

window.__onDone = (res) => {
  res = res || {};
  setBusy(false);
  STATE.lastOut = res.out_dir || '';
  const outputs = res.outputs || [];
  renderResults(outputs);

  const n = outputs.length;
  setPhase(
    n ? 'DONE' : 'WARN',
    n ? '完成 · ' + n + ' 个文件' : '处理完成 · 无输出',
    n ? '点右侧文件名可直接打开。' : '没有生成文件，查看运行日志。',
    n ? 'ok' : 'warn',
  );

  if (res.missing) {
    $('warnLine').hidden = false;
    $('warnLine').textContent = '缺中文翻译 ' + res.missing + ' 条，已标 [待补中文]';
  } else {
    $('warnLine').hidden = true;
  }

  if (n) {
    appendLog('完成，共输出 ' + n + ' 个文件：', 'ok');
    outputs.forEach((o) => appendLog('  ' + o));
  } else {
    appendLog('处理完成，未生成文件', 'warn');
  }
  if (res.missing) appendLog('提示：' + res.missing + ' 条台词缺中文翻译', 'warn');

  $('statusText').textContent = n ? '已输出 ' + n + ' 个文件' : '处理完成，无输出';
};

window.__onError = (msg) => {
  setBusy(false);
  setPhase('ERR', '失败', '查看运行日志中的错误信息。', 'err');
  appendLog('失败: ' + msg, 'fail');
  $('statusText').textContent = '拆分失败';
  setLogOpen(true);
};

// ── 分区跳转 ─────────────────────────────────────────────
function initNav() {
  const scroll = $('settingsScroll');
  const buttons = [...document.querySelectorAll('nav button[data-jump]')];

  buttons.forEach((btn) => {
    btn.addEventListener('click', () => {
      buttons.forEach((b) => b.removeAttribute('aria-current'));
      btn.setAttribute('aria-current', 'page');
      const panel = $(btn.dataset.jump);
      if (panel) {
        const delta = panel.getBoundingClientRect().top - scroll.getBoundingClientRect().top - 14;
        scroll.scrollTo({ top: scroll.scrollTop + delta, behavior: 'smooth' });
      }
    });
  });

  scroll.addEventListener('scroll', () => {
    const box = scroll.getBoundingClientRect();
    // 到底部时最后一块只露出一半，按面积会误判成上一块：直接取最后一块。
    if (scroll.scrollTop + scroll.clientHeight >= scroll.scrollHeight - 2) {
      buttons.forEach((b) => {
        if (b === buttons[buttons.length - 1]) b.setAttribute('aria-current', 'page');
        else b.removeAttribute('aria-current');
      });
      return;
    }

    let active = buttons[0];
    let bestArea = -1;
    buttons.forEach((b) => {
      const panel = $(b.dataset.jump);
      if (!panel) return;
      const r = panel.getBoundingClientRect();
      const visible = Math.min(r.bottom, box.bottom) - Math.max(r.top, box.top);
      if (visible > bestArea) { bestArea = visible; active = b; }
    });
    buttons.forEach((b) => {
      if (b === active) b.setAttribute('aria-current', 'page');
      else b.removeAttribute('aria-current');
    });
  }, { passive: true });
}

// ── 初始化 ───────────────────────────────────────────────
async function init() {
  const a = api();
  if (!a) return;

  let info;
  try {
    info = await a.app_info();
  } catch (e) {
    appendLog('初始化失败: ' + e, 'fail');
    setPhase('ERR', '初始化失败', String(e), 'err');
    return;
  }

  STATE.info = info;
  const s = info.settings || {};
  STATE.settings = s;

  $('appVersion').textContent = 'v' + info.version;
  $('statusVersion').textContent = 'v' + info.version;

  renderRadios('langRow', 'lang', info.langs || [], s.lang || 'auto');
  renderRadios('tplRow', 'template', info.templates || [], s.template || ((info.templates && info.templates[0] && info.templates[0][0]) || 'cn'));
  if (info.formats) applyFormats(info.formats, s.fmts);

  $('onlyBody').checked = s.only_body !== false;
  $('stripRev').checked = s.strip_rev !== false;
  $('beautify').checked = s.beautify !== false;
  $('toc').checked = s.toc !== false;
  $('hf').checked = s.hf !== false;
  if (s.out_dir) $('outDir').value = s.out_dir;

  applyTheme(s.theme || 'dark');
  const accent = applyAccent(s.accent || 'blue');
  // 旧版本可能存过青绿 / 烟紫，迁移到冷蓝并写回，避免每次启动都回退。
  if (s.accent && s.accent !== accent) savePatch({ accent });
  setLogOpen(!!store.get('ss.logOpen', false));
  showPlaceholder();
  setPhase('READY', '就绪', '选择剧本后点「开始拆分」。', null);
  refreshDerived();
}

// ── 静态事件 ─────────────────────────────────────────────
function bindStatic() {
  $('browseFile').addEventListener('click', pickFile);
  $('browseDir').addEventListener('click', pickDir);
  $('startBtn').addEventListener('click', runSplit);
  $('openOut').addEventListener('click', openOut);
  $('themeToggle').addEventListener('click', toggleTheme);
  $('clearLog').addEventListener('click', clearLog);
  $('logBar').addEventListener('click', () => setLogOpen($('logPanel').hidden));

  document.querySelectorAll('.theme-swatch').forEach((sw) => {
    sw.addEventListener('click', () => pickAccent(sw.dataset.accent));
  });

  document.addEventListener('change', (e) => {
    const el = e.target;
    if (el.matches('input[name="lang"], input[name="template"]')) syncChips();
    if (el.matches('#fmtList input, input[name="lang"], input[name="template"]')) refreshDerived();
  });

  $('outDir').addEventListener('input', refreshDerived);

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      runSplit();
    }
  });

  initNav();
}

// ── 启动 ─────────────────────────────────────────────────
boot();

async function boot() {
  bindStatic();
  if (window.pywebview && window.pywebview.api) { await init(); return; }
  window.addEventListener('pywebviewready', init);
  // 兜底轮询：个别 WebView 版本事件时序不同
  const timer = setInterval(() => {
    if (window.pywebview && window.pywebview.api) {
      clearInterval(timer);
      init();
    }
  }, 120);
}
