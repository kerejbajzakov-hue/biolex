import { LANGS, STRINGS } from './i18n.js';

// ---------- state ----------
const store = {
  get(key, fallback) { try { const v = localStorage.getItem(key); return v == null ? fallback : JSON.parse(v); } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ } },
};
const browserLang = (navigator.language || 'en').slice(0, 2);
let lang = store.get('biolex-lang', ['kk', 'ru'].includes(browserLang) ? browserLang : 'en');
let saved = store.get('biolex-saved', []);
const t = () => STRINGS[lang];

const view = document.getElementById('view');
const toastEl = document.getElementById('toast');

// ---------- helpers ----------
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function api(path, params = {}) {
  const url = new URL('/api' + path, location.origin);
  Object.entries({ lang, ...params }).forEach(([k, v]) => v != null && v !== '' && url.searchParams.set(k, v));
  const res = await fetch(url);
  if (!res.ok) throw new Error(res.status);
  return res.json();
}

const ICON_PATHS = {
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
  back: '<path d="M15 5l-7 7 7 7"/>',
  chev: '<path d="M9 5l7 7-7 7"/>',
  home: '<path d="M4 11l8-7 8 7v8a1 1 0 0 1-1 1h-4v-6h-6v6H5a1 1 0 0 1-1-1z"/>',
  grid: '<rect x="4" y="4" width="7" height="7" rx="2"/><rect x="13" y="4" width="7" height="7" rx="2"/><rect x="4" y="13" width="7" height="7" rx="2"/><rect x="13" y="13" width="7" height="7" rx="2"/>',
  bookmark: '<path d="M7 4h10a1 1 0 0 1 1 1v15l-6-4-6 4V5a1 1 0 0 1 1-1z"/>',
  chart: '<path d="M5 20V10"/><path d="M12 20V4"/><path d="M19 20v-7"/>',
  speaker: '<path d="M5 9h3l5-4v14l-5-4H5z"/><path d="M16 9a4 4 0 0 1 0 6"/><path d="M18.5 6.5a7.5 7.5 0 0 1 0 11"/>',
  share: '<path d="M12 4v11"/><path d="M8 8l4-4 4 4"/><path d="M5 13v6h14v-6"/>',
  arrow: '<path d="M5 12h14"/><path d="M13 6l6 6-6 6"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
};
const icon = (name, size = 20, fill = 'none') =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="${fill}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON_PATHS[name]}</svg>`;

const THEME_IMG = { dna: 'dna-small', cell: 'cell', leaf: 'leaf', molecule: 'molecule', bacterium: 'bacterium', sprout: 'sprout' };
const themeImg = (iconName, cls = 'clay-img', alt = '') => `<img class="${cls}" src="/img/${THEME_IMG[iconName] || 'cell'}.svg" alt="${esc(alt)}">`;

function orbs(list) {
  return list.map(([x, y, s, c]) => `<div class="orb" style="left:${x}px;top:${y}px;width:${s}px;height:${s}px;background:${c}"></div>`).join('');
}

function langSwitch() {
  return `<div class="lang-switch neu-in" role="group" aria-label="${esc(t().language)}">${
    LANGS.map((l) => `<button type="button" data-action="lang" data-lang="${l.code}" aria-pressed="${l.code === lang}">${l.label}</button>`).join('')
  }</div>`;
}

function tabbar(active) {
  const tabs = [['home', 'tabHome', '#/'], ['grid', 'tabThemes', '#/themes'], ['bookmark', 'tabSaved', '#/saved'], ['chart', 'tabStats', '#/stats']];
  return `<nav class="tabbar glass" aria-label="Main">${tabs.map(([ic, key, href]) => key === active
    ? `<a href="${href}" class="on clay-lime" aria-current="page">${icon(ic)}${esc(t()[key])}</a>`
    : `<a href="${href}" aria-label="${esc(t()[key])}">${icon(ic, 22)}</a>`).join('')}</nav>`;
}

