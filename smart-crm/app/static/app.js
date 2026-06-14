const API = '/api';
let currentBatchId = null;
let geoConfig = null;

const L3_DEFAULTS = [
  { code: 'cookware-commercial', name_zh: '商用锅具与烤盘' },
  { code: 'bakeware', name_zh: '烘焙模具与器皿' },
  { code: 'flatware', name_zh: '餐具与侍酒' },
  { code: 'food-storage', name_zh: '食品储存与周转' },
  { code: 'buffet', name_zh: '自助餐与宴会' },
  { code: 'kitchen-tools', name_zh: '厨房小工具' },
];

async function api(path, opts = {}) {
  const headers = { ...opts.headers };
  const token = localStorage.getItem('session_token');
  if (token) headers['X-Session-Token'] = token;
  if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(opts.body);
  }
  const res = await fetch(`${API}${path}`, { ...opts, headers });
  if (!res.ok) throw new Error(await res.text());
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('json')) return res.json();
  return res.text();
}

function log(msg) {
  const el = document.getElementById('sse-log');
  const line = document.createElement('div');
  line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
}

function fillL3Selects() {
  ['search-l3', 'bs-l3', 'ct-l3'].forEach((id) => {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = L3_DEFAULTS.map(
      (c) => `<option value="${c.code}">${c.name_zh}</option>`
    ).join('');
  });
}

// Tabs
document.querySelectorAll('.tab-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach((p) => p.classList.add('hidden'));
    btn.classList.add('active');
    document.getElementById(`tab-${btn.dataset.tab}`).classList.remove('hidden');
    if (btn.dataset.tab === 'market') loadMarket();
    if (btn.dataset.tab === 'import') loadImport();
    if (btn.dataset.tab === 'history') loadBatches();
    if (btn.dataset.tab === 'brainstorm') loadBrainstormSessions();
    if (btn.dataset.tab === 'content') loadContentHistory();
    if (btn.dataset.tab === 'config') { loadConfig(); loadIntegrationStatus(); }
  });
});

let currentDraftId = null;
let currentBatchDrafts = [];
let currentBatchId = null;

function getContentForm() {
  return {
    content_type: document.getElementById('ct-type').value,
    product_name: document.getElementById('ct-product').value.trim(),
    category_l3: document.getElementById('ct-l3').value,
    country_iso: document.getElementById('ct-country').value,
    input_notes: document.getElementById('ct-notes').value,
  };
}

function getBatchLanguages() {
  return [...document.querySelectorAll('.ct-batch-lang:checked')].map(el => el.value);
}

// Tab8 Content Studio
document.getElementById('btn-content-gen').onclick = async () => {
  const form = getContentForm();
  if (!form.product_name) return alert('请填写产品/主题名称');
  document.getElementById('ct-result').innerHTML = '<p class="text-amber-400">AI 生成中…</p>';
  hideBatchTabs();
  const res = await api('/content/generate', {
    method: 'POST',
    body: { ...form, language: document.getElementById('ct-lang').value },
  });
  currentBatchDrafts = [];
  renderContentDraft(res);
  loadContentHistory();
};

document.getElementById('btn-content-batch').onclick = async () => {
  const form = getContentForm();
  if (!form.product_name) return alert('请填写产品/主题名称');
  const languages = getBatchLanguages();
  if (!languages.length) return alert('请至少勾选一种语言');
  document.getElementById('ct-result').innerHTML = `<p class="text-amber-400">批量生成中（${languages.join(', ')}）…</p>`;
  const res = await api('/content/generate-batch', {
    method: 'POST',
    body: { ...form, languages },
  });
  currentBatchDrafts = res.drafts || [];
  renderBatchDrafts(currentBatchDrafts);
  loadContentHistory();
};

function hideBatchTabs() {
  const tabs = document.getElementById('ct-lang-tabs');
  tabs.classList.add('hidden');
  tabs.innerHTML = '';
}

function renderBatchTabs(drafts, activeId) {
  const tabs = document.getElementById('ct-lang-tabs');
  if (!drafts || drafts.length < 2) {
    hideBatchTabs();
    return;
  }
  tabs.classList.remove('hidden');
  tabs.innerHTML = drafts.map(d => `
    <button type="button"
      class="px-2 py-1 rounded ${d.id === activeId ? 'bg-emerald-600 text-white' : 'bg-slate-700 text-slate-300'}"
      onclick="switchBatchDraft('${d.id}')">${d.language_label || d.language}</button>
  `).join('');
}

