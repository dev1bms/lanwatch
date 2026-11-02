import { deviceName, deviceSubtitle, eventName, fmtNum, formatRtt, fullTime, ipKey, relTime } from './format.js';
import { bdi, code, esc } from './html.js';
import { ALERT_ICON, CHECK_ICON, deviceIcon } from './icons.js';
import { locale, t, th, typeLabel } from './i18n.js';
import { el, setHtml, state } from './state.js';

const PORTS_PER_GROUP = 8;

export const FILTERS = {
  all: () => true,
  online: (device) => device.online,
  offline: (device) => !device.online,
  new: (device) => device.is_new,
  unknown: (device) => !device.known
};

const SORTERS = {
  ip: (a, b) => ipKey(a.ip) - ipKey(b.ip),
  name: (a, b, collator) => collator.compare(deviceName(a), deviceName(b)),
  seen: (a, b) => (b.online - a.online) || (b.last_seen - a.last_seen),
  vendor: (a, b, collator) => collator.compare(a.vendor || '￿', b.vendor || '￿') || ipKey(a.ip) - ipKey(b.ip)
};

function visibleDevices(devices) {
  const query = state.query.trim().toLowerCase();
  const matches = (device) => [deviceName(device), device.ip, device.mac, device.vendor, device.hostname, device.notes, typeLabel(device.dev_type)]
    .some((value) => value && String(value).toLowerCase().includes(query));
  const collator = new Intl.Collator(locale(), { sensitivity: 'base', numeric: true });
  const sorter = SORTERS[state.sort] ?? SORTERS.ip;
  return devices
    .filter(FILTERS[state.filter] ?? FILTERS.all)
    .filter((device) => !query || matches(device))
    .sort((a, b) => sorter(a, b, collator));
}

const statusLabel = (device) => (device.online ? t('status_online') : t('offline'));
export const presenceHtml = (presence) => presence.map((mark) => `<i class="${mark === 1 ? 'on' : mark === 0 ? '' : 'nodata'}"></i>`).join('');

export function renderHeader(data) {
  const { interface: iface, subnets } = data.network;
  const subnet = subnets.join(', ');
  let line = esc(t('net_none'));
  if (subnet) {
    line = iface ? th('net_line', { subnet: bdi(subnet), iface: bdi(iface) }) : th('net_line_short', { subnet: bdi(subnet) });
  }
  if (data.demo) line = `<span>${line}</span><span class="demo-tag">${esc(t('demo_tag'))}</span>`;
  setHtml(el.netline, line);

  const { scanning } = data.scan;
  el.scanBtn.disabled = scanning;
  el.scanBtn.classList.toggle('is-scanning', scanning);
  el.scanLabel.textContent = scanning ? t('scanning') : t('scan_now');
  el.faceplate.classList.toggle('scanning', scanning);
}

function portHtml(device, index, multiNet) {
  const octets = device.ip.split('.');
  const label = multiNet ? octets.slice(2).join('.') : octets[3];
  const classes = ['port', device.online ? 'on' : 'off', device.is_new && 'new', state.openMac === device.mac && 'active'].filter(Boolean).join(' ');
  const title = `${deviceName(device)}: ${device.ip}, ${statusLabel(device)}`;
  return `<button type="button" role="listitem" class="${classes}" data-mac="${esc(device.mac)}" style="--i:${index}" title="${esc(title)}" aria-label="${esc(title)}"><span class="led"></span><span class="num">${esc(label)}</span></button>`;
}

export function renderFaceplate(data) {
  el.fpNet.textContent = data.network.subnets.join('  ');
  const devices = [...data.devices].sort(SORTERS.ip);
  const multiNet = data.network.subnets.length > 1;
  const groups = [];
  devices.forEach((device, index) => {
    (groups[Math.floor(index / PORTS_PER_GROUP)] ??= []).push(portHtml(device, index, multiNet));
  });
  const html = groups.length
    ? groups.map((group) => `<div class="port-group">${group.join('')}</div>`).join('')
    : `<p class="ports-empty">${esc(t('ports_empty'))}</p>`;

  if (setHtml(el.ports, html) && devices.length && !el.ports.dataset.powered) {
    el.ports.dataset.powered = 'true';
    el.ports.classList.add('power-on');
    setTimeout(() => el.ports.classList.remove('power-on'), 600 + devices.length * 22);
  }

  const { stats, scan } = data;
  el.onlineCount.textContent = fmtNum(stats.online);
  el.statTotal.textContent = fmtNum(stats.total);
  el.statNew.textContent = fmtNum(stats.new);
  el.statOffline.textContent = fmtNum(stats.offline);
  document.querySelectorAll('.fp-stat').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.filter === state.filter)));

  const last = scan.last;
  el.fpScan.classList.toggle('error', Boolean(last?.error));
  el.fpScan.textContent = last
    ? t('last_scan', { time: relTime(last.started + last.duration), method: last.method ? t(`method_${last.method}`) : '' })
    : t('never_scanned');
  el.fpScan.title = last ? fullTime(last.started) : '';
}