const backBtn = (href) => `<a class="icon-btn neu" href="${href}" data-action="back" aria-label="${esc(t().back)}">${icon('back')}</a>`;
const isSaved = (slug) => saved.includes(slug);
const saveBtn = (slug) => `<button type="button" class="icon-btn neu ${isSaved(slug) ? 'saved' : ''}" data-action="save" data-slug="${esc(slug)}" aria-pressed="${isSaved(slug)}" aria-label="${esc(isSaved(slug) ? t().unsave : t().save)}">${icon('bookmark', 20, isSaved(slug) ? 'currentColor' : 'none')}</button>`;

function resultRow(item, compact = false) {
  return `<a class="result glass ${compact ? 'compact' : ''}" href="#/term/${encodeURIComponent(item.slug)}">
    <div class="body">
      <div class="row between"><span class="title">${esc(item.name)}</span>${compact ? '' : `<span class="chip">${esc(item.theme.name)}</span>`}</div>
      <span class="def">${esc(item.short_def)}</span>
    </div>${icon('chev', 18)}</a>`;
}

function emptyState(title, hint, img = 'cell') {
  return `<div class="empty"><img class="clay-img" src="/img/${img}.svg" alt=""><span class="display" style="font-size:17px;font-weight:700">${esc(title)}</span><span class="muted" style="font-size:14px">${esc(hint)}</span></div>`;
}

function errorState() {
  return `<div class="empty"><span class="display" style="font-size:17px;font-weight:700">${esc(t().error)}</span><button class="cta clay-lime" style="padding:0 24px;height:48px" data-action="retry">${esc(t().retry)}</button></div>`;
}

let toastTimer;
function toast(msg) {
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove('show'), 1600);
}

function setScreen(html, { tabs = null, orbList = [] } = {}) {
  view.innerHTML = orbs(orbList) + `<main class="screen ${tabs ? '' : 'no-tabs'}">${html}</main>` + (tabs ? tabbar(tabs) : '');
}

// ---------- screens ----------
function welcome() {
  setScreen(`
    <div class="welcome-stage">
      <div class="disc glass"></div>
      <img class="clay-img" src="/img/dna.svg" alt="" style="left:50%;margin-left:-55px;top:70px;height:360px;transform:rotate(-14deg)">
      <img class="clay-img" src="/img/cell.svg" alt="" style="left:30px;top:120px;width:88px;transform:rotate(-10deg)">
      <img class="clay-img" src="/img/leaf.svg" alt="" style="right:40px;top:112px;width:74px;transform:rotate(18deg)">
      <img class="clay-img" src="/img/molecule.svg" alt="" style="right:36px;top:330px;width:80px">
      <img class="clay-img" src="/img/mito.svg" alt="" style="left:26px;top:350px;width:92px;transform:rotate(-20deg)">
      <div class="row between" style="position:absolute;left:22px;right:22px;top:52px"><span class="display" style="font-weight:800;font-size:18px">BioLex</span>${langSwitch()}</div>
    </div>
    <h1 class="display" style="font-size:30px;font-weight:800;line-height:1.1">${esc(t().headline)}</h1>
    <p class="muted" style="margin:0;font-size:15px;line-height:1.5">${esc(t().sub)}</p>
    <div class="row" style="gap:12px">
      <button class="cta clay-lime" style="flex:1" data-action="start">${esc(t().start)} ${icon('arrow')}</button>
      <a class="cta neu" style="padding:0 20px;font-size:15px;color:var(--violet-text)" href="#/themes" data-action="start-themes">${esc(t().tabThemes)}</a>
    </div>`, { orbList: [[-80, 90, 300, '#6600FF'], [200, 300, 260, '#A7FC00'], [-40, 560, 220, '#B794FF']] });
}