function renderBatchDrafts(drafts) {
  if (!drafts.length) return;
  currentBatchId = drafts[0].batch_id || null;
  renderBatchTabs(drafts, drafts[0].id);
  renderContentDraft(drafts[0]);
}

window.switchBatchDraft = (id) => {
  const draft = currentBatchDrafts.find(d => d.id === id);
  if (!draft) return;
  renderBatchTabs(currentBatchDrafts, id);
  renderContentDraft(draft);
};

function renderContentDraft(d) {
  currentDraftId = d.id;
  currentBatchId = d.batch_id || null;
  document.getElementById('btn-content-save').classList.remove('hidden');
  document.getElementById('btn-content-export').classList.remove('hidden');
  const batchBtn = document.getElementById('btn-content-export-batch');
  if (currentBatchId) batchBtn.classList.remove('hidden');
  else batchBtn.classList.add('hidden');
  const kw = (d.meta_keywords || []).join(', ');
  document.getElementById('ct-result').innerHTML = `
    <div class="grid gap-2">
      <label class="text-slate-400">Title <input id="ed-title" class="input mt-1" value="${esc(d.title)}" /></label>
      <label class="text-slate-400">Slug <input id="ed-slug" class="input mt-1" value="${esc(d.slug)}" /></label>
      <label class="text-slate-400">Meta Title (≤60) <input id="ed-meta-title" class="input mt-1" value="${esc(d.meta_title)}" /></label>
      <label class="text-slate-400">Meta Description (≤155) <textarea id="ed-meta-desc" class="input mt-1 h-16">${esc(d.meta_description)}</textarea></label>
      <label class="text-slate-400">Keywords <input id="ed-keywords" class="input mt-1" value="${esc(kw)}" /></label>
      <label class="text-slate-400">H1 <input id="ed-h1" class="input mt-1" value="${esc(d.h1)}" /></label>
      <label class="text-slate-400">正文 Markdown <textarea id="ed-body" class="input mt-1 h-48 font-mono text-xs">${esc(d.body_markdown || (d.extra?.product_description_short || ''))}</textarea></label>
      ${(d.bullet_features || []).length ? `<div><span class="text-slate-400">要点</span><ul class="list-disc ml-5 mt-1">${d.bullet_features.map(b=>`<li>${esc(b)}</li>`).join('')}</ul></div>` : ''}
      ${d.extra?.seo_notes ? `<p class="text-xs text-slate-500">SEO 提示: ${esc(d.extra.seo_notes)}</p>` : ''}
    </div>`;
}

function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
}

document.getElementById('btn-content-save').onclick = async () => {
  if (!currentDraftId) return;
  await api(`/content/drafts/${currentDraftId}`, {
    method: 'PUT',
    body: {
      title: document.getElementById('ed-title').value,
      slug: document.getElementById('ed-slug').value,
      meta_title: document.getElementById('ed-meta-title').value,
      meta_description: document.getElementById('ed-meta-desc').value,
      meta_keywords: document.getElementById('ed-keywords').value.split(',').map(s=>s.trim()).filter(Boolean),
      h1: document.getElementById('ed-h1').value,
      body_markdown: document.getElementById('ed-body').value,
      status: 'approved',
    },
  });
  alert('已保存');
};

document.getElementById('btn-content-export').onclick = () => {
  if (!currentDraftId) return;
  window.open(`${API}/content/drafts/${currentDraftId}/export.md`);
};

document.getElementById('btn-content-export-batch').onclick = () => {
  if (!currentBatchId) return;
  window.open(`${API}/content/batches/${currentBatchId}/export.zip`);
};

async function loadContentHistory() {
  const drafts = await api('/content/drafts');
  document.getElementById('ct-history').innerHTML = drafts
    .map(d => {
      const lang = d.language_label || d.language || '';
      const batch = d.batch_id ? ' [批量]' : '';
      return `<div class="cursor-pointer hover:text-emerald-400 truncate" onclick="loadDraft('${d.id}')">${d.content_type_label}: ${d.product_name?.slice(0,24)} (${lang})${batch}</div>`;
    })
    .join('') || '<span class="text-slate-500">暂无历史</span>';
}

