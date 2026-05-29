
## 2026-05-28 - Importação automática de comprovante PicPay PDF

### Pedido
Adicionar leitura de comprovante Pix do PicPay em PDF para registrar automaticamente a transação no financeiro.

### Alterações
- Criado `financeiro_app/pdf_importer.py` para extrair texto do PDF com `pypdf`.
- Adicionada rota `POST /financeiro/transactions/import-picpay`.
- Adicionada seção "Importar comprovante PicPay" em `financeiro_app/templates/transactions.html`.
- Adicionado estilo visual responsivo para importação em `financeiro_app/static/css/styles.css`.
- Adicionada dependência `pypdf==5.9.0` em `requirements.txt`.

### Campos lidos no padrão PicPay
- Data do comprovante.
- Valor.
- Nome do recebedor.
- Banco/instituição do recebedor.
- ID da transação.

### Como testar
1. Criar ou acessar uma conta no financeiro.
2. Cadastrar uma conta bancária.
3. Abrir "Receitas e despesas".
4. Em "Importar comprovante PicPay", selecionar a conta e enviar o PDF.
5. Confirmar se a transação aparece no histórico como despesa Pix.

### Observações
- A importação automática foi feita inicialmente para o padrão `Comprovante de Pix` do PicPay.
- Outros bancos podem ser adicionados depois criando novos parsers.

## 2026-05-28 - Importação de comprovante Nubank

### Pedido
Adicionar leitura do padrão Nubank/Nu Pagamentos para registrar automaticamente a transação no financeiro, além do padrão PicPay já existente.

### Alterações
- Criado parser genérico de comprovantes em `financeiro_app/pdf_importer.py`.
- Mantida compatibilidade com PicPay.
- Adicionado suporte a comprovante Nubank/Nu Pagamentos com campos de data, valor, destino, origem, instituição e ID da transação.
- A tela de importação agora informa que aceita PicPay e Nubank.
- A rota nova é `/financeiro/transactions/import-comprovante`, mantendo `/financeiro/transactions/import-picpay` como compatibilidade.

### Arquivos alterados
- `financeiro_app/pdf_importer.py`
- `financeiro_app/routes/main.py`
- `financeiro_app/templates/transactions.html`
- `financeiro_app/static/css/styles.css`

### Como testar
1. Entrar no Financeiro.
2. Cadastrar uma conta bancária.
3. Abrir Receitas e despesas.
4. Enviar um PDF de comprovante PicPay ou Nubank.
5. Conferir se a transação foi registrada como despesa Pix/Transferência.

### Observação
A leitura automática depende do texto interno do PDF. Prints/imagens ainda devem ser lançados manualmente, pois OCR não foi incluído para manter o projeto leve no Railway.

## 2026-05-28 — Painel Admin para API/IA

- Criado painel administrativo em `/prompt/admin`.
- Login admin passou a ser configurado por variáveis `ADMIN_USER` e `ADMIN_PASSWORD`.
- Ao entrar como admin, o sistema abre o painel de administração automaticamente.
- Configuração da chave Google Gemini saiu da tela comum e ficou restrita ao admin.
- Usuários comuns podem usar os recursos de IA conectados pelo admin, sem visualizar a chave.
- Adicionado teste de conexão e busca de modelos Gemini dentro do painel admin.
- Mantida compatibilidade com Railway via variáveis `ADMIN_USER`, `ADMIN_PASSWORD`, `GOOGLE_API_KEY`, `GEMINI_MODEL` e `SECRET_KEY`.

## v6 - IA ligada ao financeiro

- Criado painel administrativo dentro do módulo financeiro em `/financeiro/admin-ia`.
- Login administrativo do financeiro passou a ser configurado por variáveis de ambiente.
- O login do financeiro agora aceita usuário ou e-mail.
- A chave da API Google Gemini fica salva apenas para o administrador e não aparece para usuários comuns.
- Adicionados botões de IA no Dashboard, Transações e Relatórios.
- A IA recebe um contexto financeiro resumido com saldo, receitas, despesas, contas e últimas transações.
- Criada tela de resultado da IA para mostrar a análise financeira de forma organizada.
- Mantida compatibilidade com Railway e com SQLite local.

