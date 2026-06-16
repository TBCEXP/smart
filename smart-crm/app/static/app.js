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
  if (res.status === 401) {
    localStorage.removeItem('session_token');
    document.cookie = 'session_token=; path=/; max-age=0';
    location.href = `/admin?next=${encodeURIComponent(location.pathname)}`;
    throw new Error('请先登录');
  }
  if (!res.ok) throw new Error(await res.text());
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('json')) return res.json();
  return res.text();
}

function logout() {
  localStorage.removeItem('session_token');
  document.cookie = 'session_token=; path=/; max-age=0';
  location.href = '/admin';
}

async function updateAuthHeader() {
  const loginLink = document.getElementById('login-link');
  const logoutBtn = document.getElementById('logout-btn');
  const userBadge = document.getElementById('user-badge');
  const token = localStorage.getItem('session_token');
  if (!token) {
    loginLink?.classList.remove('hidden');
    logoutBtn?.classList.add('hidden');
    userBadge?.classList.add('hidden');
    return;
  }
  try {
    const session = await api('/auth/session');
    loginLink?.classList.add('hidden');
    logoutBtn?.classList.remove('hidden');
    if (userBadge) {
      userBadge.textContent = session.email;
      userBadge.classList.remove('hidden');
    }
  } catch {
    loginLink?.classList.remove('hidden');
    logoutBtn?.classList.add('hidden');
    userBadge?.classList.add('hidden');
  }
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
    if (btn.dataset.tab === 'dashboard') loadDashboard();
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
  ['r2_account_id', 'R2 Account ID'],
  ['r2_access_key_id', 'R2 Access Key ID'],
  ['r2_secret_access_key', 'R2 Secret Access Key'],
  ['r2_bucket', 'R2 Bucket (默认 smart-crm)'],
  ['r2_public_base_url', 'R2 公开 CDN 前缀 (可选)'],
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
    updateOnboardBanner(st.production_ready);
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
    updateOnboardBanner(res.production_ready);
  } catch (e) {
    out.textContent = String(e);
  }
});

document.getElementById('btn-feishu-test')?.addEventListener('click', async () => {
  const token = localStorage.getItem('session_token');
  if (!token) {
    alert('请先登录 /admin（飞书写入测试需鉴权）');
    window.location.href = '/admin';
    return;
  }
  const out = document.getElementById('config-probe-result');
  out.classList.remove('hidden');
  out.textContent = '飞书写入测试中…';
  try {
    const res = await api('/integrations/feishu/test-write', { method: 'POST' });
    out.textContent = JSON.stringify(res, null, 2);
  } catch (e) {
    out.textContent = String(e);
  }
});

document.getElementById('btn-goto-config')?.addEventListener('click', () => {
  document.querySelector('[data-tab="config"]')?.click();
});
document.getElementById('btn-goto-dashboard')?.addEventListener('click', () => {
  document.querySelector('[data-tab="dashboard"]')?.click();
});

function updateOnboardBanner(productionReady) {
  const banner = document.getElementById('onboard-banner');
  if (!banner) return;
  banner.classList.toggle('hidden', !!productionReady);
}

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
async function previewExaQuery() {
  const l3 = document.getElementById('search-l3').value;
  const country = document.getElementById('search-country').value;
  const city = document.getElementById('search-city').value;
  const keyword = document.getElementById('search-keyword').value.trim();
  const searchType = document.getElementById('search-type').value;
  const params = new URLSearchParams({
    keyword,
    category_l3: l3,
    country_iso: country,
    city,
    language: 'es',
    search_type: searchType,
  });
  const data = await api(`/exa/preview-query?${params}`);
  const el = document.getElementById('exa-query-preview');
  el.classList.remove('hidden');
  el.innerHTML =
    `<span class="text-emerald-400">resolved:</span> ${data.resolved_query}<br>` +
    `<span class="text-amber-400">semantic:</span> ${data.semantic_query}`;
}

document.getElementById('btn-preview-query')?.addEventListener('click', previewExaQuery);