async function home() {
  setScreen(`<div class="skeleton" style="height:500px"></div>`, { tabs: 'tabHome' });
  const [stats, themes, today] = await Promise.all([api('/stats'), api('/themes'), api('/terms/today')]);
  setScreen(`
    <div class="row between">
      <div class="row"><div class="neu" style="width:44px;height:44px;border-radius:14px;display:flex;align-items:center;justify-content:center"><img src="/img/logo.svg" alt="" style="height:30px"></div>
      <span class="display" style="font-weight:800;font-size:18px">BioLex</span></div>
      ${langSwitch()}
    </div>
    <h1 class="display" style="white-space:pre-line">${esc(t().hello)}</h1>
    <a class="search-bar neu-in" href="#/search">${icon('search', 20).replace('currentColor', '#6600FF')}<span class="placeholder">${esc(t().searchPh)}</span><span class="go clay-violet">${icon('arrow', 18)}</span></a>
    <div class="stat-pill glass"><b>${stats.total_terms}</b> ${esc(t().terms(stats.total_terms).replace(/^\d+\s*/, ''))} ${esc(t().inDictionary)} · ${esc(t().themesCount(stats.total_themes))}</div>
    <a class="tod glass" href="#/term/${encodeURIComponent(today.slug)}">
      <div class="text">
        <span class="chip lime" style="align-self:flex-start">${esc(t().tod)}</span>
        <span class="display" style="font-weight:700;font-size:19px;margin-top:4px">${esc(today.name)}</span>
        <span class="muted" style="font-size:13px;line-height:1.4">${esc(today.short_def)}</span>
        <span class="more">${esc(t().more)} ${icon('arrow', 16)}</span>
      </div>
      ${today.slug === 'mitochondrion' ? '<img class="clay-img" src="/img/mito.svg" alt="">' : themeImg(today.theme.icon, 'clay-img').replace('<img', '<img style="width:110px;right:6px;top:30px;transform:rotate(-8deg)"')}
    </a>
    <div class="row between" style="align-items:baseline"><h2 class="display" style="font-size:17px;font-weight:700">${esc(t().tabThemes)}</h2><a href="#/themes" style="font-size:13px;font-weight:800;color:var(--violet-text)">${esc(t().seeAll)}</a></div>
    <div class="grid3">${themes.map((th) => `
      <a class="tile neu" href="#/theme/${th.slug}">${themeImg(th.icon)}<span class="name">${esc(th.name)}</span><span class="count">${esc(t().terms(th.term_count))}</span></a>`).join('')}
    </div>`, { tabs: 'tabHome', orbList: [[180, 250, 260, '#6600FF'], [-90, 120, 220, '#A7FC00'], [220, 620, 200, '#B794FF']] });
}

// search keeps its input mounted and only swaps the results list
let searchState = { q: '', theme: '' };
let searchSeq = 0;
async function search(params) {
  searchState = { q: params.get('q') || '', theme: params.get('theme') || '' };
  const themes = await api('/themes');
  setScreen(`
    <div class="row">
      ${backBtn('#/')}
      <label class="search-bar neu-in" style="flex:1;padding-right:12px">${icon('search', 20).replace('currentColor', '#6600FF')}
        <input id="q" type="search" autocomplete="off" aria-label="${esc(t().searchPh)}" placeholder="${esc(t().searchPh)}" value="${esc(searchState.q)}">
      </label>
    </div>
    <div class="chips-row" id="filters">${[{ slug: '', name: t().all }, ...themes].map((th) =>
      `<button type="button" class="filter ${th.slug === searchState.theme ? 'on clay-violet' : ''}" data-action="filter" data-theme="${th.slug}" aria-pressed="${th.slug === searchState.theme}">${esc(th.name)}</button>`).join('')}
    </div>
    <div id="count" class="muted" style="font-size:13px;font-weight:700;margin-top:-10px"></div>
    <div id="results" class="list"><div class="skeleton"></div><div class="skeleton"></div></div>`,
  { tabs: 'tabHome', orbList: [[200, 160, 240, '#6600FF'], [-80, 500, 240, '#A7FC00']] });
  const input = document.getElementById('q');
  input.focus();
  input.setSelectionRange(input.value.length, input.value.length);
  let timer;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => { searchState.q = input.value; runSearch(); }, 180);
  });
  runSearch();
}