## Inclusão do Curso de Inglês

- Adicionado o módulo `curso_ingles_app` ao projeto principal.
- A Central de Programas agora exibe o card "Curso de Inglês".
- O curso foi montado em `/curso-ingles/area/ingles`.
- Incluído botão de retorno para a Central dentro das telas do curso.
- O curso possui login próprio, módulos, prática, frases, vocabulário, plano de estudos e prova final.
- Administrador do curso passou a ser configurado por variáveis de ambiente.


## Correção de tema verde/dourado
- Reaplicado o tema verde/dourado diretamente nos CSS carregados por cada módulo.
- Adicionado cache-busting `?v=verde-dourado-2` nos links CSS para evitar navegador manter estilo antigo.
- Arquivos alterados: portal.css, financeiro styles.css, prompt style.css e CSS dos cursos.


## Ajuste da Central - Portal de Cursos
- O card antigo “Curso de Inglês” foi alterado para “Portal de Cursos”.
- O botão agora abre `/curso-ingles/`, que é a página inicial do portal, em vez de abrir direto `/curso-ingles/area/ingles`.
- O usuário pode escolher dentro do portal entre área interna, cursos, documentos, administração e demais páginas disponíveis.

## Gestão de usuários pelo admin
- O painel `/curso-ingles/admin` agora permite editar usuários existentes.
- O admin pode alterar nome, login/e-mail, senha, cargo, status ativo e permissão de administrador.
- O admin pode remover usuários, apagando também o histórico de provas desse usuário.
- Proteções adicionadas: o usuário logado não pode remover/desativar a si mesmo e o sistema impede remover o último administrador.


## Correção final de padronização visual
- Foi adicionada uma camada de CSS final forçada em todos os módulos para manter o tema verde/dourado.
- Corrigidos campos brancos, cards claros, tabelas, botões, telas do financeiro, prompt, portal e cursos.
- Atualizado versionamento do CSS para evitar cache antigo do navegador.

## Inclusão de página nova protegida por admin
- A nova página enviada foi integrada como **Editor Visual Admin**.
- Acesso pela Central em `/editor-admin/`.
- O acesso é protegido por login de administrador.
- Credenciais administrativas removidas do código; usar `ADMIN_USER` e `ADMIN_PASSWORD`.
- É possível trocar as credenciais no Railway com `ADMIN_USER` e `ADMIN_PASSWORD`.

## MCP flutuante do portal
- Adicionado botão flutuante no canto inferior direito das páginas do portal/curso.
- O botão usa a imagem do lobo (`curso_ingles_app/static/img/lobo.png`).
- Ao clicar, abre um chat MCP contextual que envia rota, título, texto visível e pergunta do usuário para orientar uma resposta lógica.
- Endpoint criado: `/curso-ingles/mcp/portal` quando acessado pelo Dispatcher, ou `/mcp/portal` dentro do app do portal.

## Integração da API do MCP no painel Admin do Portal
- Adicionado cadastro seguro de Google API Key dentro do painel Admin do portal/curso.
- O MCP flutuante do lobo agora usa a chave salva pelo admin para chamar Gemini.
- Se não houver chave configurada, o MCP continua funcionando em modo local/contextual.
- A chave salva não é exibida para usuários comuns nem reaparece no formulário.
- Incluído teste de conexão e opção para remover a chave salva.

## Chat Agente com Ollama, etapas e histórico
- Chat Agente do portal agora permite escolher provedor Gemini ou Ollama local no painel Admin.
- Adicionado fluxo por etapas: plano resumido, opção de repensar e execução aprovada.
- O agente pode criar arquivos e devolver ZIP após aprovação.
- Conversas do Chat Agente são salvas por usuário e podem ser retomadas depois.
- MCP do lobo também passa a usar o provedor configurado no Admin.