document.getElementById('btn-run').onclick = async () => {
  const l3 = document.getElementById('search-l3').value;
  const country = document.getElementById('search-country').value;
  const city = document.getElementById('search-city').value;
  let keyword = document.getElementById('search-keyword').value.trim();
  if (!keyword && !l3 && geoConfig) {
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
  const streamToken = localStorage.getItem('session_token') || '';
  const streamUrl = streamToken
    ? `${API}/stream/${batch_id}?token=${encodeURIComponent(streamToken)}`
    : `${API}/stream/${batch_id}`;
  const es = new EventSource(streamUrl);
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
    <div class="flex gap-2 mt-3 flex-wrap">
      <button class="btn-secondary text-xs" onclick="confirmLead('${lead.id}')">确认入库</button>
      <button class="btn-secondary text-xs" onclick="enrichContact('${lead.id}')">Apollo 补邮箱</button>
      <button class="btn-secondary text-xs" onclick="regenLead('${lead.id}')">重新生成</button>
      ${lead.whatsapp_intro ? `<button class="btn-secondary text-xs text-amber-400" onclick="logWhatsApp('${lead.id}')">记录 WhatsApp</button>` : ''}
    </div>`;
  grid.prepend(div);
}

window.confirmLead = async (id) => {
  await api(`/confirm/${id}`, { method: 'POST' });
  alert('已确认入库');
};

window.enrichContact = async (id) => {
  const res = await api(`/leads/${id}/enrich-contact`, { method: 'POST' });
  alert(`Apollo ${res.mode}: ${res.contact_email || res.detail}`);
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

// Tab9 Pilot Dashboard
async function loadDashboard() {
  const cardsEl = document.getElementById('dash-cards');
  try {
    const [overview, logs, report] = await Promise.all([
      api('/stats/overview'),
      api('/outreach/logs'),
      api('/pilot/report'),
    ]);
    const m = overview.milestones || {};
    const milestoneItems = [
      ['1_5_4_feishu_30', '1.5.4 飞书≥30'],
      ['1_5_5_whatsapp_5', '1.5.5 WhatsApp≥5'],
      ['1_5_6_track_c', '1.5.6 Track C'],
      ['1_5_7_kb_recall', '1.5.7 KB召回'],
    ];
    document.getElementById('dash-milestone-bar').innerHTML = milestoneItems
      .map(([key, label]) => {
        const done = m[key];
        return `<span class="px-3 py-1 rounded text-xs ${
          done ? 'bg-emerald-900 text-emerald-300' : 'bg-slate-800 text-slate-400'
        }">${done ? '✓' : '○'} ${label}</span>`;
      })
      .join('');

    const cards = [
      {
        title: '线索总数',
        value: overview.leads?.total ?? 0,
        sub: `飞书同步 ${overview.leads?.feishu_synced ?? 0}`,
      },
      {
        title: 'WhatsApp 发送',
        value: overview.outreach?.whatsapp_sent ?? 0,
        sub: overview.outreach?.target_1_5_5 ?? '',
      },
      {
        title: '回复率',
        value: `${Math.round((overview.outreach?.reply_rate ?? 0) * 100)}%`,
        sub: `已回复 ${overview.outreach?.whatsapp_replied ?? 0} 家`,
      },
      {
        title: '海关导入',
        value: overview.track_c?.imported ?? 0,
        sub: `域名匹配 ${Math.round((overview.track_c?.match_rate ?? 0) * 100)}%`,
      },
      {
        title: 'MX 试点',
        value: overview.pilot?.MX ? '已验收' : '待完成',
        sub: report.milestones?.mx_queued ? 'Track A 已入队' : '未入队',
      },
      {
        title: 'CO 试点',
        value: report.milestones?.co_started ? '已启动' : '未启动',
        sub: overview.pilot?.CO ? '已验收' : '待完成',
      },
    ];
    cardsEl.innerHTML = cards
      .map(
        (c) =>
          `<div class="card">
            <p class="text-xs text-slate-400">${c.title}</p>
            <p class="text-2xl font-bold text-emerald-400 mt-1">${c.value}</p>
            ${c.sub ? `<p class="text-xs text-slate-500 mt-1">${c.sub}</p>` : ''}
          </div>`
      )
      .join('');

    const waSent = overview.outreach?.whatsapp_sent ?? 0;
    const milestone =
      waSent >= 5 ? '✓ 1.5.5 达标 (≥5)' : `○ 还需 ${5 - waSent} 条 WhatsApp`;
    document.getElementById('outreach-stats').innerHTML =
      `已发送 ${waSent} · 已回复 ${overview.outreach?.whatsapp_replied ?? 0} · ${milestone}`;

    document.getElementById('outreach-list').innerHTML = (logs || []).length
      ? logs
          .map(
            (o) =>
              `<div class="p-2 bg-slate-800 rounded flex justify-between items-center gap-2">
                <span class="truncate">${o.company_name} · ${o.country_iso || '—'}</span>
                <span class="shrink-0">
                  ${
                    o.replied
                      ? '<span class="text-emerald-400">已回复</span>'
                      : `<button class="text-xs text-amber-400" onclick="markReplied('${o.id}')">标记回复</button>`
                  }
                </span>
              </div>`
          )
          .join('')
      : '<p class="text-slate-500">暂无触达记录 — 在 Tab3 线索卡片点击「记录 WhatsApp」</p>';

    document.getElementById('dash-milestones').textContent = JSON.stringify(
      { milestones: { ...report.milestones, ...overview.milestones }, countries: report.countries },
      null,
      2
    );
    if (overview.milestones?.kb_results > 0) {
      searchKb(document.getElementById('kb-search-q')?.value || 'bakeware MX');
    }
  } catch (e) {
    cardsEl.innerHTML = `<p class="text-red-400 col-span-3">看板加载失败: ${e}</p>`;
  }
}

