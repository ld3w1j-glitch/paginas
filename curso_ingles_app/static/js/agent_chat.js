(function(){
  const form = document.getElementById('agentChatForm');
  const input = document.getElementById('agentMessageInput');
  const messages = document.getElementById('agentMessages');
  const useContext = document.getElementById('agentUsePageContext');
  const allowFiles = document.getElementById('agentAllowFiles');
  const list = document.getElementById('agentConversationList');
  const newBtn = document.getElementById('newConversationBtn');
  const deleteAllBtn = document.getElementById('deleteAllConversationsBtn');
  let history = [];
  let conversationId = null;
  let pendingQuestion = '';

  function escapeHtml(value){
    return String(value || '').replace(/[&<>\"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[ch]));
  }

  function formatAnswer(text){
    let safe = escapeHtml(text || 'Sem resposta.');
    safe = safe.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    safe = safe.replace(/`([^`]+)`/g, '<code>$1</code>');
    safe = safe.replace(/\n/g, '<br>');
    return safe;
  }

  function addMessage(role, text, loading, extra, stage){
    const node = document.createElement('article');
    node.className = 'agent-message ' + (role === 'user' ? 'user' : 'bot') + (loading ? ' loading' : '') + (stage ? ' stage-' + stage : '');
    if(loading){
      node.innerHTML = '<strong>Agente analisando</strong><p><span></span><span></span><span></span></p>';
    }else{
      const title = role === 'user' ? 'Você' : (stage === 'plan' ? 'Plano do Agente' : (stage === 'rethink' ? 'Plano repensado' : 'Agente do Portal'));
      node.innerHTML = '<strong>' + title + '</strong><p>' + formatAnswer(text) + '</p>';
      if(extra){ node.insertAdjacentHTML('beforeend', extra); }
    }
    messages.appendChild(node);
    messages.scrollTop = messages.scrollHeight;
    return node;
  }

  function collectPageContext(){
    if(!useContext || !useContext.checked){ return { history }; }
    const clone = document.body.cloneNode(true);
    clone.querySelectorAll('script, style, .agent-chat-card, .portal-mcp, .course-sidebar').forEach(el => el.remove());
    const visibleText = (clone.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 5000);
    return {
      page_title: document.title || '',
      path: location.pathname,
      url: location.href,
      selected_text: String(window.getSelection ? window.getSelection() : '').slice(0, 1500),
      page_context: visibleText,
      history: history.slice(-12)
    };
  }

  function actionButtons(question){
    return '<div class="agent-decision-box">' +
      '<button class="btn btn-secondary" type="button" data-agent-rethink>Repensar antes</button>' +
      '<button class="btn btn-primary" type="button" data-agent-execute>Aprovar e executar</button>' +
      '</div>';
  }

  async function refreshConversations(){
    if(!list) return;
    try{
      const res = await fetch('/curso-ingles/agent-chat/conversations');
      const data = await res.json();
      const convs = data.conversations || [];
      if(!convs.length){
        list.innerHTML = '<span class="muted-note">Nenhuma conversa salva ainda.</span>';
        if(deleteAllBtn) deleteAllBtn.disabled = true;
        return;
      }
      if(deleteAllBtn) deleteAllBtn.disabled = false;
      list.innerHTML = convs.map(c =>
        '<div class="agent-history-row ' + (c.id === conversationId ? 'active' : '') + '">' +
          '<button type="button" class="agent-history-item" data-conversation-id="' + c.id + '">' +
            '<strong>' + escapeHtml(c.title) + '</strong><small>' + escapeHtml(c.updated_at) + '</small>' +
          '</button>' +
          '<button type="button" class="agent-history-delete" title="Excluir conversa" aria-label="Excluir conversa" data-delete-conversation-id="' + c.id + '">×</button>' +
        '</div>'
      ).join('');
    }catch(e){
      list.innerHTML = '<span class="muted-note">Não consegui carregar o histórico.</span>';
    }
  }

  function resetMessages(){
    history = [];
    pendingQuestion = '';
    messages.innerHTML = '<article class="agent-message bot"><strong>Agente do Portal</strong><p>Nova conversa iniciada. Envie um pedido para eu montar um plano antes de executar.</p></article>';
  }

  async function deleteConversation(id){
    if(!id) return;
    const ok = confirm('Deseja excluir esta conversa salva? Essa ação não poderá ser desfeita.');
    if(!ok) return;
    try{
      const res = await fetch('/curso-ingles/agent-chat/conversations/' + id, { method: 'DELETE' });
      const data = await res.json().catch(() => ({}));
      if(!res.ok || !data.ok){ throw new Error('Falha ao excluir'); }
      if(String(conversationId) === String(id)){
        conversationId = null;
        resetMessages();
      }
      refreshConversations();
    }catch(e){
      addMessage('bot', 'Não consegui excluir essa conversa agora. Recarregue a página e tente novamente.');
    }
  }

  async function deleteAllConversations(){
    const ok = confirm('Deseja excluir TODAS as conversas salvas deste usuário? Essa ação não poderá ser desfeita.');
    if(!ok) return;
    try{
      const res = await fetch('/curso-ingles/agent-chat/conversations', { method: 'DELETE' });
      const data = await res.json().catch(() => ({}));
      if(!res.ok || !data.ok){ throw new Error('Falha ao excluir tudo'); }
      conversationId = null;
      resetMessages();
      refreshConversations();
    }catch(e){
      addMessage('bot', 'Não consegui excluir todas as conversas agora. Recarregue a página e tente novamente.');
    }
  }

  async function loadConversation(id){
    try{
      const res = await fetch('/curso-ingles/agent-chat/conversations/' + id);
      const data = await res.json();
      if(!data.ok) return;
      conversationId = data.conversation.id;
      history = [];
      messages.innerHTML = '';
      (data.conversation.messages || []).forEach(msg => {
        const role = msg.role === 'user' ? 'user' : 'agent';
        addMessage(role === 'user' ? 'user' : 'bot', msg.content, false, '', msg.stage);
        history.push({role: role === 'user' ? 'usuário' : 'agente', content: msg.content});
      });
      if(!messages.children.length){ resetMessages(); }
      refreshConversations();
    }catch(e){
      addMessage('bot', 'Não consegui abrir essa conversa agora.');
    }
  }

  async function sendMessage(text, stage){
    const isPlan = stage === 'plan';
    if(isPlan){
      pendingQuestion = text;
      addMessage('user', text);
      history.push({role: 'usuário', content: text});
    }
    const loading = addMessage('bot', '', true);
    try{
      const response = await fetch('/curso-ingles/agent-chat/api', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          message: text,
          stage: stage || 'plan',
          conversation_id: conversationId,
          context: collectPageContext(),
          allow_files: !!(allowFiles && allowFiles.checked)
        })
      });
      const data = await response.json().catch(() => ({}));
      loading.remove();
      conversationId = data.conversation_id || conversationId;
      const answer = data.answer || 'Não consegui obter resposta do agente agora.';
      let extra = '';
      if(Array.isArray(data.agent_chain) && data.agent_chain.length){
        const chain = data.agent_chain.map(agent =>
          '<li><strong>' + escapeHtml(agent.name) + '</strong><span>' + escapeHtml(agent.mission) + '</span></li>'
        ).join('');
        extra += '<div class="agent-chain-box"><strong>Equipe chamada nesta etapa</strong><ol>' + chain + '</ol>' + (data.next_agent ? '<small>Próximo responsável sugerido: ' + escapeHtml(data.next_agent) + '</small>' : '') + '</div>';
      }
      if(data.stage === 'plan' || data.stage === 'rethink'){
        extra += actionButtons(text);
      }
      if(data.zip_url){
        const files = Array.isArray(data.files) ? data.files : [];
        const fileList = files.slice(0, 8).map(f => '<li>' + escapeHtml(f) + '</li>').join('');
        extra += '<div class="agent-download-box"><strong>ZIP gerado com ' + (data.file_count || files.length || 1) + ' arquivo(s)</strong>' + (fileList ? '<ul>' + fileList + '</ul>' : '') + '<a class="btn btn-primary" href="' + escapeHtml(data.zip_url) + '">Baixar ZIP gerado</a></div>';
      }
      addMessage('bot', answer, false, extra, data.stage);
      history.push({role: 'agente', content: answer});
      refreshConversations();
    }catch(error){
      loading.remove();
      addMessage('bot', 'Não consegui conectar ao Chat Agente agora. Verifique se o Flask/Railway reiniciou e tente novamente.');
    }
  }

  if(form){
    form.addEventListener('submit', function(event){
      event.preventDefault();
      const text = (input.value || '').trim();
      if(!text) return;
      input.value = '';
      sendMessage(text, 'plan');
    });
  }

  messages.addEventListener('click', function(event){
    if(event.target.matches('[data-agent-rethink]')){
      sendMessage(pendingQuestion || 'Repense o plano anterior antes de executar.', 'rethink');
    }
    if(event.target.matches('[data-agent-execute]')){
      sendMessage(pendingQuestion || 'Execute o plano aprovado.', 'execute');
    }
  });

  if(list){
    list.addEventListener('click', function(event){
      const deleteBtn = event.target.closest('[data-delete-conversation-id]');
      if(deleteBtn){
        event.preventDefault();
        event.stopPropagation();
        deleteConversation(deleteBtn.getAttribute('data-delete-conversation-id'));
        return;
      }
      const btn = event.target.closest('[data-conversation-id]');
      if(btn){ loadConversation(btn.getAttribute('data-conversation-id')); }
    });
  }

  if(deleteAllBtn){
    deleteAllBtn.addEventListener('click', deleteAllConversations);
  }

  if(newBtn){
    newBtn.addEventListener('click', function(){
      conversationId = null;
      resetMessages();
      refreshConversations();
      input && input.focus();
    });
  }

  document.querySelectorAll('[data-agent-example]').forEach(button => {
    button.addEventListener('click', function(){
      input.value = this.getAttribute('data-agent-example') || '';
      input.focus();
    });
  });

  refreshConversations();
})();