## 2026-05-28 — Escaneamento e conexão automática com Ollama local

- Adicionado endpoint administrativo `/admin/ollama/models` para escanear modelos instalados no Ollama usando `GET /api/tags`.
- Adicionado endpoint `/admin/ollama/use` para selecionar um modelo encontrado, salvar `ai_provider=ollama`, `ollama_base_url` e `ollama_model` no banco de configurações.
- Melhorado tratamento de erro do Ollama: quando o modelo não existe, o sistema informa modelos disponíveis e orienta usar o escaneamento.
- Atualizado o painel Admin com botão **Escanear Ollama**, lista visual de modelos locais e botão **Usar este modelo**.
- O Chat Agente e o MCP passam a usar automaticamente o modelo Ollama selecionado no painel.
- Incluído aviso importante: em Railway, `localhost` é o servidor Railway; para usar Ollama do PC é necessário rodar o portal localmente ou expor um serviço Ollama acessível.


## 28/05/2026 - Exclusão de conversas do Chat Agente

- Adicionado botão para excluir uma conversa individual no histórico do Chat Agente.
- Adicionado botão para excluir todas as conversas salvas do usuário conectado.
- Criada rota `DELETE /agent-chat/conversations` para apagar o histórico do usuário atual.
- A rota `DELETE /agent-chat/conversations/<id>` já remove a conversa e suas mensagens com segurança pelo usuário logado.
- A interface reseta para nova conversa quando a conversa ativa é excluída.

## 2026-05-28 — Chat Agente com roteamento multiagente

- Adicionada uma equipe multiagente no backend do Chat Agente.
- O sistema agora escolhe automaticamente uma cadeia curta de agentes conforme a conversa, contexto da tela, histórico, etapa e permissão para gerar arquivos.
- Agentes incluídos: Coordenador de Agentes, Analista de Contexto, Designer UX/UI, Frontend, Backend Flask, Segurança e Permissões, Gerador de Arquivos/ZIP e Testador.
- O prompt do Chat Agente agora orienta o modelo a mostrar o roteamento, chamar o próximo agente necessário e indicar qual agente deve continuar o trabalho.
- A resposta da API passou a retornar `agent_chain` e `next_agent` para a interface exibir a equipe acionada em cada etapa.
- A interface do chat passou a mostrar uma caixa “Equipe chamada nesta etapa” com os agentes usados e o próximo responsável sugerido.

## 2026-05-29 — LeanCTX nos multiagentes

- Adicionado o agente **LeanCTX - Contexto Enxuto** à equipe multiagente.
- O roteador agora pode chamar LeanCTX quando a conversa tem histórico maior, contexto longo, pedido de economia de tokens ou termos ligados a memória/contexto.
- O prompt multiagente passou a exigir bloco **LeanCTX** com objetivo, contexto essencial, arquivos prováveis, riscos e próximo agente.
- A tela do Chat Agente foi ajustada para indicar o fluxo **LeanCTX + roteamento**.

## 2026-05-29 — Correção urgente de segurança e persistência

- Removidas credenciais reais/pessoais do código, templates e documentação.
- Adicionado `security_config.py` para centralizar `SECRET_KEY`, credenciais admin, detecção de produção/Railway e normalização de banco.
- Em produção/Railway, `SECRET_KEY`, `ADMIN_USER`, `ADMIN_PASSWORD` e banco persistente passam a ser obrigatórios.
- O curso agora usa `CURSO_INGLES_DATABASE_URL` ou o mesmo `DATABASE_URL` do portal, evitando perda de dados no redeploy.
- Tabelas do curso receberam prefixo `curso_` para reduzir risco de colisão no Postgres compartilhado.
- Removido `legiao.db` e caches `__pycache__/*.pyc` do pacote.
- Criado `.gitignore` para bloquear `.env`, bancos locais, pycache, uploads e workspaces gerados.

