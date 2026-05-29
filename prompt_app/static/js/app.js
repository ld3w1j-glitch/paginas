// Corrige chamadas de API quando o Prompt Profissional roda dentro do portal em /prompt.
function promptApiUrl(path){
  const clean = path.startsWith('/') ? path : '/' + path;
  const baseFromBody = document.body?.dataset?.appBase || '';
  if(baseFromBody) return baseFromBody.replace(/\/$/, '') + clean;
  if(window.location.pathname === '/prompt' || window.location.pathname.startsWith('/prompt/')) return '/prompt' + clean;
  return clean;
}
async function readJsonResponse(response){
  const text = await response.text();
  try { return JSON.parse(text || '{}'); }
  catch(_){ return {ok:false, error:`Resposta não JSON do servidor. HTTP ${response.status}. ${text.slice(0,400)}`}; }
}

function copyText(id){
  const el=document.getElementById(id); if(!el) return;
  navigator.clipboard.writeText(el.value||el.innerText||'').then(()=>toast('Copiado para a área de transferência.'));
}
function toast(msg){
  const t=document.createElement('div'); t.className='toast'; t.textContent=msg; document.body.appendChild(t);
  setTimeout(()=>t.classList.add('show'),20); setTimeout(()=>{t.classList.remove('show'); setTimeout(()=>t.remove(),250)},2200);
}
document.querySelectorAll('[data-copy]').forEach(btn=>btn.addEventListener('click',()=>copyText(btn.dataset.copy)));

const wizard=document.querySelector('.wizard'); let step=1;
function setStep(n){
  step=Math.max(1,Math.min(3,n));
  document.querySelectorAll('.step-panel').forEach(p=>p.classList.toggle('active', Number(p.dataset.panel)===step));
  const progress=document.getElementById('progressText'); if(progress) progress.textContent=`Passo ${step} de 3`;
  location.hash='gerador';
}
document.querySelectorAll('.next-step').forEach(b=>b.addEventListener('click',()=>setStep(step+1)));
document.querySelectorAll('.prev-step').forEach(b=>b.addEventListener('click',()=>setStep(step-1)));

// Quando o usuário escolhe "corrigir erro", abre automaticamente as opções de erro no passo 3.
document.querySelectorAll('input[name="modo"]').forEach(r=>r.addEventListener('change',()=>{
  if(r.checked && r.value==='erro') toast('No passo 3, cole o traceback em Opções avançadas ou use a aba Corrigir erro.');
}));

const projectSelect=document.getElementById('projectSelect');
if(projectSelect){projectSelect.addEventListener('change',()=>{
  const opt=projectSelect.selectedOptions[0]; if(!opt) return;
  const c=document.getElementById('contexto'), f=document.getElementById('arquivos');
  if(c && !c.value) c.value=opt.dataset.context||'';
  if(f && !f.value) f.value=opt.dataset.files||'';
  if(opt.value) toast('Contexto do projeto carregado.');
});}

async function analyzeError(srcId,outId){
  const text=document.getElementById(srcId)?.value||''; const out=document.getElementById(outId); if(!out) return;
  if(!text.trim()){out.textContent='Cole um erro primeiro.'; return;}
  out.textContent='Analisando...';
  try{
    const r=await fetch(promptApiUrl('/api/analyze-error'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
    const data=await r.json();
    out.textContent=`Causa provável: ${data.cause||'não identificada'}\nSolução sugerida: ${data.solution||'analisar manualmente'}\nDetectado: ${data.detected||'não'}`;
  }catch(e){out.textContent='Falha ao analisar. Verifique se o servidor está rodando.';}
}
document.getElementById('analisarErro')?.addEventListener('click',()=>analyzeError('erro_codigo','erroResultado'));
document.getElementById('analisarErroLivre')?.addEventListener('click',()=>analyzeError('erroLivre','erroLivreResultado'));

async function gemini(action){
  const text=document.getElementById('promptFinal')?.value||''; const out=document.getElementById('geminiOutput'); if(!out)return;
  out.textContent='Chamando Gemini...';
  try{
    const r=await fetch(promptApiUrl('/api/gemini'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,text})});
    const data=await r.json(); out.textContent=data.text||'Sem resposta.';
  }catch(e){out.textContent='Falha ao chamar Gemini.';}
}
document.getElementById('melhorarGemini')?.addEventListener('click',()=>gemini('melhorar'));
document.getElementById('reduzirGemini')?.addEventListener('click',()=>gemini('reduzir'));

