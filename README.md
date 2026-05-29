# Plataforma Multi-Programas

Central única com múltiplos programas Flask no mesmo deploy/Git.

## Rotas

- `/` — Central de Programas
- `/prompt/` — Prompt Profissional
- `/financeiro/` — Financeiro Pessoal
- `/curso-ingles/` — Portal de Cursos
- `/editor-admin/` — Editor Visual Admin
- `/health` — teste de saúde

## Configuração obrigatória em produção/Railway

Antes de subir para produção, configure estas variáveis no Railway:

```text
SECRET_KEY=gere_uma_chave_longa_e_aleatoria
ADMIN_USER=seu_usuario_admin
ADMIN_PASSWORD=sua_senha_admin_forte
DATABASE_URL=postgresql://...
FLASK_DEBUG=0
GOOGLE_API_KEY=sua_chave_google_opcional
GEMINI_MODEL=gemini-2.5-flash
AI_PROVIDER=gemini
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
```

Sem `SECRET_KEY`, `ADMIN_USER`, `ADMIN_PASSWORD` e banco persistente em produção, o boot falha para evitar credenciais fracas, sessões forjáveis e perda de dados.

Start command:

```text
gunicorn portal:application
```

## Banco de dados

- Em produção, use `DATABASE_URL` com Postgres.
- O módulo de cursos agora usa `CURSO_INGLES_DATABASE_URL` ou, se não existir, o mesmo `DATABASE_URL` dos outros módulos.
- O SQLite local fica apenas como fallback de desenvolvimento.
- Arquivos `.db`, `__pycache__` e `*.pyc` não devem ser versionados.

## Acessos administrativos

Não existe senha real gravada no código ou na documentação. O administrador vem das variáveis:

- `ADMIN_USER`
- `ADMIN_PASSWORD`
- `ADMIN_EMAIL` opcional

Em ambiente local, caso você não configure `.env`, o projeto usa credenciais temporárias de desenvolvimento apenas para teste. Em Railway/produção, configure as variáveis obrigatoriamente.

## Painel Admin e API de IA

Acesse o módulo de prompts em `/prompt`. Ao fazer login como administrador, o sistema abre o painel `/prompt/admin`, onde é possível configurar o provedor de IA, chave do Google Gemini, modelo e Ollama local.

A chave da API não deve ser salva em README nem em código. Prefira variável de ambiente ou cofre de segredos. Quando salva pelo painel, ela fica restrita ao admin e não aparece para usuários comuns.

## IA no financeiro

O módulo financeiro possui painel administrativo próprio em `/financeiro/admin-ia`. Usuários comuns podem usar análises internas sem visualizar a chave.

## Curso de Inglês integrado

A Central possui a opção **Portal de Cursos** em `/curso-ingles/`. O curso usa banco persistente quando `DATABASE_URL` ou `CURSO_INGLES_DATABASE_URL` está configurado.

## Editor Visual Admin

A página nova enviada foi adicionada ao sistema em `/editor-admin/` e exige login administrativo configurado por variável de ambiente.

## Importar comprovante PicPay/Nubank em PDF

Na área **Financeiro > Receitas e despesas**, existe a seção **Importar comprovante**. O sistema tenta ler automaticamente data, valor, recebedor, banco/instituição e ID da transação.

## Histórico de segurança recente

- Removidas credenciais reais do código e da documentação.
- `SECRET_KEY` agora vem de variável de ambiente e é obrigatória em produção.
- `ADMIN_USER` e `ADMIN_PASSWORD` são obrigatórios em produção.
- Curso pode usar Postgres via `DATABASE_URL`/`CURSO_INGLES_DATABASE_URL` para evitar perda de dados em redeploy.
- Tabelas do curso foram prefixadas com `curso_` para evitar colisão com outros módulos quando usarem o mesmo Postgres.
- Adicionado `.gitignore` para impedir versionamento de `.db`, `*.pyc`, `__pycache__`, `.env`, uploads e workspaces gerados.

## Migrações de banco — Fase 1

O projeto agora tem uma base preparada para Flask-Migrate/Alembic.

Comandos principais:

```bash
flask --app migration_app:app db migrate -m "descricao_da_mudanca"
flask --app migration_app:app db upgrade
```

O objeto SQLAlchemy compartilhado fica em:

```text
extensions.py
```

Novos modelos devem importar assim:

```python
from extensions import db
```

Use sempre `__tablename__` prefixado por domínio, por exemplo:

```text
prompt_...
finance_...
curso_...
```

Isso evita colisões quando todos os programas usam o mesmo Postgres.

## Fase 2 — serviços centralizados

Foram adicionados dois módulos de fundação:

- `ai_service.py`: chamada única para IA. Use `call_ai(...)` em novos módulos em vez de importar IA de outro app.
- `storage_service.py`: armazenamento central para uploads, ZIPs e workspaces.

Variável opcional para produção/Railway com volume persistente:

```text
PERSISTENT_STORAGE_DIR=/app/storage
AI_PROVIDER=gemini
GEMINI_MODEL=gemini-2.5-flash
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.1
```

Atenção: no Railway, `127.0.0.1` é o container do Railway, não o seu computador. Ollama local só funciona rodando o portal no seu PC ou apontando `OLLAMA_BASE_URL` para um servidor Ollama acessível.

## Qualidade e testes

Com a Fase 3, o projeto possui testes básicos e CI:

```bash
pip install -r requirements.txt
pytest -q
python -m compileall .
ruff check .
```

O arquivo `docs/PLANO_BLUEPRINTS.md` descreve a migração segura para uma aplicação Flask única com Blueprints.

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

## Check antes de rodar ou subir

A partir da Fase 4E, rode este comando antes de testar localmente ou fazer deploy:

```bash
python check_project.py
```

Ele não substitui o teste manual no navegador, mas ajuda a encontrar erros comuns de migração para Blueprints, como `url_for()` quebrado, arquivo estático ausente, `.db` dentro do pacote ou `Procfile` incorreto.

### Correção importante: DATABASE_URL com `porta`

Não deixe no `.env` uma URL de exemplo como:

```env
DATABASE_URL=postgresql://usuario:senha@host:porta/banco
```

Esse valor é apenas modelo. Localmente, você pode remover `DATABASE_URL` para o app usar SQLite temporário. No Railway, use a URL real do Postgres.

## Railway — Python 3.13.3

Este pacote inclui `.python-version` com `3.13.3` e `runtime.txt` com `python-3.13.3` para evitar falha de build do Railpack/mise ao tentar instalar versões antigas do Python.

Antes de subir, confirme que a raiz do projeto contém:

```text
.python-version
runtime.txt
requirements.txt
start.sh
Procfile
railway.json
portal.py
main.py
run.py
```


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