async function searchKb(query) {
  const el = document.getElementById('kb-search-results');
  if (!query?.trim()) return;
  el.innerHTML = '<p class="text-amber-400">检索中…</p>';
  try {
    const res = await api(`/kb/search?q=${encodeURIComponent(query.trim())}&limit=8`);
    renderKbResults(query, res.results || []);
  } catch (e) {
    el.innerHTML = `<p class="text-red-400">检索失败: ${e}</p>`;
  }
}

function renderKbResults(query, results) {
  const el = document.getElementById('kb-search-results');
  if (!results || !results.length) {
    el.innerHTML = query
      ? `<p class="text-slate-500">「${query}」无结果 — Mock 模式可试 bakeware MX</p>`
      : '输入查询后点击搜索';
    return;
  }
  el.innerHTML = results
    .map(
      (r) =>
        `<div class="p-2 bg-slate-800 rounded">
          <div class="font-medium text-emerald-400">${r.company_name}</div>
          <div class="text-slate-500">${r.country_iso} · ${r.city || '—'} · ${r.category_l3}</div>
          ${r.score != null ? `<div class="text-amber-400">score ${r.score}${r.search_mode ? ` · ${r.search_mode}` : ''}</div>` : ''}
        </div>`
    )
    .join('');
}

document.getElementById('btn-kb-search')?.addEventListener('click', () => {
  searchKb(document.getElementById('kb-search-q').value);
});
document.getElementById('kb-search-q')?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') searchKb(e.target.value);
});

document.getElementById('btn-export-report')?.addEventListener('click', () => {
  window.open(`${API}/pilot/export?format=md`);
});
document.getElementById('btn-refresh-dashboard')?.addEventListener('click', loadDashboard);

window.logWhatsApp = async (leadId) => {
  const preview = prompt('WhatsApp 消息摘要（可选，留空使用系统话术）') || '';
  try {
    await api('/outreach/log', {
      method: 'POST',
      body: {
        lead_id: leadId,
        channel: 'whatsapp',
        message_preview: preview,
      },
    });
    alert('已记录 WhatsApp 发送');
    loadDashboard();
  } catch (e) {
    alert(`记录失败: ${e}`);
  }
};

window.markReplied = async (logId) => {
  const notes = prompt('回复备注（可选）') || '';
  try {
    await api(`/outreach/logs/${logId}`, {
      method: 'PATCH',
      body: { replied: true, reply_notes: notes },
    });
    loadDashboard();
  } catch (e) {
    alert(`更新失败: ${e}`);
  }
};

async function loadReadinessBadge() {
  const el = document.getElementById('readiness-badge');
  if (!el) return;
  try {
    const r = await api('/system/readiness');
    const live = r.integrations?.production_ready;
    const mx = r.mx_pilot || {};
    const due = r.due_schedules || 0;
    el.classList.remove('hidden');
    if (live) {
      el.className = 'px-2 py-1 rounded bg-emerald-900 text-emerald-300 text-xs';
      el.textContent = `生产就绪 · 任务${due}`;
    } else {
      el.className = 'px-2 py-1 rounded bg-amber-900 text-amber-300 text-xs';
      el.textContent = `Mock 模式 · 任务${due}`;
    }
    el.title = `MX 情报${mx.intel_reports || 0} · 定时${mx.active_schedules || 0}`;
    const ms = r.milestones || {};
    const done = ['1_5_5_whatsapp_5', '1_5_7_kb_recall'].filter((k) => ms[k]).length;
    if (r.milestones) el.title += ` · 里程碑 ${done}/2+`;
  } catch {
    el.classList.add('hidden');
  }
}

// Init
async function requireAuth() {
  const token = localStorage.getItem('session_token');
  if (!token) {
    location.href = `/admin?next=${encodeURIComponent(location.pathname)}`;
    return false;
  }
  try {
    await api('/auth/session');
    return true;
  } catch {
    return false;
  }
}

async function init() {
  if (!(await requireAuth())) return;
  document.getElementById('logout-btn')?.addEventListener('click', logout);
  await updateAuthHeader();
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
  loadReadinessBadge();
  geoConfig = await api('/geo/config');
  await api('/geo/seed', { method: 'POST' });
}

init();