async function runSearch() {
  const seq = ++searchSeq;
  const qs = new URLSearchParams();
  if (searchState.q) qs.set('q', searchState.q);
  if (searchState.theme) qs.set('theme', searchState.theme);
  history.replaceState(null, '', '#/search' + (qs.toString() ? '?' + qs : ''));
  try {
    const data = await api('/terms', { q: searchState.q, theme: searchState.theme, limit: 100 });
    if (seq !== searchSeq) return;
    document.getElementById('count').textContent = t().results(data.total);
    document.getElementById('results').innerHTML = data.items.length
      ? data.items.map((i) => resultRow(i)).join('')
      : emptyState(t().none, t().noneHint);
  } catch {
    document.getElementById('results').innerHTML = errorState();
  }
}

async function term(slug) {
  setScreen(`<div class="skeleton" style="height:600px"></div>`);
  let d;
  try { d = await api('/terms/' + encodeURIComponent(slug)); } catch { setScreen(backBtn('#/') + emptyState(t().none, t().noneHint)); return; }
  const hero = d.slug === 'mitochondrion' ? '<img class="clay-img mito" src="/img/mito.svg" alt="">' : themeImg(d.theme.icon, 'clay-img icon');
  setScreen(`
    <div class="row between">${backBtn('#/search')}${langSwitch()}${saveBtn(d.slug)}</div>
    <div class="hero glass">${hero}
      <a class="chip lime" href="#/theme/${d.theme.slug}" style="position:absolute;left:16px;top:16px">${esc(d.theme.name)}</a>
      <button type="button" class="icon-btn neu" style="position:absolute;right:12px;top:12px" data-action="share" aria-label="${esc(t().share)}">${icon('share')}</button>
    </div>
    <div class="row between" style="align-items:flex-end;gap:12px">
      <div style="display:flex;flex-direction:column;gap:6px;min-width:0">
        <h1 class="display" style="font-size:26px;font-weight:800">${esc(d.name)}</h1>
        ${d.pronunciation ? `<span style="font-size:15px;font-weight:600;color:var(--violet-text)">${esc(d.pronunciation)}</span>` : ''}
        ${d.grammar ? `<span class="muted" style="font-size:13px">${esc(d.grammar)}</span>` : ''}
      </div>
      <button type="button" class="speak clay-lime" data-action="speak" data-text="${esc(d.name)}" aria-label="${esc(t().listen)}">${icon('speaker', 22)}</button>
    </div>
    <section class="card glass"><span class="label">${esc(t().definition)}</span><p style="margin:0;font-size:15px;line-height:1.55;font-weight:500">${esc(d.definition)}</p></section>
    ${d.facts.length ? `<section class="card neu"><span class="label">${esc(t().keyFacts)}</span>${d.facts.map((f) => `<div class="fact">${esc(f)}</div>`).join('')}</section>` : ''}
    ${d.etymology ? `<section style="display:flex;flex-direction:column;gap:6px;padding:0 4px"><span class="label">${esc(t().origin)}</span><span class="muted" style="font-size:14px;line-height:1.5">${esc(d.etymology)}</span></section>` : ''}
    ${d.related.length ? `<section style="display:flex;flex-direction:column;gap:10px;padding:0 4px"><span class="label">${esc(t().related)}</span><div class="related">${d.related.map((r) => `<a class="glass" href="#/term/${encodeURIComponent(r.slug)}">${esc(r.name)}</a>`).join('')}</div></section>` : ''}
  `, { orbList: [[150, 70, 280, '#6600FF'], [-90, 260, 220, '#A7FC00'], [220, 640, 200, '#B794FF']] });
}

