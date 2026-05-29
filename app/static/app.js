'use strict';
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const key = () => $('key').value.trim();
const pid = () => $('pid').value.trim();
const lang = () => $('lang').value;

let pollTimer = null;

/* ---------- settings persistence ---------- */
function loadSettings() {
  $('key').value = localStorage.getItem('av_key') || '';
  $('pid').value = localStorage.getItem('av_pid') || 'PROJ-3132';
  $('lang').value = localStorage.getItem('av_lang') || 'English';
  ['key', 'pid', 'lang'].forEach((id) =>
    $(id).addEventListener('change', () => {
      localStorage.setItem('av_' + id, $(id).value);
      updateConn();
    }));
  updateConn();
}
function updateConn() {
  const el = $('connState');
  if (key()) { el.textContent = 'Key set · ' + pid(); el.className = 'env-badge ok'; }
  else { el.textContent = 'No API key'; el.className = 'env-badge bad'; }
}

/* ---------- generic request ---------- */
async function api(path, opts = {}) {
  const headers = Object.assign({ 'X-API-KEY': key() }, opts.headers || {});
  const res = await fetch(path, Object.assign({}, opts, { headers }));
  let body = null;
  try { body = await res.json(); } catch { /* non-json */ }
  if (!res.ok) {
    const msg = (body && (body.detail || body.message)) || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return body;
}
function toast(msg, kind = '') {
  const t = $('toast');
  t.textContent = msg;
  t.className = 'toast ' + kind;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.className = 'toast hidden'; }, 4200);
}
function busy(btn, on, label) {
  if (on) { btn.dataset.label = btn.innerHTML; btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>${label}`; }
  else { btn.disabled = false; btn.innerHTML = btn.dataset.label || label; }
}

/* ---------- file selection ---------- */
function initDropzone() {
  const dz = $('dropzone'), input = $('files');
  input.addEventListener('change', () => showFileCount(input.files));
  ['dragover', 'dragenter'].forEach((e) =>
    dz.addEventListener(e, (ev) => { ev.preventDefault(); dz.classList.add('drag'); }));
  ['dragleave', 'drop'].forEach((e) =>
    dz.addEventListener(e, (ev) => { ev.preventDefault(); dz.classList.remove('drag'); }));
  dz.addEventListener('drop', (ev) => { input.files = ev.dataTransfer.files; showFileCount(input.files); });
}
function showFileCount(files) {
  $('fileCount').textContent = files && files.length
    ? `${files.length} file${files.length > 1 ? 's' : ''} selected`
    : 'No files selected';
}

/* ---------- 1. upload + index ---------- */
async function uploadAndIndex() {
  if (!key()) return toast('Enter your API key first', 'error');
  const files = $('files').files;
  if (!files.length) return toast('Choose at least one photo', 'error');
  const btn = $('indexBtn');
  busy(btn, true, 'Uploading...');
  try {
    const fd = new FormData();
    for (const f of files) fd.append('files', f);
    const up = await api('/api/v1/uploads', { method: 'POST', body: fd });
    busy(btn, true, 'Indexing...');
    await api('/api/v1/projects/index', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: pid(), image_urls: up.image_urls }),
    });
    toast(`Indexing ${up.image_urls.length} photo(s) started`, 'success');
    $('statusPanel').classList.remove('hidden');
    startPolling();
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    busy(btn, false, 'Upload & Index');
  }
}

function startPolling() {
  clearInterval(pollTimer);
  refreshStatus();
  pollTimer = setInterval(refreshStatus, 2500);
}

async function refreshStatus() {
  if (!key()) return;
  try {
    const st = await api(`/api/v1/projects/${encodeURIComponent(pid())}/status`);
    $('statusPanel').classList.remove('hidden');
    renderStatus(st);
    if (['completed', 'partial', 'failed'].includes(st.status)) clearInterval(pollTimer);
  } catch (e) {
    clearInterval(pollTimer);
    if (!/404/.test(e.message)) toast(e.message, 'error');
  }
}

function renderStatus(st) {
  $('statusBadge').textContent = st.status;
  $('statusBadge').className = 'status-badge ' + st.status;
  const pct = st.total_images ? Math.round((st.processed_images / st.total_images) * 100) : 0;
  $('progressBar').style.width = pct + '%';
  let txt = `${st.processed_images}/${st.total_images} processed · ${st.succeeded_images} ok`;
  if (st.failed_images) txt += ` · ${st.failed_images} failed`;
  $('statusCounts').textContent = txt;
}

/* ---------- markdown editor (Step 2) ---------- */
function mdToHtml(md) {
  if (!md || !md.trim()) return '<p class="muted">Nothing to preview yet.</p>';
  const inline = (t) => t
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
  const lines = esc(md).split(/\r?\n/);
  let html = '', inUl = false, inOl = false;
  const closeLists = () => {
    if (inUl) { html += '</ul>'; inUl = false; }
    if (inOl) { html += '</ol>'; inOl = false; }
  };
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { closeLists(); continue; }
    let m;
    if ((m = line.match(/^(#{1,4})\s+(.*)/))) {
      closeLists(); const lvl = Math.min(m[1].length + 2, 5);
      html += `<h${lvl}>${inline(m[2])}</h${lvl}>`;
    } else if ((m = line.match(/^[-*]\s+(.*)/))) {
      if (!inUl) { closeLists(); html += '<ul>'; inUl = true; }
      html += `<li>${inline(m[1])}</li>`;
    } else if ((m = line.match(/^\d+\.\s+(.*)/))) {
      if (!inOl) { closeLists(); html += '<ol>'; inOl = true; }
      html += `<li>${inline(m[1])}</li>`;
    } else {
      closeLists(); html += `<p>${inline(line)}</p>`;
    }
  }
  closeLists();
  return html;
}
function setScopeTab(which) {
  const edit = which === 'edit';
  $('tabEdit').classList.toggle('active', edit);
  $('tabPreview').classList.toggle('active', !edit);
  $('scope').classList.toggle('hidden', !edit);
  $('scopePreview').classList.toggle('hidden', edit);
  if (!edit) $('scopePreview').innerHTML = mdToHtml($('scope').value);
}

/* ---------- import PDF / image (Step 2) ---------- */
function initImport() {
  $('docFile').addEventListener('change', importDoc);
}
async function importDoc(ev) {
  const file = ev.target.files[0];
  if (!file) return;
  if (!key()) { ev.target.value = ''; return toast('Enter your API key first', 'error'); }
  const btn = $('importBtn');
  busy(btn, true, 'Extracting...');
  try {
    const fd = new FormData();
    fd.append('file', file);
    const r = await api('/api/v1/extract-text', { method: 'POST', body: fd });
    $('scope').value = r.text || '';
    setScopeTab('edit');
    toast('Text extracted — review & edit before running the audit', 'success');
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    busy(btn, false, '⤓ Import PDF / Image');
    ev.target.value = '';
  }
}

/* ---------- lightbox (full-size image) ---------- */
function openLightbox(src) {
  $('lightboxImg').src = src;
  $('lightbox').classList.remove('hidden');
}
function closeLightbox() {
  $('lightbox').classList.add('hidden');
  $('lightboxImg').src = '';
}
function initLightbox() {
  // delegate: any evidence thumbnail or chat reference image opens the lightbox
  document.addEventListener('click', (e) => {
    if (e.target.matches('.thumb, .refs img')) openLightbox(e.target.src);
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeLightbox(); });
}

/* ---------- 2. audit ---------- */
async function runAudit() {
  if (!key()) return toast('Enter your API key first', 'error');
  const scope = $('scope').value.trim();
  if (!scope) return toast('Paste the Scope of Works first', 'error');
  const btn = $('auditBtn');
  busy(btn, true, 'Analyzing...');
  $('report').innerHTML = '';
  try {
    const r = await api('/api/v1/projects/audit', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: pid(), scope_text: scope, language: lang() }),
    });
    renderReport(r.audit_report || {});
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    busy(btn, false, 'Run AI Audit');
  }
}

/* ---------- image helpers + carousel ---------- */
const URL_RE = /https?:\/\/[^\s)<>"']+/g;
function extractUrls(t) { return t ? (String(t).match(URL_RE) || []) : []; }
function stripUrls(t) {
  if (!t) return '';
  return String(t).replace(URL_RE, '')
    .replace(/\(\s*\)/g, '')          // empty parens left behind
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+([.,;:])/g, '$1')
    .trim();
}
function collectImageUrls(d) {
  const arr = Array.isArray(d.related_image_urls) ? d.related_image_urls.slice() : [];
  if (d.related_image_url) arr.push(d.related_image_url);     // legacy single field
  extractUrls(d.evidence_description).forEach((u) => arr.push(u));
  return [...new Set(arr.filter(Boolean))];
}
function mediaHtml(urls) {
  if (!urls.length) return '';
  if (urls.length === 1)
    return `<img class="thumb" src="${esc(urls[0])}" alt="evidence">`;
  const imgs = urls.map((u, i) =>
    `<img class="car-img thumb" src="${esc(u)}" alt="evidence ${i + 1}"${i ? ' hidden' : ''}>`).join('');
  return `<div class="carousel" data-i="0">
    <div class="car-stage">${imgs}</div>
    <button type="button" class="car-btn prev" aria-label="Previous">‹</button>
    <button type="button" class="car-btn next" aria-label="Next">›</button>
    <span class="car-count">1 / ${urls.length}</span>
  </div>`;
}
function initCarousel() {
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.car-btn');
    if (!btn) return;
    const car = btn.closest('.carousel');
    const imgs = car.querySelectorAll('.car-img');
    if (imgs.length < 2) return;
    let i = +car.dataset.i || 0;
    imgs[i].hidden = true;
    i = (i + (btn.classList.contains('next') ? 1 : -1) + imgs.length) % imgs.length;
    imgs[i].hidden = false;
    car.dataset.i = i;
    const c = car.querySelector('.car-count');
    if (c) c.textContent = `${i + 1} / ${imgs.length}`;
  });
}

function renderReport(rep) {
  const groups = [
    { key: 'discrepancies', title: 'Discrepancies (missing scope items)', cls: 'discrepancy',
      render: (d) => `<div class="title">${esc(d.issue_title)}</div>
        <p><span class="label">Evidence:</span> ${esc(stripUrls(d.evidence_description))}</p>
        <p class="action">→ ${esc(stripUrls(d.suggested_action))}</p>
        ${mediaHtml(collectImageUrls(d))}` },
    { key: 'ambiguity_alerts', title: 'Ambiguity Alerts', cls: 'ambiguity',
      render: (a) => `<blockquote>"${esc(a.original_text)}"</blockquote>
        <p><span class="label">Risk:</span> ${esc(a.risk_analysis)}</p>
        <p class="action">→ ${esc(a.recommended_phrasing)}</p>` },
    { key: 'safety_equipment_recommendations', title: 'Safety &amp; Equipment', cls: 'safety',
      render: (s) => `<div class="title">${esc(s.equipment_name)}</div>
        <p>${esc(s.reason)}</p>` },
  ];
  const html = groups.map((g) => {
    const items = rep[g.key] || [];
    const body = items.length
      ? items.map((it) => `<div class="finding ${g.cls}">${g.render(it)}</div>`).join('')
      : `<p class="empty-note">No items flagged.</p>`;
    return `<div class="result-group group-${g.cls}">
      <h3>${g.title} <span class="count-pill">${items.length}</span></h3>${body}</div>`;
  }).join('');
  $('report').innerHTML = html;
}

/* ---------- 3. chat ---------- */
async function sendChat() {
  if (!key()) return toast('Enter your API key first', 'error');
  const q = $('q').value.trim();
  if (!q) return;
  const btn = $('chatBtn');
  busy(btn, true, 'Asking...');
  try {
    const r = await api('/api/v1/projects/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: pid(), user_question: q, language: lang() }),
    });
    const refs = (r.reference_image_urls || [])
      .map((u) => `<img src="${esc(u)}" alt="ref">`).join('');
    $('chat').innerHTML = `<div class="bubble">${esc(r.answer_text)}</div>
      ${refs ? `<div class="refs">${refs}</div>` : ''}`;
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    busy(btn, false, 'Ask');
  }
}

/* ---------- init ---------- */
loadSettings();
initDropzone();
initImport();
initLightbox();
initCarousel();
