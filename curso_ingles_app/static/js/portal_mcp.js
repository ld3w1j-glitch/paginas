(function () {
  const root = document.querySelector('[data-portal-mcp]');
  if (!root) return;

  const toggle = root.querySelector('[data-mcp-toggle]');
  const close = root.querySelector('[data-mcp-close]');
  const panel = root.querySelector('[data-mcp-panel]');
  const form = root.querySelector('[data-mcp-form]');
  const input = root.querySelector('[data-mcp-input]');
  const messages = root.querySelector('[data-mcp-messages]');

  function getMcpEndpoint() {
    const fromTemplate = root.getAttribute('data-mcp-endpoint');
    if (fromTemplate && fromTemplate.trim()) return fromTemplate.trim();
    const path = window.location.pathname || '';
    if (path.startsWith('/curso-ingles')) return '/curso-ingles/mcp/portal';
    return '/mcp/portal';
  }

  function setOpen(open) {
    root.classList.toggle('is-open', open);
    panel.setAttribute('aria-hidden', open ? 'false' : 'true');
    if (open) setTimeout(() => input && input.focus(), 80);
  }

  function escapeHtml(text) {
    return String(text || '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function formatAnswer(text) {
    return escapeHtml(text)
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
  }

  function addMessage(kind, text, loading) {
    const item = document.createElement('div');
    item.className = 'portal-mcp-message ' + kind + (loading ? ' loading' : '');
    item.innerHTML = loading ? '<span></span><span></span><span></span>' : formatAnswer(text);
    messages.appendChild(item);
    messages.scrollTop = messages.scrollHeight;
    return item;
  }

  function collectContext() {
    const main = document.querySelector('main') || document.querySelector('.course-main-area') || document.body;
    const visibleText = (main.innerText || document.body.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 4500);
    const selectedText = String(window.getSelection ? window.getSelection() : '').replace(/\s+/g, ' ').trim().slice(0, 1500);
    return {
      page_title: document.title || '',
      path: window.location.pathname,
      url: window.location.href,
      selected_text: selectedText,
      visible_text: visibleText
    };
  }

  toggle && toggle.addEventListener('click', () => setOpen(!root.classList.contains('is-open')));
  close && close.addEventListener('click', () => setOpen(false));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') setOpen(false);
  });

  form && form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const question = (input.value || '').trim();
    if (!question) return;
    input.value = '';
    addMessage('user', question);
    const loading = addMessage('bot', '', true);

    try {
      const response = await fetch(getMcpEndpoint(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, context: collectContext() })
      });

      let data = {};
      try { data = await response.json(); } catch (_) {}

      loading.classList.remove('loading');
      if (!response.ok) {
        loading.innerHTML = formatAnswer(data.answer || 'O MCP respondeu com erro HTTP ' + response.status + '. Verifique a rota /curso-ingles/mcp/portal.');
        return;
      }
      loading.innerHTML = formatAnswer(data.answer || 'Não consegui gerar resposta agora.');
    } catch (error) {
      loading.classList.remove('loading');
      loading.innerHTML = formatAnswer('Não consegui conectar ao MCP agora. Verifique se o Flask foi reiniciado e se esta rota abre: /curso-ingles/mcp/portal.');
    }
    messages.scrollTop = messages.scrollHeight;
  });
})();