## Fase 1 — Fundação de dados e migração

- Criado `extensions.py` na raiz com um único objeto `db = SQLAlchemy()` compartilhado.
- `financeiro_app/extensions.py` agora reexporta o `db` raiz para manter compatibilidade com os imports antigos.
- `prompt_app` passou a usar o `db` compartilhado.
- Tabelas do `prompt_app` receberam prefixo `prompt_`:
  - `prompt_user`
  - `prompt_project`
  - `prompt_history`
  - `prompt_custom_template`
  - `prompt_known_error`
  - `prompt_chat_session`
  - `prompt_chat_message`
  - `prompt_generated_file`
  - `prompt_app_setting`
- Foreign keys do `prompt_app` foram ajustadas para apontar para as tabelas prefixadas.
- `curso_ingles_app` passou a usar o `db` compartilhado em vez de criar outro `SQLAlchemy(app)` separado.
- `curso_ingles_app` ganhou `create_app()` para evitar rodar seed/create_all apenas por importação do módulo.
- `portal.py` agora chama factories para curso e editor admin.
- Criado `migration_app.py` para comandos Flask-Migrate/Alembic.
- Criada estrutura `migrations/` com `env.py`, `script.py.mako`, `alembic.ini` e `versions/`.
- Adicionado `Flask-Migrate==4.0.7` aos requirements.

Observação técnica: o `login_manager` ainda fica por app nesta fase porque o portal ainda usa `DispatcherMiddleware`. Unificar o `login_manager` com apps separados pode misturar loaders de usuários. A unificação total do login deve acontecer na Fase 2, quando os programas virarem Blueprints dentro de um único `create_app()`.

## Fase 2 — consolidação de serviços compartilhados

- Criado `ai_service.py` como ponto único para chamadas de IA.
- `financeiro_app` e `curso_ingles_app` deixaram de importar diretamente `prompt_app.prompt_engine`.
- Mantida compatibilidade com Gemini e preparada chamada direta para Ollama local via `/api/generate`.
- Criado `storage_service.py` para centralizar uploads/workspaces em `PERSISTENT_STORAGE_DIR` ou `instance/storage`.
- O workspace do Chat Agente do curso foi movido para o armazenamento centralizado.
- Uploads do financeiro agora usam o armazenamento centralizado por padrão.
- `health` do portal indica a fase arquitetural atual.

Observação: a migração total de DispatcherMiddleware para Blueprints deve ser feita com cuidado, porque ainda existem usuários, sessões e templates independentes por programa. Esta fase removeu o acoplamento mais perigoso entre apps antes dessa conversão.

## Fase 3 — limpeza, qualidade e preparação para Blueprints

- Adicionado `curso_ingles_app/course_utils.py` para reduzir duplicação entre busca de Português e Inglês.
- `search_portuguese_lessons()` e `search_english_modules()` agora usam um motor genérico de busca.
- `curso_ingles_app/requirements.txt` deixou de manter dependências soltas e aponta para o requirements raiz.
- Adicionados `pytest`, `ruff`, `pyproject.toml`, testes smoke e workflow GitHub Actions.
- Criado `docs/PLANO_BLUEPRINTS.md` com a ordem segura para converter o portal de `DispatcherMiddleware` para Blueprints.
- Removidos novamente `__pycache__` e `.pyc` antes do empacotamento.

## Fase 4A — Portal Blueprint e ponte de migração

