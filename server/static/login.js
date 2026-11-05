const toggle = document.querySelector('.password-toggle');
if (toggle) {
  toggle.addEventListener('click', () => {
    const password = document.querySelector('#password');
    const show = password.type === 'password';
    password.type = show ? 'text' : 'password';
    toggle.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
  });
}