function noticeHtml({ code: noticeCode, params }) {
  switch (noticeCode) {
    case 'net_narrowed': return th('n_net_narrowed', { detected: bdi(params.detected), scanned: bdi(params.scanned), var: code('LW_SUBNETS') });
    case 'net_undetected': return th('n_net_undetected', { var1: code('LW_INTERFACE'), var2: code('LW_SUBNETS') });
    case 'subnet_invalid': return th('n_subnet_invalid', { subnet: bdi(params.subnet) });
    case 'subnet_too_large': return th('n_subnet_too_large', { subnet: bdi(params.subnet) });
    case 'arp_no_permission': return th('n_arp_no_permission', { cap: code('NET_RAW'), mode: code('network_mode: host'), capadd: code('cap_add: [NET_RAW]') });
    default: return esc(noticeCode);
  }
}

const notice = (html, kind = '') => `<div class="notice ${kind}">${ALERT_ICON}<p>${html}</p></div>`;

export function renderNotices(data) {
  const items = data ? data.notices.map((item) => notice(noticeHtml(item))) : [];
  if (data?.scan.error) items.unshift(notice(th('n_scan_error', { error: code(data.scan.error) }), 'error'));
  if (state.connectionLost) items.unshift(notice(esc(t('conn_lost')), 'error'));
  setHtml(el.notices, items.join(''));
}

export function renderFilters(data) {
  const html = Object.entries(FILTERS).map(([key, predicate]) => {
    const checked = state.filter === key;
    const count = data.devices.filter(predicate).length;
    return `<button type="button" class="seg" role="radio" aria-checked="${checked}" tabindex="${checked ? 0 : -1}" data-filter="${key}">${esc(t(`f_${key}`))}<span class="count">${fmtNum(count)}</span></button>`;
  }).join('');
  setHtml(el.filters, html);
}

function badgesHtml(device) {
  const badges = [
    device.is_new && ['new', t('badge_new')],
    device.is_gateway && ['', t('badge_gateway')],
    device.is_self && ['', t('badge_self')],
    device.random_mac && ['', t('badge_random')]
  ].filter(Boolean);
  return badges.length
    ? `<span class="badges">${badges.map(([kind, text]) => `<span class="badge ${kind}">${esc(text)}</span>`).join('')}</span>`
    : '';
}

function rowHtml(device) {
  const name = deviceName(device);
  const classes = ['row', device.online ? 'is-on' : 'is-off', device.is_new && 'is-new', state.openMac === device.mac && 'selected'].filter(Boolean).join(' ');
  const rtt = device.rtt_ms != null && !device.is_self ? `<span class="rtt">${bdi(formatRtt(device.rtt_ms))}</span>` : '';
  const seen = device.online ? `<span class="live">${esc(t('status_online'))}</span>${rtt}` : `<span>${esc(relTime(device.last_seen))}</span>`;
  return `<button type="button" class="${classes}" data-mac="${esc(device.mac)}" aria-label="${esc(`${name}, ${device.ip}, ${statusLabel(device)}`)}">
    <span class="tile" title="${esc(typeLabel(device.dev_type))}">${deviceIcon(device.dev_type)}<span class="status"></span></span>
    <span class="cell who"><span class="name"><bdi class="txt">${esc(name)}</bdi>${device.known ? CHECK_ICON : ''}${badgesHtml(device)}</span><span class="sub" dir="auto">${esc(deviceSubtitle(device))}</span></span>
    <span class="cell addr"><bdi class="mono ip">${esc(device.ip)}</bdi><bdi class="mono mac">${esc(device.mac)}</bdi></span>
    <span class="presence" title="${esc(t('col_presence'))}">${presenceHtml(device.presence)}</span>
    <span class="seen">${seen}</span>
  </button>`;
}

export function renderDevices(data) {
  const devices = visibleDevices(data.devices);
  let html;
  if (!data.devices.length) {
    html = `<div class="empty"><h3>${esc(t('empty_title'))}</h3><p>${esc(t('empty_body', { n: data.scan.interval }))}</p><button type="button" class="btn btn-primary" data-action="scan">${esc(t('scan_now'))}</button></div>`;
  } else if (!devices.length) {
    html = `<div class="empty"><p>${esc(t('no_match'))}</p><button type="button" class="btn btn-ghost" data-action="clear">${esc(t('clear_filters'))}</button></div>`;
  } else {
    html = devices.map(rowHtml).join('');
  }

  const focused = el.list.contains(document.activeElement) ? document.activeElement.dataset.mac : null;
  if (setHtml(el.list, html) && focused) {
    el.list.querySelector(`[data-mac="${CSS.escape(focused)}"]`)?.focus({ preventScroll: true });
  }
}

export function renderEvents(data) {
  const known = new Set(data.devices.map((device) => device.mac));
  const html = data.events.length
    ? data.events.map((event) => {
      const text = th(`ev_${event.kind}`, { name: `<b><bdi>${esc(eventName(event))}</bdi></b>`, ip: bdi(event.ip), old: bdi(event.detail) });
      const time = `<time class="when" datetime="${new Date(event.ts * 1000).toISOString()}" title="${esc(fullTime(event.ts))}">${esc(relTime(event.ts))}</time>`;
      const inner = `<span class="mark"></span><span>${text}</span>${time}`;
      const body = known.has(event.mac) ? `<button type="button" data-mac="${esc(event.mac)}">${inner}</button>` : inner;
      return `<li class="ev ${esc(event.kind)}">${body}</li>`;
    }).join('')
    : `<li class="ev-empty">${esc(t('no_events'))}</li>`;
  setHtml(el.events, html);
}

export function renderAll(data) {
  renderHeader(data);
  renderFaceplate(data);
  renderNotices(data);
  renderFilters(data);
  renderDevices(data);
  renderEvents(data);
}

