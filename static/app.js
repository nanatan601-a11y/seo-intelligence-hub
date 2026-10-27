const state = {
  dashboard: null,
  sources: [],
  articles: new Map(),
  route: '',
};

const STATIC_DEMO = Boolean(window.SIGNAL_DESK_DEMO) &&
  (location.protocol === 'file:' || location.hostname.endsWith('github.io') ||
   (['127.0.0.1', 'localhost'].includes(location.hostname) && location.port !== '8765'));

function demoApi(path, options = {}) {
  const demo = window.SIGNAL_DESK_DEMO;
  const method = options.method || 'GET';
  const url = new URL(path, location.href);
  if (path === '/api/dashboard') return structuredClone(demo.dashboard);
  if (path === '/api/sources' && method === 'GET') return { items: structuredClone(demo.sources) };
  if (path === '/api/experts') return { items: structuredClone(demo.experts) };
  if (path.startsWith('/api/articles?')) {
    let items = [...demo.articles];
    const params = url.searchParams;
    const category = params.get('category');
    const source = params.get('source');
    const market = params.get('market');
    const query = (params.get('q') || '').toLowerCase();
    const days = Number(params.get('days') || 0);
    if (category) items = items.filter(item => item.category === category);
    if (source) items = items.filter(item => String(item.source_id) === source);
    if (market) items = items.filter(item => item.market === market);
    if (params.get('official') === '1') items = items.filter(item => item.source_tier === 'T0');
    if (params.get('experts') === '1') items = items.filter(item => ['expert', 'social'].includes(item.source_kind));
    if (params.get('bookmarked') === '1') items = items.filter(item => item.is_bookmarked);
    if (days) {
      const cutoff = Date.now() - days * 86400000;
      items = items.filter(item => new Date(item.published_at || item.fetched_at).getTime() >= cutoff);
    }
    if (query) items = items.filter(item => [item.title, item.summary, item.source_name, ...(item.tags || [])].join(' ').toLowerCase().includes(query));
    items = items.slice(0, Number(params.get('limit') || 100));
    return { items: structuredClone(items) };
  }
  const articleMatch = path.match(/^\/api\/articles\/(\d+)$/);
  if (articleMatch && method === 'PATCH') {
    const article = demo.articles.find(item => String(item.id) === articleMatch[1]);
    if (!article) throw new Error('Article not found.');
    Object.assign(article, JSON.parse(options.body || '{}'));
    return structuredClone(article);
  }
  const sourceMatch = path.match(/^\/api\/sources\/(\d+)$/);
  if (sourceMatch && method === 'PATCH') {
    const sourceItem = demo.sources.find(item => String(item.id) === sourceMatch[1]);
    if (!sourceItem) throw new Error('Source not found.');
    Object.assign(sourceItem, JSON.parse(options.body || '{}'));
    return structuredClone(sourceItem);
  }
  if (path === '/api/refresh' || path === '/api/weekly') return { demo: true, added: 0, ok: demo.sources.filter(item => item.enabled).length, errors: 0 };
  if (path === '/api/sources' && method === 'POST') throw new Error('The public portfolio is read-only. Run the Python app to add sources.');
  throw new Error(`This action is unavailable in the static portfolio demo: ${path}`);
}

const CATEGORY = {
  content: { label: 'Content SEO', eyebrow: 'CONTENT INTELLIGENCE', description: 'Search intent, topical strategy, content quality, entity semantics, E-E-A-T and content lifecycle.', color: '#ee886d' },
  technical: { label: 'Technical SEO', eyebrow: 'TECHNICAL INTELLIGENCE', description: 'Crawling, indexing, rendering, site architecture, structured data, performance and technical audits.', color: '#5db9b4' },
  authority: { label: 'Authority SEO', eyebrow: 'AUTHORITY & DIGITAL PR', description: 'Digital PR, link acquisition, brand and author entities, industry mentions and online reputation.', color: '#9d8cd8' },
  international: { label: 'International SEO', eyebrow: 'GLOBAL SEARCH', description: 'Multilingual and multiregional SEO, hreflang, localization, regional search behavior and cross-market growth.', color: '#e0b65c' },
  geo: { label: 'GEO / AI Search', eyebrow: 'GENERATIVE SEARCH', description: 'AI search platforms, LLM visibility, citation monitoring, entity optimization and reproducible experiments.', color: '#8fd17f' },
  sem: { label: 'SEM', eyebrow: 'PAID SEARCH', description: 'Google Ads, Microsoft Ads, bidding, automation, landing pages, attribution and SEO alignment.', color: '#7298d9' },
};