const busca=document.getElementById('buscaHistorico');
if(busca){busca.addEventListener('input',()=>{
  const q=busca.value.toLowerCase();
  document.querySelectorAll('.hist-item').forEach(item=>{item.style.display=item.innerText.toLowerCase().includes(q)?'block':'none';});
});}

// Navegação lateral com destaque visual.
const links=document.querySelectorAll('.nav-link');
links.forEach(link=>link.addEventListener('click',()=>{links.forEach(l=>l.classList.remove('active')); link.classList.add('active');}));

// Evita que o usuário envie sem pedido e entende melhor o caminho.
document.getElementById('promptForm')?.addEventListener('submit',(e)=>{
  const pedido=document.getElementById('pedido');
  if(!pedido.value.trim()){
    e.preventDefault(); setStep(2); pedido.focus(); toast('Escreva o pedido principal antes de gerar.');
  }
});


function setChatStatus(items){
  const el=document.getElementById('chatStatus'); if(!el) return;
  el.innerHTML=items.map((txt,i)=>`<span class="${i===items.length-1?'active':''}">${txt}</span>`).join('');
}

// Chat Executor: conversa com Gemini, salva histórico e extrai arquivos gerados.
function appendChat(role, text){
  const box=document.getElementById('chatBox'); if(!box) return;
  const empty=box.querySelector('.chat-empty'); if(empty) empty.remove();
  const msg=document.createElement('div');
  msg.className='chat-msg '+role;
  msg.innerHTML=`<div class="chat-role">${role==='user'?'Você':'Executor IA'}</div><pre></pre>`;
  msg.querySelector('pre').textContent=text;
  box.appendChild(msg); box.scrollTop=box.scrollHeight;
}
function renderGeneratedFiles(files, sessionId){
  const wrap=document.getElementById('chatFiles');
  const link=document.getElementById('downloadChatZip');
  const applyForm=document.getElementById('applyZipForm');
  if(!wrap) return;
  if(!files || !files.length){
    wrap.innerHTML='<p class="empty">Nenhum arquivo extraído ainda. Peça normalmente para gerar arquivos; o sistema já orienta a IA no formato correto.</p>';
    if(applyForm) applyForm.style.display='none';
    return;
  }
  wrap.innerHTML='<h3>Arquivos detectados no workspace</h3>'+files.map(f=>`<div class="file-pill">📄 <b>${f.path}</b> <small>${f.size} caracteres</small> <button class="btn small preview-file" data-file-id="${f.id}" type="button">Ver</button> <a class="btn small" href="${promptApiUrl(`/export/generated-file/${f.id}`)}">Baixar</a></div>`).join('');
  if(link && sessionId){ link.style.display='inline-flex'; link.href=promptApiUrl(`/export/chat/${sessionId}`); }
  if(applyForm && sessionId){ applyForm.style.display='block'; applyForm.action=promptApiUrl(`/export/chat/${sessionId}/apply`); }
}
async function loadChatSession(id){
  if(!id) return;
  const res=await fetch(promptApiUrl(`/api/chat/${id}`)); const data=await res.json();
  const box=document.getElementById('chatBox'); if(box) box.innerHTML='';
  data.messages.forEach(m=>appendChat(m.role,m.content));
  renderGeneratedFiles(data.files, data.session_id);
  const link=document.getElementById('downloadChatZip'); if(link){link.style.display='inline-flex'; link.href=promptApiUrl(`/export/chat/${data.session_id}`);}
}
document.getElementById('chatSession')?.addEventListener('change',e=>loadChatSession(e.target.value));

