const $ = (selector) => document.querySelector(selector);

export const storage = {
  get(key, fallback) {
    try {
      return localStorage.getItem(key) ?? fallback;
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, value);
      return true;
    } catch {
      return false;
    }
  }
};

export const state = {
  data: null,
  filter: 'all',
  sort: storage.get('lw.sort', 'ip'),
  query: '',
  openMac: null,
  connectionLost: false,
  rendered: new Map()
};

export const findDevice = (mac) => state.data?.devices.find((device) => device.mac === mac) ?? null;

export function setHtml(node, html) {
  if (state.rendered.get(node) === html) return false;
  state.rendered.set(node, html);
  node.innerHTML = html;
  return true;
}

export const invalidate = (...nodes) => nodes.forEach((node) => state.rendered.delete(node));

export const el = {
  root: document.documentElement,
  netline: $('#netline'),
  scanBtn: $('#scanBtn'),
  scanLabel: $('#scanLabel'),
  themeBtn: $('#themeBtn'),
  langBtn: $('#langBtn'),
  faceplate: $('#faceplate'),
  fpNet: $('#fpNet'),
  ports: $('#ports'),
  onlineCount: $('#onlineCount'),
  statTotal: $('#statTotal'),
  statNew: $('#statNew'),
  statOffline: $('#statOffline'),
  fpScan: $('#fpScan'),
  notices: $('#notices'),
  search: $('#search'),
  filters: $('#filters'),
  sort: $('#sort'),
  list: $('#deviceList'),
  events: $('#events'),
  backdrop: $('#backdrop'),
  drawer: $('#drawer'),
  drawerId: $('#drawerId'),
  drawerInfo: $('#drawerInfo'),
  drawerForm: $('#drawerForm'),
  drawerClose: $('#drawerClose'),
  toast: $('#toast')
};
