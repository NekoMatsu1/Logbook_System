async function save(url, data) {
  const message = document.querySelector('#message');
  try {
    const response = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name="csrf-token"]').content}, body:JSON.stringify(data)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Request failed');
    message.textContent = 'Saved.';
  } catch (error) { message.textContent = error.message; }
}
document.querySelectorAll('[data-student]').forEach(form => form.addEventListener('submit', event => {
  event.preventDefault();
  save('/admin/students', {student_id:form.elements.student_id.value,name:form.elements.name.value,active:form.dataset.create==='true'||form.elements.active.checked,create:form.dataset.create==='true'});
}));
const settings = document.querySelector('#settings');
if (settings) {
  settings.elements.scope.addEventListener('change', () => {
    if (settings.elements.scope.value !== '*') Array.from(settings.elements).forEach(el => { if(el.name && el.name !== 'scope') el.value=''; });
    else location.reload();
  });
  settings.addEventListener('submit', event => {
    event.preventDefault(); const values = {};
    for (const [key, value] of new FormData(settings)) {
      if (key === 'scope' || value === '') continue;
      values[key] = key.startsWith('auto_') ? value === 'true' : Number(value);
    }
    save('/admin/settings',{scope:settings.elements.scope.value,values});
  });
}
if (location.pathname === '/admin/overview') setTimeout(() => location.reload(), 10000);