const ROUTE_LABELS = {
  dashboard: 'Dashboard', weekly: 'Weekly Brief', official: 'Official Updates',
  content: 'Content SEO', technical: 'Technical SEO', authority: 'Authority SEO',
  international: 'International SEO', geo: 'GEO / AI Search', sem: 'SEM',
  experts: 'Expert Network', search: 'Search & Archive', sources: 'Source Registry',
};

const app = document.querySelector('#app');
const sourceDialog = document.querySelector('#source-dialog');
const articleDialog = document.querySelector('#article-dialog');

function rememberArticle(article) {
  if (article?.id !== undefined && article?.id !== null) state.articles.set(String(article.id), article);
  return article;
}

async function api(path, options = {}) {
  if (STATIC_DEMO) return demoApi(path, options);
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  let payload;
  try { payload = await response.json(); } catch { payload = { error: `HTTP ${response.status}` }; }
  if (!response.ok) throw new Error(payload.error || `Request failed: ${response.status}`);
  return payload;
}

function esc(value = '') {
  return String(value).replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
}

function safeUrl(value = '') {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) ? esc(url.href) : '#';
  } catch { return '#'; }
}

function formatDate(value, style = 'short') {
  if (!value) return 'Unknown date';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unknown date';
  if (style === 'full') return new Intl.DateTimeFormat('en-US', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }).format(date);
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(date);
}

function currentDateParts() {
  const now = new Date();
  return {
    main: new Intl.DateTimeFormat('en-US', { month: 'long', day: 'numeric' }).format(now),
    sub: new Intl.DateTimeFormat('en-US', { year: 'numeric', weekday: 'long' }).format(now),
  };
}

function toast(message, type = '') {
  const node = document.createElement('div');
  node.className = `toast ${type}`;
  node.textContent = message;
  document.querySelector('#toast-stack').appendChild(node);
  setTimeout(() => node.remove(), 4200);
}

function loading(message = 'Organizing intelligence…') {
  app.innerHTML = `<div class="loading-state"><div class="spinner"></div><p>${esc(message)}</p></div>`;
}

function errorView(error) {
  app.innerHTML = `<div class="error-state"><strong>Unable to load</strong><p>${esc(error.message)}</p><button class="button dark" data-action="retry">Try again</button></div>`;
}

function emptyView(title = 'No intelligence yet', text = 'Run a refresh to collect the latest signals.') {
  return `<div class="empty-state"><strong>${esc(title)}</strong><p>${esc(text)}</p><button class="button dark" data-action="refresh">Refresh intelligence</button></div>`;
}

function pageHeader(eyebrow, title, description, action = '') {
  const date = currentDateParts();
  return `<header class="page-header">
    <div><span class="eyebrow">${esc(eyebrow)}</span><h1>${esc(title)}</h1><p>${esc(description)}</p></div>
    ${action || `<div class="date-block"><strong>${esc(date.main)}</strong><small>${esc(date.sub)}</small></div>`}
  </header>`;
}

function articleRow(article) {
  rememberArticle(article);
  return `<article class="article-row" data-article-id="${article.id}">
    <div class="article-date">${formatDate(article.published_at || article.fetched_at)}<br>${esc(article.language || '').toUpperCase()}</div>
    <div class="article-main">
      <h3><button class="article-title-button" data-article-preview="${article.id}">${esc(article.title)}</button></h3>
      <div class="article-meta"><span class="tier ${String(article.source_tier).toLowerCase()}">${esc(article.source_tier)}</span><span>${esc(article.source_name)}</span><span>·</span><span>${esc(CATEGORY[article.category]?.label || article.category)}</span></div>
    </div>
    <div class="article-actions"><button class="mini-button ${article.is_bookmarked ? 'on' : ''}" data-bookmark="${article.id}" data-value="${article.is_bookmarked ? '0' : '1'}" title="Bookmark">${article.is_bookmarked ? '★' : '☆'}</button><a class="mini-button" href="${safeUrl(article.url)}" target="_blank" rel="noopener noreferrer" data-article-link="${article.id}" title="Open original article">↗</a></div>
  </article>`;
}