window.loadDraft = async (id) => {
  const d = await api(`/content/drafts/${id}`);
  if (d.batch_id) {
    const batch = await api(`/content/batches/${d.batch_id}`);
    currentBatchDrafts = batch.drafts || [];
    renderBatchTabs(currentBatchDrafts, d.id);
  } else {
    currentBatchDrafts = [];
    hideBatchTabs();
  }
  renderContentDraft(d);
};

// Config form
const CONFIG_FIELDS = [
  ['exa_api_key', 'Exa API Key'],
  ['firecrawl_api_key', 'Firecrawl API Key'],
  ['openai_api_key', 'OpenAI API Key'],
  ['openai_model', 'OpenAI Model'],
  ['feishu_app_id', '飞书 App ID'],
  ['feishu_app_secret', '飞书 App Secret'],
  ['feishu_base_token', '飞书 Base Token'],
  ['feishu_table_id', '飞书 Table ID'],
  ['ingest_mode', '入库模式 (auto/review)'],
  ['max_concurrency', '最大并发数'],
  ['tbcexp_api_url', 'TBCEXP API URL'],
  ['tbcexp_api_token', 'TBCEXP API Token'],
  ['resend_api_key', 'Resend API Key'],
  ['resend_from_email', 'Resend From Email'],
  ['apollo_api_key', 'Apollo API Key (可选)'],
  ['importgenius_api_key', 'ImportGenius API Key (可选)'],
  ['scheduler_enabled', '定时任务 (true/false)'],
];

async function loadIntegrationStatus() {
  const el = document.getElementById('config-integ-status');
  if (!el) return;
  try {
    const st = await api('/integrations/status');
    const rows = (st.services || [])
      .map(s => `${s.label}: ${s.configured ? '✓ live' : '○ mock'}`)
      .join(' · ');
    el.innerHTML = `<span class="${st.production_ready ? 'text-emerald-400' : 'text-amber-400'}">
      已配置 ${st.configured_count}/${st.total}
      ${st.production_ready ? ' — 可跑真实试点' : ' — 请补齐 Exa/Firecrawl/OpenAI/飞书'}
    </span><br/><span class="text-xs">${rows}</span>`;
  } catch {
    el.textContent = '集成状态加载失败';
  }
}

document.getElementById('btn-probe-apis')?.addEventListener('click', async () => {
  const out = document.getElementById('config-probe-result');
  out.classList.remove('hidden');
  out.textContent = '探测中…';
  try {
    const res = await api('/integrations/probe', { method: 'POST' });
    out.textContent = JSON.stringify(res, null, 2);
    loadIntegrationStatus();
  } catch (e) {
    out.textContent = String(e);
  }
});

async function loadConfig() {
  const cfg = await api('/config');
  const form = document.getElementById('config-form');
  form.innerHTML = CONFIG_FIELDS.map(
    ([key, label]) =>
      `<label class="block text-sm"><span class="text-slate-400">${label}</span>
       <input name="${key}" class="input mt-1" value="${cfg[key] ?? ''}" /></label>`
  ).join('');
}

document.getElementById('btn-save-config').onclick = async () => {
  const form = document.getElementById('config-form');
  const data = {};
  CONFIG_FIELDS.forEach(([key]) => {
    const input = form.querySelector(`[name="${key}"]`);
    if (input) data[key] = input.value;
  });
  data.max_concurrency = parseInt(data.max_concurrency) || 5;
  data.extended_feishu_fields = true;
  await api('/config', { method: 'POST', body: data });
  alert('配置已保存');
  loadIntegrationStatus();
};

// Run batch
document.getElementById('btn-run').onclick = async () => {
  const l3 = document.getElementById('search-l3').value;
  const country = document.getElementById('search-country').value;
  const city = document.getElementById('search-city').value;
  let keyword = document.getElementById('search-keyword').value.trim();
  if (!keyword && geoConfig) {
    const templates = geoConfig.categories?.l3 || [];
    const cat = templates.find((c) => c.code === l3);
    keyword = `mayorista ${cat?.name_en || l3} ${city} ${country}`;
  }
  const body = {
    keyword,
    industry: document.getElementById('search-industry').value,
    count: parseInt(document.getElementById('search-count').value) || 5,
    country_iso: country,
    city,
    category_l3: l3,
    language: 'es',
    search_type: document.getElementById('search-type').value,
  };
  log(`启动批次: ${keyword}`);
  const { batch_id } = await api('/run', { method: 'POST', body });
  currentBatchId = batch_id;
  const es = new EventSource(`${API}/stream/${batch_id}`);
  es.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.event === 'lead') {
      log(`✓ ${data.lead.company_name}`);
      renderLeadCard(data.lead);
    } else if (data.event === 'skip') {
      log(`跳过重复: ${data.domain}`);
    } else if (data.event === 'complete') {
      log(`完成: 成功 ${data.success}`);
      es.close();
    } else if (data.event === 'error') {
      log(`错误: ${data.message}`);
      es.close();
    } else {
      log(JSON.stringify(data));
    }
  };
};