async function themesList() {
  const themes = await api('/themes');
  setScreen(`
    <div class="row between"><h1 class="display">${esc(t().tabThemes)}</h1>${langSwitch()}</div>
    <div class="list">${themes.map((th) => `
      <a class="theme-card glass" href="#/theme/${th.slug}">${themeImg(th.icon)}
        <div style="flex:1;display:flex;flex-direction:column;gap:4px"><span class="display" style="font-weight:700;font-size:16px">${esc(th.name)}</span>
        <span class="muted" style="font-size:12.5px;line-height:1.4">${esc(th.description || '')}</span>
        <span class="chip" style="align-self:flex-start;margin-top:4px">${esc(t().terms(th.term_count))}</span></div>${icon('chev', 18)}</a>`).join('')}
    </div>`, { tabs: 'tabThemes', orbList: [[170, 40, 280, '#A7FC00'], [-100, 360, 240, '#6600FF']] });
}

async function themeDetail(slug) {
  const [th, data] = await Promise.all([api('/themes/' + slug), api('/terms', { theme: slug, limit: 500 })]);
  const heroImg = th.icon === 'dna' ? '<img class="clay-img" src="/img/dna-tall.svg" alt="">' : themeImg(th.icon, 'clay-img').replace('<img', '<img style="height:110px;top:24px;transform:rotate(10deg)"');
  setScreen(`
    <div class="row between">${backBtn('#/themes')}${langSwitch()}</div>
    <div class="theme-hero glass">
      <div class="text"><span class="label">${esc(t().theme)} · ${esc(t().terms(th.term_count))}</span>
        <h1 class="display" style="font-size:26px;font-weight:800">${esc(th.name)}</h1>
        <span class="muted" style="font-size:13px;line-height:1.45">${esc(th.description || '')}</span></div>
      ${heroImg}
    </div>
    <label class="search-bar neu-in">${icon('search', 19).replace('currentColor', '#6600FF')}<input id="tq" type="search" autocomplete="off" placeholder="${esc(t().searchIn)}" aria-label="${esc(t().searchIn)}"></label>
    <div id="az" class="list"></div>`,
  { tabs: 'tabThemes', orbList: [[170, 40, 280, '#A7FC00'], [-100, 260, 240, '#6600FF']] });

  const draw = (filter = '') => {
    const f = filter.trim().toLocaleLowerCase(lang);
    const items = data.items.filter((i) => !f || i.name.toLocaleLowerCase(lang).includes(f));
    if (!items.length) { document.getElementById('az').innerHTML = emptyState(t().none, t().noneHint); return; }
    let html = '', last = '';
    items.forEach((i) => {
      const L = i.name[0].toLocaleUpperCase(lang);
      if (L !== last) { html += `<span class="letter">${esc(L)}</span>`; last = L; }
      html += resultRow(i, true);
    });
    document.getElementById('az').innerHTML = html;
  };
  draw();
  document.getElementById('tq').addEventListener('input', (e) => draw(e.target.value));
}

async function savedScreen() {
  const items = saved.length ? await api('/terms/batch', { slugs: saved.join(',') }) : [];
  setScreen(`
    <div class="row between"><h1 class="display">${esc(t().savedTitle)}</h1>${langSwitch()}</div>
    ${items.length ? `<div class="muted" style="font-size:13px;font-weight:700">${esc(t().terms(items.length))}</div><div class="list">${items.map((i) => resultRow(i)).join('')}</div>`
      : emptyState(t().savedEmpty, t().savedEmptyHint, 'molecule')}`,
  { tabs: 'tabSaved', orbList: [[180, 120, 260, '#6600FF'], [-90, 480, 240, '#A7FC00']] });
}

