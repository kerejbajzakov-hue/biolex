// Browser-side copy of the FastAPI endpoints, used on GitHub Pages (no server there).
// Reads data/seed.json and answers the same paths with the same JSON shapes.
// Terms people add themselves are kept in this browser (localStorage), merged into the dictionary.

const ALPHABETS = {
  en: 'abcdefghijklmnopqrstuvwxyz',
  kk: 'аәбвгғдеёжзийкқлмнңоөпрстуұүфхһцчшщъыіьэюя',
  ru: 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
};
const LANGS = ['en', 'kk', 'ru'];
const CUSTOM_KEY = 'biolex-custom-terms';

let seedPromise;
function seed() {
  seedPromise ??= fetch('data/seed.json').then((r) => {
    if (!r.ok) throw new Error('seed ' + r.status);
    return r.json();
  });
  return seedPromise;
}

function readCustom() {
  try { return JSON.parse(localStorage.getItem(CUSTOM_KEY) || '[]'); } catch { return []; }
}
function writeCustom(list) {
  try { localStorage.setItem(CUSTOM_KEY, JSON.stringify(list)); }
  catch { throw apiError(507, 'Could not save on this device (storage is full or blocked).'); }
}

async function getData() {
  const s = await seed();
  return { ...s, terms: [...s.terms, ...readCustom()] };
}

function apiError(status, message) {
  const e = new Error(message);
  e.status = status;
  return e;
}

const norm = (s) => (s || '').toLocaleLowerCase().replace(/ё/g, 'е').trim();
// requested language → English → whatever language the term was written in
const pick = (obj, lang) => {
  if (!obj) return null;
  if (obj[lang]) return obj[lang];
  if (obj.en) return obj.en;
  const first = Object.values(obj).find((v) => v);
  return first ?? null;
};

function sortKey(lang, text) {
  const alpha = ALPHABETS[lang] || ALPHABETS.en;
  return [...text.toLocaleLowerCase()].map((c) => {
    const i = alpha.indexOf(c);
    return i >= 0 ? i : 1000 + c.codePointAt(0);
  });
}
function compareKeys(a, b) {
  for (let i = 0; i < Math.min(a.length, b.length); i++) if (a[i] !== b[i]) return a[i] - b[i];
  return a.length - b.length;
}

function themeOf(data, slug, lang) {
  const th = data.themes.find((t) => t.slug === slug) || data.themes[0];
  return { slug: th.slug, name: pick(th.name, lang), icon: th.icon };
}

function summary(data, t, lang) {
  return { slug: t.slug, name: pick(t.name, lang), short_def: pick(t.short, lang), theme: themeOf(data, t.theme, lang), custom: !!t.custom };
}

function listThemes(data, lang) {
  return data.themes.map((th) => ({
    slug: th.slug,
    icon: th.icon,
    name: pick(th.name, lang),
    description: pick(th.description, lang),
    term_count: data.terms.filter((t) => t.theme === th.slug).length,
  }));
}

function search(data, lang, q = '', theme = null, limit = 50, offset = 0) {
  const qn = norm(q);
  const rows = data.terms
    .filter((t) => !theme || t.theme === theme)
    .map((t) => ({ t, name: pick(t.name, lang), nameN: norm(pick(t.name, lang)), shortN: norm(pick(t.short, lang)) }))
    .filter((r) => !qn || r.nameN.includes(qn) || r.shortN.includes(qn));
  const level = (r) => {
    if (!qn || r.nameN.startsWith(qn)) return 0;
    if (r.nameN.split(/\s+/).some((w) => w.startsWith(qn))) return 1;
    if (r.nameN.includes(qn)) return 2;
    return 3;
  };
  rows.sort((a, b) => level(a) - level(b) || compareKeys(sortKey(lang, a.name), sortKey(lang, b.name)));
  return {
    query: q,
    theme,
    total: rows.length,
    items: rows.slice(offset, offset + limit).map((r) => summary(data, r.t, lang)),
  };
}

function detail(data, slug, lang) {
  const t = data.terms.find((x) => x.slug === slug);
  if (!t) return null;
  const shown = t.name[lang] ? lang : t.name.en ? 'en' : Object.keys(t.name)[0];
  const facts = (t.facts && (t.facts[lang] || t.facts.en || t.facts[shown])) || [];
  const bySlug = Object.fromEntries(data.terms.map((x) => [x.slug, x]));
  const def = t.definition || {};
  return {
    ...summary(data, t, lang),
    definition: def[lang] || t.short[lang] || def.en || t.short.en || def[shown] || t.short[shown],
    pronunciation: pick(t.pronunciation, lang),
    grammar: t.grammar ? t.grammar[lang] ?? null : null,
    etymology: pick(t.etymology, lang),
    facts,
    related: (t.related || []).filter((s) => bySlug[s]).map((s) => summary(data, bySlug[s], lang)),
    languages: Object.keys(t.name).sort(),
    translated: lang in t.name,
  };
}

// ---------- user terms ----------

const clean = (s, max) => String(s ?? '').trim().slice(0, max);