- Criado `portal_blueprints.py` com as rotas principais do portal como Blueprint.
- Criado `legacy_wsgi_bridge.py` para isolar a montagem temporária dos apps legados.
- Criado `create_application()` em `portal.py` como factory principal do deploy.
- Adicionada rota `/system/programs` para listar os programas de forma centralizada.
- Mantidas as URLs atuais (`/prompt`, `/financeiro`, `/curso-ingles`, `/editor-admin`) para evitar quebra de login e templates durante a migração.
- Criado `docs/FASE4_BLUEPRINT_BRIDGE.md` documentando a estratégia segura para transformar cada módulo em Blueprint real.



## Fase 4B — Editor Admin em Blueprint nativo

- Criado `editor_admin_app/routes.py` com `editor_admin_bp`.
- O portal principal agora registra o Editor Admin diretamente como Blueprint em `/editor-admin`.
- O Editor Admin saiu do `DispatcherMiddleware`.
- `editor_admin_app/app.py` foi mantido como factory standalone apenas para compatibilidade/teste local.
- Os templates do Editor Admin foram ajustados para usar endpoints `editor_admin.*` e static próprio.
- A rota `/system/programs` agora marca o Editor Admin como `blueprint_nativo`.
- A ponte WSGI continua temporariamente para `/prompt`, `/financeiro` e `/curso-ingles`.

## Fase 4C — Prompt Profissional como Blueprint nativo

- Convertido `prompt_app` para `prompt_bp` registrado diretamente em `/prompt`.
- Removido `/prompt` da ponte `DispatcherMiddleware`.
- Ajustados endpoints dos templates para `prompt.*`.
- Corrigidas chamadas JavaScript do Chat Executor para respeitar a base `/prompt`.
- Mantida compatibilidade para rodar o Prompt isoladamente com `prompt_app.create_app()`.
- Financeiro e Curso continuam temporariamente na ponte WSGI para migração segura em etapas.



## Fase 4D — Financeiro como Blueprint nativo

- O módulo Financeiro agora é registrado diretamente em `/financeiro` como Blueprint.
- `/financeiro` saiu da ponte `DispatcherMiddleware`.
- Os templates do Financeiro foram isolados em `financeiro_app/templates/financeiro/`.
- Os endpoints foram ajustados para `financeiro.*` e `financeiro_auth.*`.
- A autenticação passou a usar IDs prefixados por domínio (`prompt:<id>` e `financeiro:<id>`) para evitar conflito entre usuários de módulos diferentes no mesmo app Flask.
- A ponte WSGI agora mantém apenas o Curso/Chat Agente até a próxima migração.

## Fase 4E — Estabilização e check antes de deploy

- Adicionado `check_project.py` para validar o projeto antes de executar ou subir para Railway.
- O verificador confere arquivos essenciais, variáveis de produção, sintaxe Python, `url_for()`, estáticos, `Procfile` e artefatos proibidos como `.db`, `.pyc` e `__pycache__`.
- Adicionada documentação `docs/FASE4E_ESTABILIZACAO.md`.
- O objetivo desta fase é estabilizar a migração já feita antes de converter o módulo de cursos, que é o maior e ainda está na ponte WSGI.

## Fase 4E.1 — Correção de boot SQLAlchemy AppSetting

- Corrigido erro de inicialização `Multiple classes found for path "AppSetting"` após a unificação do `db`.
- Ajustado `financeiro_app.models.User.settings` para referenciar `financeiro_app.models.AppSetting` com caminho completo.
- Melhorado `check_project.py` para detectar `db.relationship("Classe")` ambíguo quando a mesma classe existe em mais de um módulo.
- Rodado `python check_project.py` com sucesso.

## Fase 4E.2 — Correção de sessão compartilhada entre Prompt e Financeiro

- Corrigido erro do Financeiro após o usuário voltar da central logado no Prompt Profissional.
- O erro ocorria porque `current_user` podia ser um usuário do Prompt dentro do Financeiro.
- Adicionado isolamento de sessão nos Blueprints `prompt`, `financeiro` e `financeiro_auth`.
- O Financeiro agora redireciona para o login correto quando a sessão pertence a outro módulo.
- O dashboard financeiro passou a calcular totais por consulta `Transaction.query.filter_by(user_id=current_user.id)` em vez de acessar diretamente `current_user.transactions`.
- `check_project.py` executado com sucesso após remover `__pycache__` e `.pyc`.