function renderLeadCard(lead) {
  const grid = document.getElementById('results-grid');
  const div = document.createElement('div');
  div.className = 'lead-card';
  div.innerHTML = `
    <div class="flex justify-between items-start mb-2">
      <a href="${lead.website_url}" target="_blank" class="font-semibold text-emerald-400">${lead.company_name}</a>
      <span class="channel-badge">${lead.preferred_channel || 'email'}</span>
    </div>
    <p class="text-xs text-slate-400 mb-2">${lead.country_iso} · ${lead.city} · ${lead.category_l3}</p>
    <p class="text-sm line-clamp-3 mb-2">${(lead.firecrawl_summary || '').slice(0, 200)}...</p>
    <details class="text-sm">
      <summary class="cursor-pointer text-emerald-400">开发信</summary>
      <pre class="whitespace-pre-wrap mt-2 text-xs">${lead.outreach_email}</pre>
    </details>
    ${lead.whatsapp_intro ? `<details class="text-sm mt-2"><summary class="cursor-pointer text-amber-400">WhatsApp 话术</summary><pre class="whitespace-pre-wrap mt-2 text-xs">${lead.whatsapp_intro}</pre></details>` : ''}
    <div class="flex gap-2 mt-3">
      <button class="btn-secondary text-xs" onclick="confirmLead('${lead.id}')">确认入库</button>
      <button class="btn-secondary text-xs" onclick="regenLead('${lead.id}')">重新生成</button>
    </div>`;
  grid.prepend(div);
}

window.confirmLead = async (id) => {
  await api(`/confirm/${id}`, { method: 'POST' });
  alert('已确认入库');
};
window.regenLead = async (id) => {
  await api(`/regenerate/${id}`, { method: 'POST' });
  alert('已重新生成');
};

document.getElementById('btn-export-csv').onclick = () => {
  if (!currentBatchId) return alert('无当前批次');
  window.open(`${API}/batch/${currentBatchId}/export.csv`);
};

async function loadBatches() {
  const batches = await api('/batches');
  document.getElementById('batch-list').innerHTML = batches
    .map(
      (b) =>
        `<div class="p-3 bg-slate-800 rounded flex justify-between">
          <span>${b.keyword?.slice(0, 40)}</span>
          <span class="text-emerald-400">${b.success}/${b.total}</span>
          <button class="text-xs text-slate-400" onclick="loadBatch('${b.id}')">查看</button>
        </div>`
    )
    .join('');
  const schedules = await api('/schedules');
  document.getElementById('schedule-list').innerHTML = schedules
    .map((s) => `<div class="p-2 bg-slate-800 rounded text-xs">${s.keyword?.slice(0, 50)} — 每 ${s.interval_hours}h</div>`)
    .join('');
}

window.loadBatch = async (id) => {
  currentBatchId = id;
  const data = await api(`/batch/${id}`);
  document.getElementById('results-grid').innerHTML = '';
  (data.leads || []).forEach(renderLeadCard);
  document.querySelector('[data-tab="results"]').click();
};

document.getElementById('btn-add-schedule').onclick = async () => {
  await api('/schedules', {
    method: 'POST',
    body: {
      keyword: document.getElementById('sched-keyword').value,
      industry: '跨境电商',
      interval_hours: parseInt(document.getElementById('sched-interval').value) || 24,
    },
  });
  loadBatches();
};

document.getElementById('btn-run-due-schedules')?.addEventListener('click', async () => {
  log('执行到期定时任务…');
  const res = await api('/schedules/run-due?limit=3&count_per_task=5', { method: 'POST' });
  log(`到期任务已入队: ${res.queued} 个`);
  if (res.jobs?.length) {
    res.jobs.forEach(j => log(`  ${j.city}/${j.category_l3}: batch ${j.batch_id}`));
  }
  loadBatches();
  document.querySelector('[data-tab="results"]')?.click();
});

