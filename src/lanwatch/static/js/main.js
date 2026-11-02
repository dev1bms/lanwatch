import { fetchState, requestScan } from './api.js';
import { initDrawer, openDrawer, refreshDrawer, renderForm } from './drawer.js';
import { fmtNum, syncClock } from './format.js';
import { DEFAULT_LANGUAGE, LANGUAGES, isRtl, language, nextLanguage, setLanguage, t } from './i18n.js';
import { el, state, storage } from './state.js';
import { FILTERS, renderAll, renderDevices, renderFaceplate, renderFilters, renderHeader, renderNotices } from './view.js';

const POLL_MS = 5000;
const POLL_SCANNING_MS = 1500;
const POLL_HIDDEN_MS = 30000;
const TOAST_MS = 3200;

let pollTimer = null;
let toastTimer = null;
let scanRequestedByUser = false;

function toast(message) {
  el.toast.textContent = message;
  el.toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.toast.classList.remove('show'), TOAST_MS);
}

function render() {
  if (!state.data) return;
  renderAll(state.data);
  refreshDrawer();
}

function prefersDark() {
  const explicit = el.root.dataset.theme;
  return explicit ? explicit === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function applyTheme() {
  const dark = prefersDark();
  el.root.classList.toggle('is-dark', dark);
  const label = dark ? t('theme_to_light') : t('theme_to_dark');
  el.themeBtn.setAttribute('aria-label', label);
  el.themeBtn.title = label;
}

function applyLanguage() {
  el.root.lang = language();
  el.root.dir = isRtl() ? 'rtl' : 'ltr';
  document.querySelectorAll('[data-i18n]').forEach((node) => { node.textContent = t(node.dataset.i18n); });
  document.querySelectorAll('[data-i18n-placeholder]').forEach((node) => { node.placeholder = t(node.dataset.i18nPlaceholder); });
  document.querySelectorAll('[data-i18n-aria]').forEach((node) => { node.setAttribute('aria-label', t(node.dataset.i18nAria)); });
  const next = nextLanguage();
  el.langBtn.textContent = LANGUAGES[next].short;
  el.langBtn.lang = next;
  el.langBtn.setAttribute('aria-label', LANGUAGES[next].switchTo);
  el.langBtn.title = LANGUAGES[next].switchTo;
  el.sort.value = state.sort;
  state.rendered.clear();
  applyTheme();
}

function schedule() {
  clearTimeout(pollTimer);
  const delay = document.hidden ? POLL_HIDDEN_MS : state.data?.scan.scanning ? POLL_SCANNING_MS : POLL_MS;
  pollTimer = setTimeout(refresh, delay);
}

async function refresh() {
  clearTimeout(pollTimer);
  if (document.hidden) {
    schedule();
    return;
  }
  try {
    const data = await fetchState();
    const wasScanning = state.data?.scan.scanning ?? false;
    syncClock(data.now);
    state.data = data;
    state.connectionLost = false;
    if (wasScanning && !data.scan.scanning && scanRequestedByUser) {
      scanRequestedByUser = false;
      toast(t('scan_done', { n: fmtNum(data.stats.online) }));
    }
    render();
  } catch {
    state.connectionLost = true;
    renderNotices(state.data);
  }
  schedule();
}

async function startScan() {
  try {
    const { queued } = await requestScan();
    if (!queued) toast(t('scan_busy'));
    scanRequestedByUser = true;
    if (state.data) {
      state.data.scan.scanning = true;
      renderHeader(state.data);
    }
    schedule();
  } catch (error) {
    toast(t('scan_failed_toast', { error: error.message }));
  }
}

function setFilter(filter) {
  state.filter = filter in FILTERS ? filter : 'all';
  if (!state.data) return;
  renderFilters(state.data);
  renderDevices(state.data);
  renderFaceplate(state.data);
}

function moveFilterFocus(event) {
  if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
  event.preventDefault();
  const keys = Object.keys(FILTERS);
  const forward = event.key === 'ArrowDown' || (event.key === 'ArrowLeft') === isRtl();
  const next = keys[(keys.indexOf(state.filter) + (forward ? 1 : keys.length - 1)) % keys.length];
  setFilter(next);
  el.filters.querySelector(`[data-filter="${next}"]`)?.focus();
}

function bindEvents() {
  el.scanBtn.addEventListener('click', startScan);

  el.themeBtn.addEventListener('click', () => {
    const next = prefersDark() ? 'light' : 'dark';
    el.root.dataset.theme = next;
    storage.set('lw.theme', next);
    applyTheme();
  });
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyTheme);

  el.langBtn.addEventListener('click', async () => {
    storage.set('lw.lang', await setLanguage(nextLanguage()));
    applyLanguage();
    render();
    renderForm();
  });

  el.search.addEventListener('input', () => {
    state.query = el.search.value;
    if (state.data) renderDevices(state.data);
  });
  el.sort.addEventListener('change', () => {
    state.sort = el.sort.value;
    storage.set('lw.sort', state.sort);
    if (state.data) renderDevices(state.data);
  });

  el.filters.addEventListener('click', (event) => {
    const button = event.target.closest('[data-filter]');
    if (button) setFilter(button.dataset.filter);
  });
  el.filters.addEventListener('keydown', moveFilterFocus);
  document.querySelectorAll('.fp-stat').forEach((button) => button.addEventListener('click', () => setFilter(button.dataset.filter)));

  el.list.addEventListener('click', (event) => {
    const action = event.target.closest('[data-action]')?.dataset.action;
    if (action === 'scan') startScan();
    if (action === 'clear') {
      state.query = '';
      el.search.value = '';
      setFilter('all');
    }
    const row = !action && event.target.closest('.row');
    if (row) openDrawer(row.dataset.mac, row);
  });

  for (const container of [el.ports, el.events]) {
    container.addEventListener('click', (event) => {
      const target = event.target.closest('[data-mac]');
      if (target) openDrawer(target.dataset.mac, target);
    });
  }

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) refresh();
  });
}

async function start() {
  await setLanguage(storage.get('lw.lang', DEFAULT_LANGUAGE));
  initDrawer({ onChange: render, onRemoved: refresh, notify: toast });
  bindEvents();
  applyLanguage();
  refresh();
}

start();
