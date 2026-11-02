const ENTITIES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ENTITIES[c]);
export const bdi = (text) => `<bdi class="mono">${esc(text)}</bdi>`;
export const code = (text) => `<code>${esc(text)}</code>`;