// Market Intel Tab5
async function loadMxPilotStatus() {
  const el = document.getElementById('mx-pilot-status');
  if (!el) return;
  try {
    const [mx, co] = await Promise.all([
      api('/pilot/mx/status'),
      api('/pilot/co/status'),
    ]);
    const fmt = (st, label) => {
      const acc = st.latest_run?.acceptance || {};
      const t = st.totals || {};
      return `${label}: 情报${t.intel_reports || 0} / 策略${t.brainstorm_sessions || 0} / 任务${t.active_schedules || 0}
        ${st.latest_run ? ` | B:${acc.track_b_intel ? '✓' : '○'} Brainstorm:${acc.brainstorm_cards ? '✓' : '○'} 入队:${acc.track_a_queued ? '✓' : '○'}` : ' | 未运行'}`;
    };
    el.innerHTML = `<pre class="text-xs whitespace-pre-wrap">${fmt(mx, 'MX')}\n${fmt(co, 'CO')}</pre>`;
  } catch (e) {
    el.textContent = '试点状态加载失败';
  }
}

async function startPilot(countryIso, btnId) {
  const btn = document.getElementById(btnId);
  const out = document.getElementById('mx-pilot-result');
  btn.disabled = true;
  const oldText = btn.textContent;
  btn.textContent = '运行中…';
  out.classList.remove('hidden');
  out.textContent = `${countryIso} 试点：Track B → Brainstorm → Track A 入队…`;
  try {
    const res = await api(`/pilot/${countryIso}/start`, {
      method: 'POST',
      body: {
        country_iso: countryIso,
        category_l3: 'bakeware',
        anchor_limit: 2,
        enqueue_track_a: true,
      },
    });
    out.textContent = JSON.stringify(res, null, 2);
    log(`${countryIso} 试点完成 session=${res.session_id}`);
    loadMxPilotStatus();
    loadMarket();
    loadBatches();
  } catch (e) {
    out.textContent = String(e);
  } finally {
    btn.disabled = false;
    btn.textContent = oldText;
  }
}

document.getElementById('btn-mx-pilot')?.addEventListener('click', () => startPilot('MX', 'btn-mx-pilot'));
document.getElementById('btn-co-pilot')?.addEventListener('click', () => startPilot('CO', 'btn-co-pilot'));

async function loadMarket() {
  loadMxPilotStatus();
  const country = document.getElementById('market-country').value;
  const q = country ? `?country_iso=${country}` : '';
  const anchors = await api(`/market/anchors${q}`);
  document.getElementById('anchor-list').innerHTML = anchors
    .map(
      (a) =>
        `<div class="p-3 bg-slate-800 rounded">
          <div class="font-medium">${a.company_name}</div>
          <div class="text-xs text-slate-400">${a.website}</div>
          <button class="btn-secondary text-xs mt-2" onclick="crawlAnchor('${a.id}')">采集产品情报</button>
        </div>`
    )
    .join('');
  const intel = await api(`/market/intel${q}`);
  document.getElementById('intel-list').innerHTML = intel
    .map(
      (i) =>
        `<div class="p-3 bg-slate-800 rounded">
          <div class="flex justify-between"><span class="font-medium">${i.category_l3}</span>
          <span class="heat-${i.sales_signal}">${i.sales_signal}</span></div>
          <p class="text-sm mt-1">${i.trend_summary}</p>
        </div>`
    )
    .join('');
}

window.crawlAnchor = async (id) => {
  log(`Track B 采集锚点 ${id}...`);
  const res = await api(`/market/anchors/${id}/crawl`, { method: 'POST' });
  log(`情报完成: ${res.category_l3} — ${res.sales_signal}`);
  loadMarket();
};

document.getElementById('market-country')?.addEventListener('change', loadMarket);

// Brainstorm Tab6
document.getElementById('btn-brainstorm').onclick = async () => {
  const res = await api('/brainstorm/generate', {
    method: 'POST',
    body: {
      country_iso: document.getElementById('bs-country').value,
      city: document.getElementById('bs-city').value,
      category_l3: document.getElementById('bs-l3').value,
      language: 'es',
      moq: document.getElementById('bs-moq').value,
    },
  });
  renderBrainstormCards(res.session_id, res.cards);
  loadBrainstormSessions();
};