async function statsScreen() {
  const s = await api('/stats');
  const max = Math.max(1, ...s.by_theme.map((x) => x.term_count));
  setScreen(`
    <div class="row between"><h1 class="display">${esc(t().statsTitle)}</h1>${langSwitch()}</div>
    <section class="card glass" style="align-items:flex-start">
      <span class="big-number">${s.total_terms}</span>
      <span style="font-weight:700">${esc(t().terms(s.total_terms).replace(/^\d+\s*/, ''))} ${esc(t().inDictionary)} · ${esc(t().themesCount(s.total_themes))}</span>
      <span class="muted" style="font-size:13px">${s.terms_with_full_article} ${esc(t().fullArticles)}</span>
    </section>
    <section class="card neu"><span class="label">${esc(t().byTheme)}</span>
      ${s.by_theme.map((x) => `<a href="#/theme/${x.slug}" style="display:flex;flex-direction:column;gap:6px">
        <span class="row between" style="font-size:14px;font-weight:700"><span>${esc(x.name)}</span><span style="color:var(--violet-text)">${x.term_count}</span></span>
        <span class="bar"><span style="width:${(x.term_count / max) * 100}%"></span></span></a>`).join('')}
    </section>
    <section class="card glass"><span class="label">${esc(t().byLanguage)}</span>
      ${Object.entries(s.by_language).map(([code, x]) => `<div class="row between" style="font-size:14px;font-weight:700"><span>${esc(x.name)}</span><span>${x.translated} / ${s.total_terms}</span></div>`).join('')}
    </section>`,
  { tabs: 'tabStats', orbList: [[170, 60, 260, '#A7FC00'], [-100, 420, 260, '#6600FF']] });
}

// ---------- router ----------
async function route() {
  document.documentElement.lang = lang;
  const [path, query = ''] = location.hash.replace(/^#/, '').split('?');
  const parts = path.split('/').filter(Boolean);
  const params = new URLSearchParams(query);
  try {
    if (!store.get('biolex-onboarded', false) && parts[0] !== 'term') return welcome();
    switch (parts[0]) {
      case undefined: return await home();
      case 'welcome': return welcome();
      case 'search': return await search(params);
      case 'term': return await term(decodeURIComponent(parts[1] || ''));
      case 'themes': return await themesList();
      case 'theme': return await themeDetail(parts[1]);
      case 'saved': return await savedScreen();
      case 'stats': return await statsScreen();
      default: location.hash = '#/';
    }
  } catch (err) {
    console.error(err);
    setScreen(errorState(), { tabs: 'tabHome' });
  }
}

// ---------- events ----------
document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-action]');
  if (!el) return;
  const action = el.dataset.action;
  if (action === 'lang') {
    lang = el.dataset.lang;
    store.set('biolex-lang', lang);
    const q = document.getElementById('q');
    if (q) searchState.q = q.value;
    route();
  } else if (action === 'start' || action === 'start-themes') {
    store.set('biolex-onboarded', true);
    if (action === 'start') {
      e.preventDefault();
      if (location.hash === '#/' || location.hash === '') route(); else location.hash = '#/';
    }
  } else if (action === 'filter') {
    searchState.theme = el.dataset.theme;
    document.querySelectorAll('#filters .filter').forEach((b) => {
      const on = b.dataset.theme === searchState.theme;
      b.classList.toggle('on', on); b.classList.toggle('clay-violet', on); b.setAttribute('aria-pressed', on);
    });
    runSearch();
  } else if (action === 'save') {
    const slug = el.dataset.slug;
    saved = isSaved(slug) ? saved.filter((s) => s !== slug) : [slug, ...saved];
    store.set('biolex-saved', saved);
    el.outerHTML = saveBtn(slug);
    toast(isSaved(slug) ? t().savedToast : t().removedToast);
  } else if (action === 'speak') {
    if (!('speechSynthesis' in window)) return;
    const u = new SpeechSynthesisUtterance(el.dataset.text);
    u.lang = LANGS.find((l) => l.code === lang).speech;
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  } else if (action === 'share') {
    const data = { title: 'BioLex', url: location.href };
    if (navigator.share) navigator.share(data).catch(() => {});
    else navigator.clipboard?.writeText(location.href).then(() => toast(t().copied));
  } else if (action === 'retry') {
    route();
  }
});

window.addEventListener('hashchange', route);
route();