## 2026-05-29 - Fase 4E.3 - Correção de DATABASE_URL com placeholder

Problema reportado:
- Ao iniciar o portal, o SQLAlchemy quebrou com `ValueError: invalid literal for int() with base 10: 'porta'`.
- Causa: `DATABASE_URL` ou `CURSO_INGLES_DATABASE_URL` estava com valor de exemplo, como `postgresql://usuario:senha@host:porta/banco`.

Correção aplicada:
- `security_config.py` agora detecta URLs de exemplo contendo `porta`, `usuario`, `senha`, `host` ou `banco`.
- Em ambiente local, se a URL estiver como exemplo, o sistema mostra aviso e usa SQLite local temporário.
- Em produção/Railway, o sistema falha com mensagem clara pedindo uma URL real de Postgres.
- `check_project.py` agora verifica se `.env`, `DATABASE_URL` ou `CURSO_INGLES_DATABASE_URL` estão com placeholder.


## Fase 4E.4 — Correção de templates e retorno ao portal

- Corrigido problema em que, após login no Prompt Profissional, abrir `/prompt/` carregava a página central em vez da tela do Prompt.
- A causa era colisão de templates com o mesmo nome `index.html` entre portal, Prompt e Editor Admin.
- Templates do Prompt foram isolados em `prompt_app/templates/prompt/`.
- Templates do Editor Admin foram isolados em `editor_admin_app/templates/editor_admin/`.
- Corrigidos renders do Financeiro para `financeiro/dashboard.html` e `financeiro/reports.html`, evitando `TemplateNotFound`.
- `check_project.py` passou a alertar sobre `render_template` sem namespace em módulos Blueprint.

## Fase 4E.5 — Correção de layout das lições do curso de português

- Corrigido o comportamento em que algumas lições ficavam com o cartão lateral separado do conteúdo principal.
- Ajustado o breakpoint do layout: em desktop com menu lateral, a lição permanece em duas colunas.
- Adicionado ajuste de quebra de texto para títulos, checklist e conteúdo extraído.
- Mantido layout em uma coluna apenas em tablet/celular.


## Fase 4E.6 — Railway/Railpack

- Adicionado start.sh na raiz para o Railway.
- Adicionado main.py como fallback de detecção Python no Railpack.
- Procfile e railway.json agora usam bash start.sh.
- Documentado que o deploy deve ser feito pela raiz completa do projeto, não apenas pelas pastas internas.

## Fase 4E.7 — Correção Railway Python 3.13.3

- Adicionado `.python-version` com `3.13.3` para o Railway/Railpack.
- Atualizado `runtime.txt` de `python-3.12.8` para `python-3.13.3`.
- Mantido `start.sh` como comando de inicialização do Railway.
- Marcado `start.sh` como executável.


## Fase 4E.8 — Railway abrindo apenas Editor Admin

- Corrigido start do Railway para apontar diretamente para `portal:application`.
- Adicionado `nixpacks.toml` como fallback.
- Adicionadas rotas `/central` e `/programas`.
- O Editor Admin iniciado sozinho agora mostra aviso de configuração incorreta.


## Fase 4E.9 — blindagem Railway contra abrir só o Editor Admin

- Adicionado `app.py` raiz como fallback WSGI apontando para `portal.application`.
- Adicionado `wsgi.py` raiz como fallback alternativo.
- `editor_admin_app/app.py` agora carrega o portal completo por padrão caso seja iniciado por engano em produção.
- Para rodar apenas o Editor Admin isolado localmente, use `RUN_EDITOR_STANDALONE=1`.
- Mantido o comando correto: `gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 portal:application`.
