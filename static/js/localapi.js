// Browser-side copy of the FastAPI endpoints, used on GitHub Pages (no server there).
// Reads data/seed.json and answers the same paths with the same JSON shapes.

const ALPHABETS = {
  en: 'abcdefghijklmnopqrstuvwxyz',
  kk: 'аәбвгғдеёжзийкқлмнңоөпрстуұүфхһцчшщъыіьэюя',
  ru: 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
};

let seedPromise;
function seed() {
  seedPromise ??= fetch('data/seed.json').then((r) => {
    if (!r.ok) throw new Error('seed ' + r.status);
    return r.json();
  });
  return seedPromise;
}

const norm = (s) => (s || '').toLocaleLowerCase().replace(/ё/g, 'е').trim();
const pick = (obj, lang) => (obj ? obj[lang] ?? obj.en ?? null : null);

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
  const th = data.themes.find((t) => t.slug === slug);
  return { slug: th.slug, name: pick(th.name, lang), icon: th.icon };
}

function summary(data, t, lang) {
  return { slug: t.slug, name: pick(t.name, lang), short_def: pick(t.short, lang), theme: themeOf(data, t.theme, lang) };
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
  const facts = (t.facts && (t.facts[lang] || t.facts.en)) || [];
  const bySlug = Object.fromEntries(data.terms.map((x) => [x.slug, x]));
  return {
    ...summary(data, t, lang),
    definition: (t.definition && t.definition[lang]) || t.short[lang] || (t.definition && t.definition.en) || t.short.en,
    pronunciation: pick(t.pronunciation, lang),
    grammar: t.grammar ? t.grammar[lang] ?? null : null,
    etymology: pick(t.etymology, lang),
    facts,
    related: (t.related || []).filter((s) => bySlug[s]).map((s) => summary(data, bySlug[s], lang)),
    languages: Object.keys(t.name).sort(),
    translated: lang in t.name,
  };
}

function dayOrdinal(d = new Date()) {
  // same number Python's date.toordinal() gives, so web and server agree on the term of the day
  return Math.floor(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 86400000) + 719163;
}

export async function localApi(path, params = {}) {
  const data = await seed();
  const lang = params.lang || 'en';
  const [, root, a] = path.split('/'); // "/terms/xyz" -> ["", "terms", "xyz"]

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
    };
  }
  if (root === 'themes') {
    const themes = listThemes(data, lang);
    if (!a) return themes;
    const th = themes.find((t) => t.slug === a);
    if (!th) throw new Error('404');
    return th;
  }
  if (root === 'terms') {
    if (!a) return search(data, lang, params.q || '', params.theme || null, Number(params.limit) || 50, Number(params.offset) || 0);
    if (a === 'batch') {
      const bySlug = Object.fromEntries(data.terms.map((x) => [x.slug, x]));
      return String(params.slugs || '').split(',').filter((s) => bySlug[s]).map((s) => summary(data, bySlug[s], lang));
    }
    if (a === 'today') return detail(data, data.terms[dayOrdinal() % data.terms.length].slug, lang);
    const d = detail(data, decodeURIComponent(a), lang);
    if (!d) throw new Error('404');
    return d;
  }
  throw new Error('404');
}
