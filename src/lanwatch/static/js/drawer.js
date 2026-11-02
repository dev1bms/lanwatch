import { deleteDevice, updateDevice } from './api.js';
import { deviceName, formatRtt, fullTime, relTime } from './format.js';
import { bdi, esc } from './html.js';
import { deviceIcon } from './icons.js';
import { t, typeLabel } from './i18n.js';
import { el, findDevice, invalidate, setHtml, state } from './state.js';
import { presenceHtml } from './view.js';

const TYPES = ['phone', 'tablet', 'computer', 'tv', 'console', 'speaker', 'printer', 'camera', 'iot', 'server', 'router', 'unknown'];

let opener = null;
let hooks = { onChange: () => {}, onRemoved: () => {}, notify: () => {} };

export function initDrawer(callbacks) {
  hooks = { ...hooks, ...callbacks };
  el.drawerClose.addEventListener('click', closeDrawer);
  el.backdrop.addEventListener('click', closeDrawer);
  el.drawerForm.addEventListener('submit', save);
  el.drawerForm.addEventListener('click', (event) => {
    if (event.target.closest('[data-action="remove"]')) remove();
  });
  document.addEventListener('keydown', onKeydown);
}

export function openDrawer(mac, trigger) {
  const device = findDevice(mac);
  if (!device) return;
  state.openMac = mac;
  opener = trigger ?? document.activeElement;
  el.drawer.hidden = false;
  el.backdrop.hidden = false;
  document.body.style.overflow = 'hidden';
  refreshDrawer();
  renderForm(device);
  invalidate(el.list, el.ports);
  hooks.onChange();
  el.drawerClose.focus();
}

export function closeDrawer() {
  if (!state.openMac) return;
  const mac = state.openMac;
  state.openMac = null;
  el.drawer.hidden = true;
  el.backdrop.hidden = true;
  document.body.style.overflow = '';
  invalidate(el.list, el.ports);
  hooks.onChange();
  const target = opener && document.contains(opener) ? opener : el.list.querySelector(`[data-mac="${CSS.escape(mac)}"]`);
  target?.focus({ preventScroll: true });
}

export function refreshDrawer() {
  if (!state.openMac) return;
  const device = findDevice(state.openMac);
  if (!device) {
    closeDrawer();
    return;
  }
  const stateLine = device.online
    ? `<p class="state live">${esc(t('state_online'))}</p>`
    : `<p class="state">${esc(t('state_offline', { time: relTime(device.last_seen) }))}</p>`;
  setHtml(el.drawerId, `<span class="tile ${device.online ? 'is-on' : 'is-off'}">${deviceIcon(device.dev_type)}</span><div><h2 id="drawerTitle"><bdi>${esc(deviceName(device))}</bdi></h2>${stateLine}</div>`);

  const fact = (label, value, html = esc(value)) => `<dt>${esc(label)}</dt>${value ? `<dd>${html}</dd>` : `<dd class="na">${esc(t('na'))}</dd>`}`;
  const rtt = device.online && device.rtt_ms != null && !device.is_self ? formatRtt(device.rtt_ms) : '';
  const hints = [device.is_self && t('self_hint'), device.random_mac && t('random_hint')].filter(Boolean);
  setHtml(el.drawerInfo, `
    <dl class="facts">
      ${fact(t('d_ip'), device.ip, bdi(device.ip))}
      ${fact(t('d_mac'), device.mac, bdi(device.mac))}
      ${fact(t('d_vendor'), device.vendor, `<bdi>${esc(device.vendor)}</bdi>`)}
      ${fact(t('d_host'), device.hostname, bdi(device.hostname))}
      ${fact(t('d_type'), typeLabel(device.dev_type))}
      ${fact(t('d_first'), fullTime(device.first_seen))}
      ${fact(t('d_last'), device.online ? t('state_online') : fullTime(device.last_seen))}
      ${fact(t('d_rtt'), rtt, bdi(rtt))}
    </dl>
    <div class="d-presence">
      <h3>${esc(t('d_presence'))}</h3>
      <div class="presence">${presenceHtml(device.presence)}</div>
      <div class="scale"><span>${esc(t('ago_24h'))}</span><span>${esc(t('now_label'))}</span></div>
    </div>
    ${hints.map((hint) => `<p class="hint">${esc(hint)}</p>`).join('')}`);
}

export function renderForm(device = findDevice(state.openMac)) {
  if (!device) return;
  const options = [
    `<option value="auto"${device.type_locked ? '' : ' selected'}>${esc(t('type_auto', { type: typeLabel(device.dev_type) }))}</option>`,
    ...TYPES.map((type) => `<option value="${type}"${device.type_locked && device.dev_type === type ? ' selected' : ''}>${esc(typeLabel(type))}</option>`)
  ];
  el.drawerForm.innerHTML = `
    <label class="field"><span>${esc(t('f_alias'))}</span><input name="alias" maxlength="64" value="${esc(device.alias ?? '')}" placeholder="${esc(t('f_alias_ph'))}"></label>
    <label class="field"><span>${esc(t('f_type'))}</span><select name="dev_type">${options.join('')}</select></label>
    <label class="check"><input type="checkbox" name="known"${device.known ? ' checked' : ''}><span>${esc(t('f_known'))}<small>${esc(t('f_known_hint'))}</small></span></label>
    <label class="field"><span>${esc(t('f_notes'))}</span><textarea name="notes" maxlength="500">${esc(device.notes ?? '')}</textarea></label>
    <div class="form-actions">
      <button type="submit" class="btn btn-primary">${esc(t('save'))}</button>
      <button type="button" class="btn btn-danger" data-action="remove">${esc(t('remove'))}</button>
    </div>`;
}

async function save(event) {
  event.preventDefault();
  const device = findDevice(state.openMac);
  if (!device) return;
  const form = new FormData(el.drawerForm);
  const submit = el.drawerForm.querySelector('[type="submit"]');
  submit.disabled = true;
  try {
    const updated = await updateDevice(device.mac, {
      alias: String(form.get('alias') ?? ''),
      dev_type: String(form.get('dev_type') ?? 'auto'),
      known: form.get('known') === 'on',
      notes: String(form.get('notes') ?? '')
    });
    Object.assign(device, updated);
    state.data.stats.unknown = state.data.devices.filter((item) => !item.known).length;
    hooks.notify(t('saved'));
    hooks.onChange();
    renderForm(device);
  } catch (error) {
    hooks.notify(t('save_failed', { error: error.message }));
  } finally {
    submit.disabled = false;
  }
}

async function remove() {
  const device = findDevice(state.openMac);
  if (!device || !window.confirm(t('confirm_remove', { name: deviceName(device) }))) return;
  try {
    await deleteDevice(device.mac);
    state.data.devices = state.data.devices.filter((item) => item.mac !== device.mac);
    opener = null;
    closeDrawer();
    hooks.notify(t('removed'));
    hooks.onRemoved();
  } catch (error) {
    hooks.notify(t('save_failed', { error: error.message }));
  }
}

function onKeydown(event) {
  if (!state.openMac) return;
  if (event.key === 'Escape') {
    event.preventDefault();
    closeDrawer();
    return;
  }
  if (event.key !== 'Tab') return;
  const focusable = el.drawer.querySelectorAll('button, input, select, textarea, [tabindex]:not([tabindex="-1"])');
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
