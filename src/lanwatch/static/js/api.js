async function request(path, { method = 'GET', body } = {}) {
  const response = await fetch(path, {
    method,
    credentials: 'same-origin',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.status === 204 ? null : response.json();
}

async function errorMessage(response) {
  const body = await response.json().catch(() => null);
  const detail = body?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join('; ');
  return `${response.status} ${response.statusText}`;
}

const devicePath = (mac) => `/api/devices/${encodeURIComponent(mac)}`;

export const fetchState = () => request('/api/state');
export const requestScan = () => request('/api/scan', { method: 'POST' });
export const updateDevice = (mac, changes) => request(devicePath(mac), { method: 'PATCH', body: changes });
export const deleteDevice = (mac) => request(devicePath(mac), { method: 'DELETE' });