document.addEventListener('click', async (e)=>{
  const btn=e.target.closest('.preview-file');
  if(!btn) return;
  const id=btn.dataset.fileId;
  const box=document.getElementById('filePreview');
  const title=document.getElementById('filePreviewTitle');
  const content=document.getElementById('filePreviewContent');
  if(!box||!title||!content) return;
  content.textContent='Carregando arquivo...'; box.style.display='block';
  const res=await fetch(promptApiUrl(`/api/generated-file/${id}`)); const data=await res.json();
  title.textContent=data.path||'Arquivo'; content.textContent=data.content||data.error||'Sem conteúdo.';
});
document.getElementById('closeFilePreview')?.addEventListener('click',()=>{
  const box=document.getElementById('filePreview'); if(box) box.style.display='none';
});
document.getElementById('sendChat')?.addEventListener('click', async()=>{
  const input=document.getElementById('chatInput');
  const session=document.getElementById('chatSession');
  const project=document.getElementById('chatProject');
  const msg=(input?.value||'').trim();
  if(!msg){ toast('Escreva uma mensagem para o Chat Executor.'); return; }
  appendChat('user', msg); input.value='';
  setChatStatus(['Pedido recebido','Analisando contexto','Chamando Gemini']);
  appendChat('assistant', 'Processando com Gemini... Se a API não estiver configurada, aparecerá o aviso aqui.');
  const responseType=document.getElementById('chatResponseType');
  const res=await fetch(promptApiUrl('/api/chat/send'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg, session_id:session?.value, project_id:project?.value, response_type:responseType?.value})});
  const data=await res.json();
  const box=document.getElementById('chatBox');
  const last=box?.querySelector('.chat-msg.assistant:last-child pre');
  if(last) last.textContent=data.answer || data.error || 'Sem resposta.';
  if(session && data.session_id){
    let exists=[...session.options].some(o=>o.value==String(data.session_id));
    if(!exists){ const o=document.createElement('option'); o.value=data.session_id; o.textContent='Conversa atual'; session.prepend(o); }
    session.value=data.session_id;
  }
  setChatStatus(['Pedido recebido','Resposta gerada','Arquivos salvos no workspace']);
  renderGeneratedFiles(data.files||[], data.session_id);
});

// Configuração e teste da chave Google Gemini.
document.getElementById('testGemini')?.addEventListener('click', async()=>{
  const out=document.getElementById('geminiTestOutput');
  if(!out) return;
  out.style.display='block';
  out.textContent='Testando conexão com Gemini...';
  try{
    const r=await fetch(promptApiUrl('/api/test-gemini'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});
    const data=await readJsonResponse(r);
    const status = data.ok ? 'Conexão funcionando' : 'Verifique a chave/modelo';
    out.textContent=`Modelo: ${data.model||''}\nStatus: ${status}\n\nResposta:\n${data.text || data.error || 'Sem detalhe retornado pelo servidor.'}`;
  }catch(e){
    out.textContent='Falha ao testar. Verifique se o servidor está rodando, se a chave foi salva e se a rota /prompt/api/test-gemini está acessível.';
  }
});

// Busca modelos disponíveis pela própria chave Google salva.
document.getElementById('loadGeminiModels')?.addEventListener('click', async()=>{
  const box=document.getElementById('geminiModelsBox');
  if(!box) return;
  box.style.display='block';
  box.textContent='Buscando modelos disponíveis para sua chave...';
  try{
    const r=await fetch(promptApiUrl('/api/gemini/models'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});
    const data=await readJsonResponse(r);
    if(!data.ok){ box.textContent=data.error||'Não foi possível buscar os modelos.'; return; }
    if(!data.models || !data.models.length){ box.textContent='Nenhum modelo com generateContent foi retornado para essa chave.'; return; }
    const select=document.querySelector('select[name="gemini_model"]');
    if(select){
      const current=select.value;
      select.innerHTML='';
      data.models.forEach(m=>{
        const opt=document.createElement('option');
        opt.value=m.name; opt.textContent=m.name + (m.display_name && m.display_name!==m.name ? ` — ${m.display_name}` : '');
        select.appendChild(opt);
      });
      if([...select.options].some(o=>o.value===current)) select.value=current;
    }
    box.innerHTML='<b>Modelos encontrados:</b><br>'+data.models.slice(0,20).map(m=>`• ${m.name}`).join('<br>')+'<br><br>Escolha um deles no campo Modelo Gemini e clique em Salvar configuração da API.';
  }catch(e){
    box.textContent='Falha ao buscar modelos. Verifique se o servidor está rodando e se a chave foi salva.';
  }
});
