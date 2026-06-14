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
  ['search-l3', 'bs-l3'].forEach((id) => {
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
  });
});

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

// Market Intel Tab5
async function loadMarket() {
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
  geoConfig = await api('/geo/config');
  await api('/geo/seed', { method: 'POST' });
}

init();
