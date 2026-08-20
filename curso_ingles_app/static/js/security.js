(function () {
  const meta = document.querySelector('meta[name="csrf-token"]');
  const token = meta ? meta.content : '';
  window.portalCsrfToken = token;

  document.querySelectorAll('form').forEach((form) => {
    const method = String(form.getAttribute('method') || 'GET').toUpperCase();
    if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) return;
    if (form.querySelector('input[name="_csrf_token"]')) return;
    const hidden = document.createElement('input');
    hidden.type = 'hidden';
    hidden.name = '_csrf_token';
    hidden.value = token;
    form.appendChild(hidden);
  });

  const originalFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    init = init ? Object.assign({}, init) : {};
    const requestMethod = String(init.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
    const unsafe = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(requestMethod);
    if (unsafe && token) {
      let sameOrigin = true;
      try {
        const rawUrl = typeof input === 'string' ? input : input.url;
        const parsed = new URL(rawUrl, window.location.href);
        sameOrigin = parsed.origin === window.location.origin;
      } catch (_) {}
      if (sameOrigin) {
        const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
        if (!headers.has('X-CSRF-Token')) headers.set('X-CSRF-Token', token);
        init.headers = headers;
      }
    }
    return originalFetch(input, init);
  };
})();