function renderBrainstormCards(sessionId, cards) {
  const container = document.getElementById('bs-cards');
  container.innerHTML = cards
    .map(
      (c) =>
        `<div class="bs-card">
          <h3 class="font-semibold text-amber-400 mb-2">卡片 ${c.id}: ${c.title}</h3>
          <pre class="text-sm whitespace-pre-wrap overflow-auto max-h-48">${JSON.stringify(c.content, null, 2)}</pre>
        </div>`
    )
    .join('');
  container.innerHTML += `
    <div class="card flex flex-wrap gap-2">
      <button class="btn-primary" onclick="bsAction('${sessionId}','track_a_job')">生成 Track A 任务</button>
      <button class="btn-secondary" onclick="bsAction('${sessionId}','anchor')">添加 Track B 锚点</button>
      <button class="btn-secondary" onclick="bsAction('${sessionId}','similar_search')">相似公司搜索入队</button>
    </div>`;
}

window.bsAction = async (sessionId, type) => {
  await api('/brainstorm/actions', {
    method: 'POST',
    body: { session_id: sessionId, action_type: type, payload: {} },
  });
  alert(`已执行: ${type}`);
};

async function loadBrainstormSessions() {
  const sessions = await api('/brainstorm/sessions');
  document.getElementById('bs-sessions').innerHTML = sessions
    .map(
      (s) =>
        `<div class="cursor-pointer hover:text-emerald-400" onclick="loadBsSession('${s.id}')">
          ${s.country_iso} · ${s.city} · ${s.category_l3}
        </div>`
    )
    .join('');
}

window.loadBsSession = async (id) => {
  const res = await api(`/brainstorm/sessions/${id}`);
  renderBrainstormCards(res.session_id, res.cards);
};

// Import Tab7
async function loadImport() {
  const shows = await api('/tradeshows');
  document.getElementById('tradeshow-list').innerHTML = shows
    .map(
      (t) =>
        `<div class="p-3 bg-slate-800 rounded flex justify-between items-center">
          <span>${t.name} (${t.country_iso})</span>
          <button class="btn-secondary text-xs" onclick="crawlShow('${t.id}')">抓取参展商</button>
        </div>`
    )
    .join('');
  const leads = await api('/import/leads');
  document.getElementById('import-lead-list').innerHTML = leads
    .map(
      (l) =>
        `<div class="p-2 bg-slate-800 rounded flex justify-between">
          <span>${l.company_name} · HS ${l.hs_code}</span>
          <button class="text-xs text-emerald-400" onclick="promoteImport('${l.id}')">${l.status}</button>
        </div>`
    )
    .join('');
}

window.crawlShow = async (id) => {
  const res = await api(`/tradeshows/${id}/crawl`, { method: 'POST' });
  alert(`找到 ${res.exhibitors_found} 家参展商`);
  loadImport();
};

window.promoteImport = async (id) => {
  await api(`/import/leads/${id}/promote`, { method: 'POST' });
  loadImport();
};

document.getElementById('btn-import-csv').onclick = async () => {
  const file = document.getElementById('import-file').files[0];
  if (!file) return alert('请选择 CSV');
  const fd = new FormData();
  fd.append('file', file);
  const hs = document.getElementById('import-hs').value;
  const country = document.getElementById('import-country').value;
  const url = `${API}/import/csv?country_iso=${country}&hs_codes=${hs}`;
  const r = await fetch(url, { method: 'POST', body: fd });
  const res = await r.json();
  alert(`导入 ${res.imported} 条，重复 ${res.duplicates}`);
  loadImport();
};

document.getElementById('btn-match-domains').onclick = async () => {
  const res = await api('/import/match-domains', { method: 'POST' });
  alert(`匹配 ${res.matched} 个域名`);
  loadImport();
};

// Init
async function init() {
  fillL3Selects();
  try {
    const health = await api('/health');
    document.getElementById('health-badge').textContent = `在线 ${health.time?.slice(11, 19) || ''}`;
    document.getElementById('health-badge').className = 'px-2 py-1 rounded bg-emerald-900 text-emerald-300';
  } catch {
    document.getElementById('health-badge').textContent = '离线';
  }
  await loadConfig();
  loadIntegrationStatus();
  geoConfig = await api('/geo/config');
  await api('/geo/seed', { method: 'POST' });
}

init();