function storyCard(article) {
  rememberArticle(article);
  const tags = (article.tags || []).map(tag => `<span class="tag">${esc(tag)}</span>`).join('');
  return `<article class="story-card" data-article-id="${article.id}">
    <div class="story-card-top"><span class="category-pill">${esc(CATEGORY[article.category]?.label || article.category)}</span><span class="tier ${String(article.source_tier).toLowerCase()}">${esc(article.source_tier)}</span></div>
    <h2><button class="article-title-button" data-article-preview="${article.id}">${esc(article.title)}</button></h2>
    <p class="summary">${esc(article.summary || 'This source did not provide a summary. Open the original article for full context.')}</p>
    <div class="tag-list">${tags || '<span class="tag">Unclassified</span>'}</div>
    <footer class="story-foot"><div class="story-source"><strong>${esc(article.source_name)}</strong><small>${formatDate(article.published_at || article.fetched_at)} · ${esc(article.market)}</small></div><div class="article-actions"><button class="mini-button ${article.is_bookmarked ? 'on' : ''}" data-bookmark="${article.id}" data-value="${article.is_bookmarked ? '0' : '1'}">${article.is_bookmarked ? '★' : '☆'}</button><a class="mini-button" href="${safeUrl(article.url)}" target="_blank" rel="noopener noreferrer" data-article-link="${article.id}" title="Open original article">↗</a></div></footer>
  </article>`;
}

function markArticleRead(id) {
  api(`/api/articles/${id}`, { method: 'PATCH', body: JSON.stringify({ is_read: true }) }).catch(() => {});
  state.dashboard = null;
}

function openArticlePreview(id) {
  const article = state.articles.get(String(id));
  if (!article) return;
  const tags = (article.tags || []).map(tag => `<span class="tag">${esc(tag)}</span>`).join('');
  const sourceName = article.source_name || article.source || 'Unknown source';
  const tier = article.source_tier || article.tier || 'T3';
  const summary = article.summary || article.excerpt || 'This source did not provide a summary. Open the original article to continue reading.';
  articleDialog.querySelector('#article-dialog-content').innerHTML = `
    <div class="article-preview">
      <div class="modal-head"><div><span class="eyebrow">IN-APP PREVIEW</span><h2 id="article-preview-title">${esc(article.title)}</h2></div><button type="button" class="icon-button" data-close-article aria-label="Close">×</button></div>
      <div class="article-preview-meta"><span class="tier ${String(tier).toLowerCase()}">${esc(tier)}</span><span>${esc(sourceName)}</span><span>${formatDate(article.published_at || article.fetched_at, 'full')}</span><span>${esc(CATEGORY[article.category]?.label || article.category || '')}</span></div>
      <p class="article-preview-summary">${esc(summary)}</p>
      ${tags ? `<div class="tag-list">${tags}</div>` : ''}
      <div class="preview-note"><strong>Why show a preview first?</strong><span>It keeps redirects, login walls and security prompts from interrupting your workflow. Open the source only when you need the full article.</span></div>
      <div class="modal-actions"><button type="button" class="button ghost" data-close-article>Close</button><a class="button primary external-button" href="${safeUrl(article.url)}" target="_blank" rel="noopener noreferrer" data-article-link="${article.id}">Open original ↗</a></div>
    </div>`;
  articleDialog.showModal();
  markArticleRead(id);
}

async function loadDashboard(force = false) {
  if (!state.dashboard || force) state.dashboard = await api('/api/dashboard');
  return state.dashboard;
}

