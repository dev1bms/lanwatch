import { isRtl, locale, t, typeLabel } from './i18n.js';

let clockOffset = 0;

export const syncClock = (serverNow) => { clockOffset = serverNow - Date.now() / 1000; };
export const serverNow = () => Date.now() / 1000 + clockOffset;
export const fmtNum = (n) => new Intl.NumberFormat(locale()).format(n);
export const ipKey = (ip) => (ip || '').split('.').reduce((acc, octet) => acc * 256 + (Number(octet) || 0), 0);

export function relTime(ts) {
  if (!ts) return '';
  const secs = Math.max(0, Math.round(serverNow() - ts));
  if (secs < 10) return t('just_now');
  const rtf = new Intl.RelativeTimeFormat(locale(), { numeric: 'auto' });
  if (secs < 60) return rtf.format(-secs, 'second');
  if (secs < 3600) return rtf.format(-Math.round(secs / 60), 'minute');
  if (secs < 86400) return rtf.format(-Math.round(secs / 3600), 'hour');
  return rtf.format(-Math.round(secs / 86400), 'day');
}

export function fullTime(ts) {
  if (!ts) return '';
  return new Intl.DateTimeFormat(locale(), { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(ts * 1000));
}

export function shortHost(host) {
  if (!host || /^\d{1,3}(\.\d{1,3}){3}$/.test(host)) return '';
  return host.replace(/\.$/, '').split('.')[0];
}

export function deviceName(device) {
  return device.alias || shortHost(device.hostname) || device.vendor || t('unknown_device');
}

export function deviceSubtitle(device) {
  const parts = [];
  const host = shortHost(device.hostname);
  if (device.alias && host) parts.push(host);
  if (device.vendor && deviceName(device) !== device.vendor) parts.push(device.vendor);
  if (!parts.length) parts.push(typeLabel(device.dev_type));
  return parts.join(isRtl() ? '، ' : ', ');
}

export function eventName(event) {
  return event.alias || shortHost(event.hostname) || event.vendor || event.mac;
}

export const formatRtt = (ms) => `${ms.toFixed(1)} ms`;