/** Validate a TermIn body (same rules as the server) and turn it into a stored term. */
function toStored(data, body, slug) {
  if (!data.themes.some((t) => t.slug === body.theme)) throw apiError(422, 'Unknown theme');
  const term = { slug, theme: body.theme, custom: true, name: {}, short: {}, definition: {}, pronunciation: {}, etymology: {}, facts: {} };
  for (const lang of LANGS) {
    const tr = (body.translations || {})[lang];
    if (!tr) continue;
    const name = clean(tr.name, 120), short = clean(tr.short_def, 400);
    const definition = clean(tr.definition, 4000), pron = clean(tr.pronunciation, 120), ety = clean(tr.etymology, 600);
    const facts = (tr.facts || []).map((f) => clean(f, 400)).filter(Boolean).slice(0, 20);
    if (!name && !short && !definition && !pron && !ety && !facts.length) continue;
    if (!name || !short) throw apiError(422, `${lang}: both the term and its short definition are needed`);
    term.name[lang] = name;
    term.short[lang] = short;
    if (definition) term.definition[lang] = definition;
    if (pron) term.pronunciation[lang] = pron;
    if (ety) term.etymology[lang] = ety;
    if (facts.length) term.facts[lang] = facts;
  }
  if (!Object.keys(term.name).length) throw apiError(422, 'Fill in the term and a short definition in at least one language');
  const known = new Set(data.terms.map((t) => t.slug));
  term.related = (body.related || []).filter((s) => known.has(s) && s !== slug).slice(0, 20);
  return term;
}

function source(t) {
  const translations = {};
  for (const lang of Object.keys(t.name)) {
    translations[lang] = {
      name: t.name[lang], short_def: t.short[lang],
      definition: t.definition?.[lang] ?? null, pronunciation: t.pronunciation?.[lang] ?? null,
      etymology: t.etymology?.[lang] ?? null, facts: t.facts?.[lang] ?? [],
    };
  }
  return { slug: t.slug, theme: t.theme, custom: !!t.custom, translations, related: t.related || [] };
}

function newSlug(existing) {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const base = 'my-' + String(d.getFullYear()).slice(2) + pad(d.getMonth() + 1) + pad(d.getDate()) + pad(d.getHours()) + pad(d.getMinutes()) + pad(d.getSeconds());
  let slug = base, n = 1;
  while (existing.has(slug)) slug = `${base}-${++n}`;
  return slug;
}

function dayOrdinal(d = new Date()) {
  // same number Python's date.toordinal() gives, so web and server agree on the term of the day
  return Math.floor(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 86400000) + 719163;
}

export async function localApi(path, params = {}, { method = 'GET', body = null } = {}) {
  const data = await getData();
  const lang = params.lang || 'en';
  const [, root, a, b] = path.split('/'); // "/terms/xyz/source" -> ["", "terms", "xyz", "source"]

  if (method !== 'GET') {
    if (root !== 'terms') throw apiError(405, 'Method not allowed');
    const custom = readCustom();
    if (method === 'POST' && !a) {
      const term = toStored(data, body, newSlug(new Set(data.terms.map((t) => t.slug))));
      writeCustom([...custom, term]);
      return detail({ ...data, terms: [...data.terms, term] }, term.slug, lang);
    }
    const slug = decodeURIComponent(a || '');
    const i = custom.findIndex((t) => t.slug === slug);
    if (i < 0) throw apiError(data.terms.some((t) => t.slug === slug) ? 403 : 404, 'Only your own terms can be changed');
    if (method === 'PUT') {
      custom[i] = toStored(data, body, slug);
      writeCustom(custom);
      return detail(await getData(), slug, lang);
    }
    if (method === 'DELETE') {
      custom.splice(i, 1);
      custom.forEach((t) => { t.related = (t.related || []).filter((s) => s !== slug); });
      writeCustom(custom);
      return null;
    }
    throw apiError(405, 'Method not allowed');
  }

  if (root === 'stats') {
    const themes = listThemes(data, lang);
    const byLanguage = {};
    for (const l of data.languages) {
      byLanguage[l.code] = { name: l.name, translated: data.terms.filter((t) => t.name[l.code]).length };
    }
    return {
      total_terms: data.terms.length,
      total_themes: themes.length,
      by_theme: themes.map((t) => ({ slug: t.slug, name: t.name, term_count: t.term_count })),
      by_language: byLanguage,
      terms_with_full_article: data.terms.filter((t) => t.definition && t.definition[lang]).length,
      custom_terms: readCustom().length,
    };
  }
  if (root === 'my-terms') {
    return readCustom().slice().reverse().map((t) => summary(data, t, lang));
  }
  if (root === 'themes') {
    const themes = listThemes(data, lang);
    if (!a) return themes;
    const th = themes.find((t) => t.slug === a);
    if (!th) throw apiError(404, 'Theme not found');
    return th;
  }
  if (root === 'terms') {
    if (!a) return search(data, lang, params.q || '', params.theme || null, Number(params.limit) || 50, Number(params.offset) || 0);
    if (a === 'batch') {
      const bySlug = Object.fromEntries(data.terms.map((x) => [x.slug, x]));
      return String(params.slugs || '').split(',').filter((s) => bySlug[s]).map((s) => summary(data, bySlug[s], lang));
    }
    if (a === 'today') {
      const builtIn = data.terms.filter((t) => !t.custom);
      return detail(data, builtIn[dayOrdinal() % builtIn.length].slug, lang);
    }
    const slug = decodeURIComponent(a);
    if (b === 'source') {
      const t = data.terms.find((x) => x.slug === slug);
      if (!t) throw apiError(404, 'Term not found');
      return source(t);
    }
    const d = detail(data, slug, lang);
    if (!d) throw apiError(404, 'Term not found');
    return d;
  }
  throw apiError(404, 'Not found');
}