function renderDashboard(data) {
  const stats = data.stats;
  const latest = data.latest || [];
  const categories = data.categories || {};
  const maxCount = Math.max(1, ...Object.values(categories));
  const totalInBars = Object.values(categories).reduce((sum, n) => sum + n, 0);
  const colorMap = Object.fromEntries(Object.entries(CATEGORY).map(([key, value]) => [key, value.color]));
  const weeklyGroups = data.weekly?.groups || {};
  const weeklyInsights = Object.values(weeklyGroups).flat();
  const populated = weeklyInsights.filter(item => item.evidence?.length).length;
  const articleRows = latest.slice(0, 7).map(articleRow).join('');
  const bars = Object.keys(CATEGORY).map(key => `<div class="bar-row"><span>${esc(CATEGORY[key].label)}</span><div class="bar-track"><div class="bar-fill" style="--width:${Math.round(((categories[key] || 0) / maxCount) * 100)}%;--color:${colorMap[key]}"></div></div><b>${categories[key] || 0}</b></div>`).join('');
  const weekly = data.weekly || {};
  document.querySelector('#health-detail').textContent = `${data.source_stats.healthy}/${data.source_stats.enabled} enabled sources healthy`;
  document.querySelector('#health-dot').classList.toggle('warn', data.source_stats.errors > 0);

  app.innerHTML = `
    ${pageHeader('GOOD MORNING · SEO STRATEGIST', 'Your search intelligence is ready.', 'Official updates, industry research and expert insight—organized by evidence tier, discipline and market.')}
    <section class="metric-grid">
      <div class="metric-card" style="--tint:#eaf4df"><span class="metric-label"><i class="metric-icon">↗</i>New this week</span><strong>${stats.week}</strong><small>All sources · deduplicated</small></div>
      <div class="metric-card" style="--tint:#e4f1ef"><span class="metric-label"><i class="metric-icon">◎</i>Official updates</span><strong>${stats.official_week}</strong><small>T0 · primary sources</small></div>
      <div class="metric-card" style="--tint:#f8ecd3"><span class="metric-label"><i class="metric-icon">◇</i>Unread</span><strong>${stats.unread}</strong><small>Current reading queue</small></div>
      <div class="metric-card" style="--tint:#eee8f7"><span class="metric-label"><i class="metric-icon">☆</i>Bookmarked</span><strong>${stats.bookmarked}</strong><small>Research and action leads</small></div>
    </section>
    <section class="dashboard-grid">
      <div class="stack">
        <div class="signal-banner">
          <span class="eyebrow">WEEKLY SIGNAL</span>
          <h2>${esc(weekly.title || 'Awaiting the first weekly brief')}</h2>
          <p>${esc(weekly.executive_summary || 'Refresh the feeds to generate a structured weekly brief.')}</p>
          <div class="signal-meta"><span><b>${weekly.priorities?.length || 0}</b> priorities</span><span><b>${populated}</b> active disciplines</span><span><b>${weekly.evidence_count || 0}</b> evidence sources</span></div>
        </div>
        <div class="panel">
          <div class="panel-head"><div><h2>Latest intelligence</h2><p>Ranked by recency and source priority</p></div><button class="text-link" data-route-jump="search">View all →</button></div>
          ${articleRows ? `<div class="article-list">${articleRows}</div>` : emptyView()}
        </div>
      </div>
      <aside class="stack">
        <div class="panel"><div class="panel-head"><div><h2>Channel coverage</h2><p>Current knowledge-base distribution</p></div><b>${totalInBars}</b></div><div class="channel-bars">${bars}</div></div>
        <div class="panel brief-card"><span class="eyebrow">SOURCE HEALTH</span><h3>Source network</h3><p>Every feed is monitored independently. One failing source never blocks the rest of the pipeline and can be retried on its own.</p><div class="brief-stats"><div><strong>${data.source_stats.enabled}</strong><small>ENABLED</small></div><div><strong>${data.source_stats.healthy}</strong><small>HEALTHY</small></div><div><strong>${data.source_stats.errors}</strong><small>ERRORS</small></div></div><button class="text-link" data-route-jump="sources" style="margin-top:16px">Manage sources →</button></div>
      </aside>
    </section>`;
}

async function renderChannel(category) {
  const meta = CATEGORY[category];
  loading(`Loading ${meta.label}…`);
  const payload = await api(`/api/articles?category=${encodeURIComponent(category)}&limit=90`);
  const items = payload.items || [];
  app.innerHTML = `${pageHeader(meta.eyebrow, meta.label, meta.description)}
    <div class="filter-row"><button class="filter-chip active" data-channel-days="all">All</button><button class="filter-chip" data-channel-days="7">Last 7 days</button><button class="filter-chip" data-channel-days="30">Last 30 days</button><button class="filter-chip" data-channel-official="1">Official only</button></div>
    <div class="results-count" style="margin-bottom:13px;color:var(--muted);font-size:10px">${items.length} intelligence items</div>
    <section class="card-grid">${items.map(storyCard).join('')}</section>${items.length ? '' : emptyView(`No ${meta.label} intelligence yet`)}`;
  app.dataset.category = category;
}

async function filterChannel(button) {
  const category = app.dataset.category;
  if (!category) return;
  document.querySelectorAll('.filter-chip').forEach(node => node.classList.remove('active'));
  button.classList.add('active');
  const days = button.dataset.channelDays;
  const official = button.dataset.channelOfficial;
  const params = new URLSearchParams({ category, limit: '90' });
  if (days && days !== 'all') params.set('days', days);
  if (official) params.set('official', '1');
  const payload = await api(`/api/articles?${params}`);
  const grid = document.querySelector('.card-grid');
  grid.innerHTML = payload.items.map(storyCard).join('');
  document.querySelector('.results-count').textContent = `${payload.items.length} intelligence items`;
}

async function renderOfficial() {
  loading('Loading official updates…');
  const payload = await api('/api/articles?official=1&limit=100');
  const items = payload.items || [];
  app.innerHTML = `${pageHeader('T0 · PRIMARY SOURCES', 'Official Updates', 'First-party updates from search engines, advertising platforms, browsers and standards bodies—the highest-priority evidence in every brief.')}
    <section class="card-grid">${items.map(storyCard).join('')}</section>${items.length ? '' : emptyView('No official updates collected yet')}`;
}

