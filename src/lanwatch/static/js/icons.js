const PATHS = {
  phone: '<rect x="7" y="2.5" width="10" height="19" rx="2.2"/><path d="M11 18.5h2"/>',
  tablet: '<rect x="4.5" y="2.5" width="15" height="19" rx="2.2"/><path d="M11 18.5h2"/>',
  computer: '<rect x="4" y="4.5" width="16" height="11" rx="1.6"/><path d="M2 19.5h20"/>',
  tv: '<rect x="2.5" y="4" width="19" height="13" rx="1.6"/><path d="M8 21h8M12 17v4"/>',
  console: '<path d="M7 8h10a4.5 4.5 0 0 1 4.4 5.4l-.8 3.6a1.9 1.9 0 0 1-3.3.8L15.5 16h-7l-1.8 1.8a1.9 1.9 0 0 1-3.3-.8l-.8-3.6A4.5 4.5 0 0 1 7 8z"/><path d="M7.5 12h3M9 10.5v3M15.5 11.5h.01M17.5 12.5h.01"/>',
  speaker: '<rect x="6" y="2.5" width="12" height="19" rx="2.2"/><circle cx="12" cy="14" r="3.5"/><path d="M12 6.5h.01"/>',
  printer: '<path d="M7 8V3.5h10V8"/><rect x="3" y="8" width="18" height="8.5" rx="1.6"/><path d="M7 13.5h10v7H7z"/>',
  camera: '<path d="M3 8h3.2l1.6-2.5h8.4L17.8 8H21v11H3z"/><circle cx="12" cy="13.3" r="3.4"/>',
  iot: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.6 10.8c.7.5 1.1 1.3 1.1 2.1v.1h5v-.1c0-.8.4-1.6 1.1-2.1A6 6 0 0 0 12 3z"/>',
  server: '<rect x="3" y="3.5" width="18" height="7" rx="1.6"/><rect x="3" y="13.5" width="18" height="7" rx="1.6"/><path d="M7 7h.01M7 17h.01"/>',
  router: '<rect x="2.5" y="13" width="19" height="7" rx="1.6"/><path d="M6.5 16.5h.01M10 16.5h.01"/><path d="M8.5 9.6a5 5 0 0 1 7 0M6 7a8.5 8.5 0 0 1 12 0"/>',
  unknown: '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.4a2.5 2.5 0 1 1 3.6 2.3c-.7.3-1.2 1-1.2 1.8v.5M12 17h.01"/>'
};

export const deviceIcon = (type) => `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">${PATHS[type] ?? PATHS.unknown}</svg>`;

export const CHECK_ICON = '<svg class="known-mark" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>';

export const ALERT_ICON = '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5 2.5 20h19z"/><path d="M12 10v4.5M12 17.3h.01"/></svg>';
