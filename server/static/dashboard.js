async function save(url, data) {
  const message = document.querySelector('#message');
  message.classList.remove('success');
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content},
      body: JSON.stringify(data)
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Request failed');
    message.textContent = 'Saved.';
    message.classList.add('success');
  } catch (error) {
    message.textContent = error.message;
  }
}

document.querySelectorAll('[data-student]').forEach(form => form.addEventListener('submit', event => {
  event.preventDefault();
  save('/admin/students', {
    student_id: form.elements.student_id.value,
    name: form.elements.name.value,
    active: form.dataset.create === 'true' || form.elements.active.checked,
    create: form.dataset.create === 'true'
  });
}));

const settings = document.querySelector('#settings');
if (settings) {
  settings.elements.scope.addEventListener('change', () => {
    if (settings.elements.scope.value !== '*') {
      Array.from(settings.elements).forEach(element => {
        if (element.name && element.name !== 'scope') element.value = '';
      });
    } else {
      location.reload();
    }
  });
  settings.addEventListener('submit', event => {
    event.preventDefault();
    const values = {};
    for (const [key, value] of new FormData(settings)) {
      if (key === 'scope' || value === '') continue;
      values[key] = key.startsWith('auto_') ? value === 'true' : Number(value);
    }
    save('/admin/settings', {scope: settings.elements.scope.value, values});
  });
}

if (location.pathname === '/admin/overview') {
  const status = document.querySelector('#monitor-status');
  async function refreshOverview() {
    if (document.hidden) {
      setTimeout(refreshOverview, 10000);
      return;
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch('/admin/overview', {cache: 'no-store', signal: controller.signal});
      if (response.status === 401 || response.status === 403) {
        location.assign('/auth/login');
        return;
      }
      if (!response.ok) throw new Error('Monitoring unavailable');
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const cards = page.querySelector('.cards');
      const table = page.querySelector('[data-overview-table]');
      if (!cards || !table) throw new Error('Monitoring unavailable');
      document.querySelector('.cards').replaceWith(cards);
      document.querySelector('[data-overview-table]').replaceWith(table);
      status.textContent = 'Updated ' + new Date().toLocaleTimeString() + ' · Checks every 10 seconds.';
    } catch (error) {
      status.textContent = 'Connection lost. Showing the last received data. Retrying automatically.';
    } finally {
      clearTimeout(timeout);
      setTimeout(refreshOverview, 10000);
    }
  }
  setTimeout(refreshOverview, 10000);
}