function evidenceLinks(items = []) {
  if (!items.length) return '<p class="no-evidence">No new citable evidence this week</p>';
  return `<div class="evidence-list">${items.map(item => {
    rememberArticle({ ...item, source_name: item.source, source_tier: item.tier, summary: item.excerpt });
    return item.id ? `<button data-article-preview="${item.id}"><span class="tier ${String(item.tier).toLowerCase()}">${esc(item.tier)}</span><span><strong>${esc(item.source)}</strong><small>${esc(item.title)} · ${formatDate(item.published_at)}</small></span><i>Preview</i></button>` : `<a href="${safeUrl(item.url)}" target="_blank" rel="noopener noreferrer"><span class="tier ${String(item.tier).toLowerCase()}">${esc(item.tier)}</span><span><strong>${esc(item.source)}</strong><small>${esc(item.title)} · ${formatDate(item.published_at)}</small></span><i>↗</i></a>`;
  }).join('')}</div>`;
}

function priorityCard(item, index) {
  const source = item.evidence?.[0];
  return `<article class="priority-card">
    <div class="priority-number">0${index + 1}</div>
    <span class="category-pill">${esc(CATEGORY[item.category]?.label || item.category)}</span>
    <h3>${esc(item.headline)}</h3>
    <div class="priority-detail"><b>Why it matters</b><p>${esc(item.why_it_matters)}</p></div>
    <div class="priority-detail response"><b>Recommended response</b><p>${esc(item.response)}</p></div>
    ${source ? `<a class="priority-source" href="${safeUrl(source.url)}" target="_blank" rel="noopener noreferrer"><span class="tier ${String(source.tier).toLowerCase()}">${esc(source.tier)}</span>${esc(source.source)} ↗</a>` : ''}
  </article>`;
}

function insightCard(insight) {
  const watchPoints = (insight.watch_points || []).map(item => `<li>${esc(item)}</li>`).join('');
  const responses = (insight.responses || []).map(item => `<li>${esc(item)}</li>`).join('');
  const hasEvidence = insight.evidence?.length;
  return `<article class="panel insight-card ${hasEvidence ? '' : 'muted-insight'}">
    <header class="insight-head"><div><span class="eyebrow">${esc(CATEGORY[insight.category]?.eyebrow || insight.category)}</span><h2>${esc(insight.label || CATEGORY[insight.category]?.label)}</h2></div><span class="insight-status ${hasEvidence ? 'active' : ''}">${esc(insight.status)}</span></header>
    <h3 class="insight-signal">${esc(insight.signal)}</h3>
    <p class="insight-summary">${esc(insight.summary)}</p>
    <div class="insight-columns">
      <section><h4>What to watch</h4><ul>${watchPoints}</ul></section>
      <section><h4>Potential impact</h4><p>${esc(insight.impact)}</p></section>
      <section class="solution"><h4>Response plan</h4><ol>${responses}</ol></section>
    </div>
    <div class="evidence-block"><h4>Supporting evidence</h4>${evidenceLinks(insight.evidence)}</div>
  </article>`;
}

async function renderWeekly(force = false) {
  loading('Preparing this week’s brief…');
  const data = await loadDashboard(force);
  const report = data.weekly;
  const core = report.groups?.core_capabilities || [];
  const specialties = report.groups?.professional_directions || [];
  const activeCount = [...core, ...specialties].filter(item => item.evidence?.length).length;
  const modeText = report.mode === 'ai' ? 'OpenAI analysis' : 'Evidence-rule synthesis';
  app.innerHTML = `${pageHeader('WEEKLY BRIEFING', 'Weekly Intelligence Brief', 'A decision-ready synthesis of meaningful changes, supporting evidence, likely impact and recommended responses.', `<div class="top-actions"><button class="button ghost" data-generate-weekly="local">Rebuild brief</button><button class="button primary" data-generate-weekly="ai">Generate AI analysis</button></div>`)}
    <section class="weekly-layout">
      <div class="stack">
        <div class="report-cover"><span class="eyebrow">SEARCH INTELLIGENCE · WEEKLY</span><h1>${esc(report.title)}</h1><p>${esc(report.executive_summary)}</p><div class="report-meta"><span>${esc(report.period)}</span><span>${esc(modeText)}</span><span>${activeCount} disciplines with new signals</span></div></div>
        <div class="panel priority-panel"><div class="panel-head"><div><h2>Top priorities</h2><p>Selected by evidence quality, recency and business impact</p></div><span class="priority-count">${report.priorities?.length || 0} ITEMS</span></div><div class="priority-grid">${(report.priorities || []).map(priorityCard).join('') || '<p class="no-evidence">No sufficiently reliable new signals this week.</p>'}</div></div>
        <div class="report-group-title"><span>01</span><div><strong>Core capabilities</strong><small>Content · Technical · Authority</small></div></div>
        ${core.map(insightCard).join('')}
        <div class="report-group-title"><span>02</span><div><strong>Specialist tracks</strong><small>International · GEO · SEM</small></div></div>
        ${specialties.map(insightCard).join('')}
      </div>
      <aside class="stack">
        <div class="panel report-section"><span class="eyebrow">NEXT ACTIONS</span><h2>Priority actions</h2><ol class="action-list">${(report.actions || []).map(action => `<li>${esc(action)}</li>`).join('')}</ol></div>
        <div class="panel brief-card"><span class="eyebrow">EVIDENCE POLICY</span><h3>How to read this brief</h3><p>${esc(report.methodology || '')}</p><div class="brief-stats"><div><strong>${report.evidence_count || 0}</strong><small>SOURCES</small></div><div><strong>${activeCount}</strong><small>ACTIVE AREAS</small></div></div></div>
        <div class="panel brief-card"><span class="eyebrow">AI SETUP</span><h3>Enable deeper synthesis</h3><p>With <code>OPENAI_API_KEY</code> configured, AI extracts consensus, impact and response options within the same evidence framework. It does not invent facts outside the collected sources.</p></div>
      </aside>
    </section>`;
}

