import { esc } from './html.js';

export const DEFAULT_LANGUAGE = 'en';

export const LANGUAGES = {
  en: { short: 'EN', switchTo: 'Switch to English', dir: 'ltr', locale: 'en-GB' },
  ar: { short: 'ع', switchTo: 'التبديل إلى العربية', dir: 'rtl', locale: 'ar-u-nu-latn' }
};

const catalogs = new Map();
let current = DEFAULT_LANGUAGE;

async function loadCatalog(lang) {
  if (!catalogs.has(lang)) {
    const response = await fetch(`/static/locales/${lang}.json`, { credentials: 'same-origin' });
    if (!response.ok) throw new Error(`No translations for "${lang}"`);
    catalogs.set(lang, await response.json());
  }
  return catalogs.get(lang);
}

export const supported = (lang) => Object.hasOwn(LANGUAGES, lang);

export async function setLanguage(lang) {
  const next = supported(lang) ? lang : DEFAULT_LANGUAGE;
  await Promise.all([loadCatalog(DEFAULT_LANGUAGE), loadCatalog(next)]);
  current = next;
  return current;
}

export const language = () => current;
export const isRtl = () => LANGUAGES[current].dir === 'rtl';
export const locale = () => LANGUAGES[current].locale;

export function nextLanguage() {
  const codes = Object.keys(LANGUAGES);
  return codes[(codes.indexOf(current) + 1) % codes.length];
}

const lookup = (catalog, key) => key.split('.').reduce((node, part) => node?.[part], catalog);

function template(key) {
  const value = lookup(catalogs.get(current), key) ?? lookup(catalogs.get(DEFAULT_LANGUAGE), key);
  return typeof value === 'string' ? value : key;
}

export function t(key, params = {}) {
  return template(key).replace(/\{(\w+)\}/g, (_, name) => String(params[name] ?? ''));
}

export function th(key, htmlParams = {}) {
  return esc(template(key)).replace(/\{(\w+)\}/g, (_, name) => htmlParams[name] ?? '');
}

export function typeLabel(type) {
  const key = `types.${type}`;
  const label = t(key);
  return label === key ? t('types.unknown') : label;
}
