async function save(url, data, showInline = true) {
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
    if (showInline) {
      message.textContent = 'Saved.';
      message.classList.add('success');
    }
    return result;
  } catch (error) {
    if (showInline) message.textContent = error.message;
    throw error;
  }
}

function showNotice(title, detail) {
  const dialog = document.querySelector('#notice-dialog');
  if (!dialog || typeof dialog.showModal !== 'function') {
    alert(detail);
    return;
  }
  dialog.querySelector('#notice-title').textContent = title;
  dialog.querySelector('#notice-message').textContent = detail;
  dialog.showModal();
}

document.querySelectorAll('[data-student]').forEach(form => form.addEventListener('submit', event => {
  event.preventDefault();
  save('/admin/students', {
    student_id: form.elements.student_id.value,
    name: form.elements.name.value,
    active: form.dataset.create === 'true' || form.elements.active.value === 'true',
    create: form.dataset.create === 'true'
  }).catch(() => {});
}));

const studentImport = document.querySelector('#student-import');
if (studentImport) studentImport.addEventListener('submit', async event => {
  event.preventDefault();
  const message = document.querySelector('#message');
  message.classList.remove('success');
  try {
    const response = await fetch('/admin/students/import', {
      method: 'POST',
      headers: {'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content},
      body: new FormData(studentImport)
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Import failed');
    message.textContent = `${result.imported} student accounts imported.`;
    message.classList.add('success');
    setTimeout(() => location.reload(), 700);
  } catch (error) {
    message.textContent = error.message;
  }
});

document.querySelectorAll('[data-password-reset]').forEach(button => button.addEventListener('click', async () => {
  if (!confirm(`Reset the password for ${button.dataset.passwordReset}?`)) return;
  try {
    await save('/admin/students/password-reset', {student_id: button.dataset.passwordReset});
    setTimeout(() => location.reload(), 700);
  } catch (_) {}
}));

document.querySelectorAll('[data-student-active]').forEach(button => button.addEventListener('click', async () => {
  const form = button.closest('[data-student]');
  const active = button.dataset.studentActive === 'true';
  const studentId = form.elements.student_id.value;
  const action = active ? 'activate' : 'deactivate';
  if (!confirm(`${action[0].toUpperCase() + action.slice(1)} account ${studentId}?`)) return;
  try {
    await save('/admin/students', {
      student_id: studentId,
      name: form.elements.name.value,
      active,
      create: false
    });
    setTimeout(() => location.reload(), 500);
  } catch (_) {}
}));

document.querySelectorAll('[data-student-delete]').forEach(button => button.addEventListener('click', async () => {
  const studentId = button.dataset.studentDelete;
  if (!confirm(`Delete account ${studentId}? This cannot be undone.`)) return;
  try {
    await save('/admin/students/delete', {student_id: studentId}, false);
    setTimeout(() => location.reload(), 700);
  } catch (error) {
    showNotice('Account cannot be deleted', error.message);
  }
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
    save('/admin/settings', {scope: settings.elements.scope.value, values}).catch(() => {});
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