async function renderExperts() {
  loading('Loading the expert network…');
  const [experts, insights] = await Promise.all([api('/api/experts'), api('/api/articles?experts=1&limit=30')]);
  const cards = experts.items.map(expert => {
    const initials = expert.name.split(/\s+/).map(part => part[0]).join('').slice(0, 2).toUpperCase();
    const specialties = (expert.specialties || []).map(item => `<span class="tag">${esc(item)}</span>`).join('');
    return `<article class="expert-card"><div class="expert-head"><div class="avatar">${esc(initials)}</div><div><h2>${esc(expert.name)}</h2><p>${esc(CATEGORY[expert.primary_category]?.label || expert.primary_category)} · ${esc(expert.market)}</p></div></div><p><strong>${esc(expert.organization)}</strong><br>${esc(expert.role)}</p><div class="tag-list expert-tags">${specialties}</div><div class="expert-stats"><div><strong>${expert.article_count}</strong><small>COLLECTED ARTICLES</small></div><div><strong>${expert.feed_enabled ? 'Feed' : 'Profile'}</strong><small>MONITORING MODE</small></div></div><div class="expert-links"><a class="text-link" href="${safeUrl(expert.website_url)}" target="_blank" rel="noopener noreferrer">Website ↗</a><a class="text-link x-link" href="${safeUrl(expert.x_url)}" target="_blank" rel="noopener noreferrer">X profile ↗</a></div></article>`;
  }).join('');
  app.innerHTML = `${pageHeader('EXPERT NETWORK', `${experts.items.length} search-industry experts`, 'Websites, RSS feeds and X profiles form a dual monitoring layer: durable content is collected automatically, while social posts surface timely hypotheses to verify against primary evidence.')}
    <section class="expert-grid">${cards}</section>
    <div class="panel" style="margin-top:18px"><div class="panel-head"><div><h2>Latest expert insight</h2><p>T2/T3 · analysis, not official guidance</p></div></div>${insights.items.length ? `<div class="article-list">${insights.items.map(articleRow).join('')}</div>` : emptyView('No expert articles collected yet')}</div>`;
}

async function renderSearch() {
  if (!state.sources.length) state.sources = (await api('/api/sources')).items;
  app.innerHTML = `${pageHeader('KNOWLEDGE ARCHIVE', 'Search & Archive', 'Search titles, summaries, tags and sources across disciplines to recover citable primary evidence and useful cases.')}
    <form id="search-form"><div class="search-box"><input id="search-input" name="q" autocomplete="off" placeholder="Search a topic, tool, expert or idea—e.g. hreflang, JavaScript rendering…"><button type="submit">⌕</button></div>
    <div class="filter-panel"><select name="category"><option value="">All channels</option>${Object.entries(CATEGORY).map(([key, meta]) => `<option value="${key}">${esc(meta.label)}</option>`).join('')}</select><select name="source"><option value="">All sources</option>${state.sources.map(source => `<option value="${source.id}">${esc(source.name)}</option>`).join('')}</select><select name="days"><option value="">All time</option><option value="7">Last 7 days</option><option value="30">Last 30 days</option><option value="365">Last year</option></select><select name="scope"><option value="">All intelligence</option><option value="official">Official only</option><option value="bookmarked">Bookmarked only</option></select></div></form>
    <div id="search-results">${emptyView('Enter a keyword to search', 'Or browse by channel, source and time range without a query.').replace('data-action="refresh"', 'data-action="search-all"').replace('Refresh intelligence', 'Browse all intelligence')}</div>`;
  setTimeout(() => document.querySelector('#search-input')?.focus(), 0);
}

async function executeSearch(form = document.querySelector('#search-form')) {
  const formData = new FormData(form);
  const params = new URLSearchParams({ limit: '120' });
  for (const [key, value] of formData.entries()) {
    if (!value) continue;
    if (key === 'scope' && value === 'official') params.set('official', '1');
    else if (key === 'scope' && value === 'bookmarked') params.set('bookmarked', '1');
    else params.set(key, value);
  }
  const target = document.querySelector('#search-results');
  target.innerHTML = `<div class="loading-state"><div class="spinner"></div></div>`;
  const payload = await api(`/api/articles?${params}`);
  target.innerHTML = `<p style="color:var(--muted);font-size:10px">${payload.items.length} results</p><section class="card-grid">${payload.items.map(storyCard).join('')}</section>${payload.items.length ? '' : emptyView('No matching results', 'Try a broader keyword or remove one of the filters.')}`;
}

async function renderSources() {
  loading('Loading the source registry…');
  state.sources = (await api('/api/sources')).items;
  const enabled = state.sources.filter(s => s.enabled).length;
  const healthy = state.sources.filter(s => s.last_status === 'ok').length;
  const errors = state.sources.filter(s => s.last_status === 'error').length;
  const rows = state.sources.map(source => `<tr>
    <td><div class="source-name"><strong>${esc(source.name)}</strong><small>${esc(source.feed_url || source.site_url || 'No URL configured')}</small></div></td>
    <td>${esc(source.kind)}</td><td>${esc(CATEGORY[source.category]?.label || source.category)}</td><td><span class="tier ${source.tier.toLowerCase()}">${esc(source.tier)}</span></td>
    <td><span class="status ${esc(source.last_status)}" title="${esc(source.last_error)}">${source.last_status === 'ok' ? 'Healthy' : source.last_status === 'error' ? 'Error' : 'Pending'}</span></td>
    <td>${source.last_fetch_at ? formatDate(source.last_fetch_at) : '—'}</td>
    <td><button class="switch ${source.enabled ? 'on' : ''}" data-source-toggle="${source.id}" data-value="${source.enabled ? '0' : '1'}" aria-label="Enable or disable source"></button></td>
    <td><button class="mini-button" data-source-refresh="${source.id}" title="Refresh this source">↻</button></td>
  </tr>`).join('');
  app.innerHTML = `${pageHeader('SOURCE REGISTRY', 'Source Registry', 'Manage RSS/Atom feeds, primary sources and expert entry points. Each source keeps its own health state, so one failure never interrupts the pipeline.')}
    <section class="metric-grid"><div class="metric-card"><span class="metric-label">All sources</span><strong>${state.sources.length}</strong><small>Official, media and experts</small></div><div class="metric-card"><span class="metric-label">Enabled</span><strong>${enabled}</strong><small>Included in scheduled refreshes</small></div><div class="metric-card"><span class="metric-label">Healthy</span><strong>${healthy}</strong><small>Most recent refresh succeeded</small></div><div class="metric-card"><span class="metric-label">Needs attention</span><strong>${errors}</strong><small>Review source status</small></div></section>
    <div class="source-toolbar"><p>RSS/Atom powers the first release. Login-gated platforms should be connected through official APIs or another compliant route.</p><button class="button primary" data-add-source>＋ Add source</button></div>
    <div class="table-wrap"><table class="data-table"><thead><tr><th>Source</th><th>Type</th><th>Channel</th><th>Tier</th><th>Status</th><th>Last refresh</th><th>Enabled</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

async function route() {
  const name = (location.hash || '#dashboard').slice(1).split('?')[0];
  state.route = ROUTE_LABELS[name] ? name : 'dashboard';
  document.querySelector('#page-crumb').textContent = ROUTE_LABELS[state.route];
  document.querySelectorAll('.nav-link').forEach(link => link.classList.toggle('active', link.dataset.route === state.route));
  document.querySelector('#sidebar').classList.remove('open');
  try {
    if (state.route === 'dashboard') renderDashboard(await loadDashboard());
    else if (state.route === 'weekly') await renderWeekly();
    else if (state.route === 'official') await renderOfficial();
    else if (CATEGORY[state.route]) await renderChannel(state.route);
    else if (state.route === 'experts') await renderExperts();
    else if (state.route === 'search') await renderSearch();
    else if (state.route === 'sources') await renderSources();
  } catch (error) { errorView(error); }
  window.scrollTo({ top: 0, behavior: 'instant' });
}

async function refreshAll(sourceId = null) {
  if (STATIC_DEMO) {
    toast('This portfolio uses a curated snapshot. Run the Python app for live feed refreshes.');
    return;
  }
  const button = document.querySelector('#refresh-button');
  button.disabled = true;
  button.classList.add('busy');
  try {
    const result = await api('/api/refresh', { method: 'POST', body: JSON.stringify(sourceId ? { source_id: sourceId } : {}) });
    state.dashboard = null;
    const message = `Refresh complete: ${result.added} added, ${result.ok} sources succeeded${result.errors ? `, ${result.errors} need attention` : ''}`;
    toast(message, result.errors ? '' : 'success');
    await route();
  } catch (error) { toast(error.message, 'error'); }
  finally { button.disabled = false; button.classList.remove('busy'); }
}

document.addEventListener('click', async event => {
  const target = event.target.closest('button, a');
  if (!target) return;
  if (target.dataset.routeJump) location.hash = target.dataset.routeJump;
  if (target.dataset.action === 'retry') route();
  if (target.dataset.action === 'refresh') refreshAll();
  if (target.dataset.action === 'search-all') executeSearch();
  if (target.dataset.channelDays || target.dataset.channelOfficial) filterChannel(target).catch(error => toast(error.message, 'error'));
  if (target.dataset.bookmark) {
    event.preventDefault();
    try {
      const article = await api(`/api/articles/${target.dataset.bookmark}`, { method: 'PATCH', body: JSON.stringify({ is_bookmarked: target.dataset.value === '1' }) });
      target.dataset.value = article.is_bookmarked ? '0' : '1';
      target.textContent = article.is_bookmarked ? '★' : '☆';
      target.classList.toggle('on', article.is_bookmarked);
      state.dashboard = null;
    } catch (error) { toast(error.message, 'error'); }
  }
  if (target.dataset.articleLink) {
    markArticleRead(target.dataset.articleLink);
  }
  if (target.dataset.articlePreview) openArticlePreview(target.dataset.articlePreview);
  if (target.dataset.closeArticle !== undefined) articleDialog.close();
  if (target.dataset.generateWeekly) {
    const useAi = target.dataset.generateWeekly === 'ai';
    target.disabled = true;
    try {
      await api('/api/weekly', { method: 'POST', body: JSON.stringify({ use_ai: useAi }) });
      state.dashboard = null;
      toast(STATIC_DEMO ? 'The portfolio shows a pre-generated weekly brief.' : useAi ? 'AI brief generated' : 'Evidence brief updated', 'success');
      await renderWeekly(true);
    } catch (error) { toast(error.message, 'error'); }
    finally { target.disabled = false; }
  }
  if (target.dataset.addSource !== undefined) {
    if (STATIC_DEMO) toast('The public portfolio is read-only. Run the Python app to manage sources.');
    else sourceDialog.showModal();
  }
  if (target.dataset.closeModal !== undefined) sourceDialog.close();
  if (target.dataset.sourceToggle) {
    try {
      await api(`/api/sources/${target.dataset.sourceToggle}`, { method: 'PATCH', body: JSON.stringify({ enabled: target.dataset.value === '1' }) });
      toast(STATIC_DEMO ? 'Demo state updated for this browser session.' : 'Source status updated', 'success');
      await renderSources();
      state.dashboard = null;
    } catch (error) { toast(error.message, 'error'); }
  }
  if (target.dataset.sourceRefresh) refreshAll(Number(target.dataset.sourceRefresh));
});

document.querySelector('#refresh-button').addEventListener('click', () => refreshAll());
document.querySelector('#global-search-button').addEventListener('click', () => { location.hash = 'search'; });
document.querySelector('#menu-button').addEventListener('click', () => document.querySelector('#sidebar').classList.toggle('open'));

document.addEventListener('submit', async event => {
  if (event.target.id === 'search-form') {
    event.preventDefault();
    try { await executeSearch(event.target); } catch (error) { toast(error.message, 'error'); }
  }
  if (event.target.id === 'source-form') {
    event.preventDefault();
    const form = event.target;
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.enabled = true;
    try {
      await api('/api/sources', { method: 'POST', body: JSON.stringify(payload) });
      sourceDialog.close();
      form.reset();
      toast('Source added', 'success');
      state.dashboard = null;
      await renderSources();
    } catch (error) { toast(error.message, 'error'); }
  }
});

window.addEventListener('hashchange', route);
route();
