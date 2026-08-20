# Portal de Cursos — Evolução para Level 6

Data da revisão: 19/08/2026

Esta versão mantém o visual, os cursos e o fluxo principal do portal, mas adiciona práticas de engenharia de software, segurança, qualidade e operação que aproximam o projeto do **Level 6** definido durante o estudo.

## 1. Arquitetura e separação de responsabilidades

Foi criada a pasta `portal_core/` para impedir que toda regra nova continue crescendo dentro de `curso_ingles_app/app.py`.

```text
portal_core/
├── blueprints/
│   └── system.py
├── services/
│   ├── agent_policy.py
│   ├── audit_service.py
│   ├── user_service.py
│   └── workspace_service.py
├── logging_config.py
├── rate_limit.py
└── security.py
```

### Implementado

- Blueprint real para rotas de sistema/healthcheck.
- Serviços separados para exclusão de usuário, auditoria, workspace e política do agente.
- Configuração central por ambiente em `config.py`.
- `extensions.py` agora concentra SQLAlchemy e Flask-Migrate.

### Decisão de compatibilidade

O arquivo legado `curso_ingles_app/app.py` ainda contém várias rotas. Ele **não foi quebrado de uma vez** para evitar regressões no portal. A regra a partir desta versão é: novas regras de negócio entram em `portal_core/services/` e novas áreas independentes devem usar Blueprints. Assim o arquivo principal pode diminuir progressivamente.

---

## 2. Migrations de banco

Foi adicionado:

- `Flask-Migrate`;
- Alembic;
- pasta `migrations/`;
- migration inicial Level 6 para `curso_audit_log`;
- execução de `flask db upgrade` no Windows e no processo de deploy.

Comandos:

```bash
python -m flask --app app:application db migrate -m "descricao"
python -m flask --app app:application db upgrade
```

O `db.create_all()` foi mantido temporariamente como **modo de compatibilidade** com bancos locais existentes. Novas alterações de schema devem ser feitas por migration.

---

## 3. Segurança Web

### CSRF

POST, PUT, PATCH e DELETE agora possuem verificação de token CSRF.

- token criado na sessão;
- `<meta name="csrf-token">` incluído no layout;
- formulários recebem `_csrf_token` automaticamente;
- chamadas `fetch()` same-origin recebem `X-CSRF-Token` automaticamente.

Em produção, CSRF permanece ativo.

### Sessão

Configurações adicionadas:

- `SESSION_COOKIE_HTTPONLY = True`;
- `SESSION_COOKIE_SAMESITE = "Lax"`;
- `SESSION_COOKIE_SECURE = True` em produção;
- sessão permanente com duração limitada.

### Redirect seguro

O parâmetro `next` do login agora só aceita destino do próprio portal. URLs externas são descartadas.

### Headers de segurança

Cada resposta recebe:

- `X-Content-Type-Options: nosniff`;
- `X-Frame-Options: SAMEORIGIN`;
- `Referrer-Policy: strict-origin-when-cross-origin`;
- `X-Request-ID`.

---

## 4. Rate limiting

Foi criada uma proteção leve sem dependência externa para:

```text
Login       5/minuto
MCP         20/minuto
Chat Agente 30/minuto
```

Os valores podem ser alterados no `.env`.

Observação: o limitador atual funciona por processo. Em uma implantação futura com muitos workers/servidores, a evolução recomendada é Redis + Flask-Limiter.

---

## 5. RBAC e operações sensíveis

Foi criada a base `permission_required()` para permissões críticas.

A partir desta versão:

- o MCP `/mcp/portal` exige login;
- iniciar o runtime local de IA exige administrador;
- parar o runtime local de IA exige administrador;
- rotas administrativas continuam protegidas por `admin_required`.

Isso evita que um aluno comum controle um processo de IA compartilhado pelo servidor.

---

## 6. Integridade ao excluir usuário

O problema de exclusão incompleta foi corrigido.

Antes, a rota removia apenas `ModuleAttempt` antes de apagar o usuário. Agora o serviço `delete_user_and_related_data()` remove também:

- conversas do agente;
- mensagens ligadas às conversas;
- preferências do tutor;
- mensagens do tutor;
- erros recorrentes;
- exercícios adaptativos;
- tentativas de pronúncia;
- memória de tradução;
- progresso de inglês;
- eventos de estudo;
- provas/módulos relacionados ao usuário.

Isso mantém compatibilidade inclusive com bancos antigos cujas foreign keys ainda não foram migradas para cascade.

---

## 7. Audit Log

Foi criada a tabela:

```text
curso_audit_log
```

Campos principais:

```text
user_id
action
target
ip_address
metadata_json
created_at
```

Ações já auditadas incluem:

- login;
- logout;
- criação de usuário;
- atualização de usuário;
- exclusão de usuário;
- seleção de modelo Ollama;
- início do runtime local de IA;
- parada do runtime local de IA.

Os registros aparecem no painel Admin em **Ações sensíveis recentes**.

---

## 8. Logs e observabilidade

Foi criado logging rotativo em:

```text
instance/logs/portal.log
```

Cada requisição registra, quando aplicável:

```text
request_id
method
path
status
duration_ms
user_id
```

O header `X-Request-ID` permite relacionar um erro mostrado ao usuário com o log do servidor.

### Healthchecks

`/health` continua simples para Railway e monitoramento:

```json
{"ok": true, "service": "portal-de-cursos"}
```

Foi adicionado `/health/details`, restrito ao administrador, para verificar banco e runtime local de IA.

---

## 9. Política do Chat Agente

O Chat Agente continua sendo um gerador de arquivos, não um executor arbitrário de shell. Mesmo assim foram implementadas barreiras adicionais.

### Workspace por usuário

Antes:

```text
workspace compartilhado
```

Agora:

```text
curso_ingles_agent/
├── user_1/
├── user_2/
└── user_N/
```

Cada download procura o ZIP somente dentro do workspace do usuário autenticado.

### Política de caminhos

O agente:

- usa somente caminhos relativos;
- não pode escapar com `../`;
- não pode criar caminhos absolutos do Windows;
- bloqueia nomes sensíveis como `.ssh`, `.aws`, `.gnupg`, `.env`, `id_rsa` e `id_ed25519`.

### ai-jail

Esta versão **não executa shell arbitrário pelo Chat Agente**, então não foi criado um falso sandbox apenas para marcar checklist.

Se no futuro o agente ganhar execução de comandos, a arquitetura obrigatória registrada é:

```text
Windows
  -> WSL2
     -> ai-jail
        -> workspace Git dedicado
           -> worker do agente
```

Rede, Docker, GPU, display, SSH e credenciais devem permanecer opt-in.

---

## 10. Tratamento de erros

Foram criados handlers padronizados para:

- 400;
- 403;
- 404;
- 500.

APIs recebem JSON; páginas HTML recebem uma tela amigável `error.html`.

Em erro 500, a transação do banco é revertida com `rollback()`.

---

## 11. Testes

A suíte anterior foi preservada e recebeu novos casos para:

- bloquear redirect externo no login;
- impedir aluno comum de iniciar runtime compartilhado de IA;
- excluir usuário juntamente com dados relacionados;
- validar CSRF;
- validar política de caminhos do agente.

Foi adicionado `pytest-cov`. O CI gera o relatório de cobertura; o primeiro objetivo é medir a linha de base antes de impor um percentual mínimo artificial.

---

## 12. CI/CD

Criado:

```text
.github/workflows/ci.yml
```

Em push e pull request o workflow executa:

1. instalação das dependências;
2. `compileall`;
3. Ruff;
4. pytest + relatório de coverage;
5. `pip-audit` nas dependências.

Permissões do workflow são mantidas em `contents: read`.

---

## 13. Backup e recuperação

Foram adicionados:

```text
scripts/backup_db.py
scripts/restore_db.py
```

### SQLite

Copia o arquivo de banco para `backups/`.

### PostgreSQL

Usa `pg_dump` e `pg_restore`, se instalados no ambiente.

A restauração deve ser testada periodicamente. O restore agora exige confirmação explícita por padrão, cria cópia de segurança automática antes de sobrescrever SQLite e evita colocar senha PostgreSQL no argv de `pg_dump`/`pg_restore`.

---

## 14. Arquivos de documentação

```text
docs/ARCHITECTURE.md
docs/SECURITY.md
docs/OPERATIONS.md
LEVEL_6_IMPLEMENTADO.md
```

---

# Situação do projeto após esta versão

## Level 5 — consolidado

- frontend real;
- backend Flask;
- banco;
- autenticação;
- deploy;
- IA local/externa;
- testes;
- persistência.

## Level 6 — implementado em grande parte

- configuração por ambiente;
- services;
- Blueprint inicial;
- migrations;
- CSRF;
- cookies seguros;
- chave Gemini não persistida no banco em produção;
- RBAC para operações críticas;
- rate limit;
- audit log;
- logging estruturado;
- Request ID;
- tratamento de erros;
- workspace isolado por usuário;
- política anti-traversal/paths sensíveis e limite de tamanho por arquivo/lote do agente;
- testes de segurança;
- coverage;
- CI;
- dependency audit;
- GitHub Actions fixadas por SHA para reduzir risco de supply chain;
- backup/restore;
- documentação técnica.

## Evoluções futuras sem urgência

Estas melhorias passam a ser evolução, não requisito para considerar o projeto um laboratório Level 6:

1. continuar migrando rotas do `app.py` para Blueprints;
2. substituir o rate limit em memória por Redis quando houver múltiplas instâncias;
3. usar storage externo/S3 se arquivos do agente precisarem escalar;
4. separar o AI Service em worker/processo próprio quando a carga justificar;
5. integrar `ai-jail` somente se o agente passar a executar comandos arbitrários;
6. adicionar monitoramento externo de métricas e alertas;
7. remover definitivamente o bootstrap `db.create_all()` após todos os ambientes estarem sob Alembic.

---

# Regra para novas mudanças

A partir desta versão, antes de adicionar uma função ao portal, verificar:

```text
É rota HTTP?              -> Blueprint/rota
É regra de negócio?       -> service
É dado persistente novo?  -> model + migration
É ação sensível?          -> permissão + audit log
É POST/PUT/PATCH/DELETE?  -> CSRF
É chamada frequente?      -> considerar rate limit
É arquivo do agente?      -> workspace do usuário
Pode falhar?              -> log + tratamento de erro
Tem comportamento crítico?-> teste automatizado
```

Esse padrão é o principal ganho do Level 6: o sistema deixa de crescer apenas por funcionalidades e passa a crescer com **controle arquitetural**.

---

# Validação técnica deste pacote

Antes do empacotamento desta versão foram executadas validações que não dependem de serviços externos:

```text
Python compileall              -> OK
security.js                    -> sintaxe OK (node --check)
testes sem dependências Flask       -> 7 testes passaram
backup/restore SQLite temporário     -> round-trip OK
```

A suíte completa `pytest` foi preparada e ampliada, porém **não pôde ser executada no ambiente usado para montar este ZIP**, pois as dependências Python não estavam previamente instaladas e o ambiente estava sem resolução de rede/DNS para baixá-las do PyPI. Por isso este documento não declara falsamente que todos os testes passaram.

Após instalar as dependências localmente, a validação recomendada é:

```bash
python -m pip install -r requirements-dev.txt
python -m compileall -q .
python -m ruff check config.py extensions.py portal_core scripts tests
python -m pytest -q --cov=curso_ingles_app --cov=portal_core --cov-report=term-missing
```

Também foi reforçado o tratamento de segredos: em **produção**, `GOOGLE_API_KEY` é lida apenas das variáveis de ambiente e uma nova chave Gemini enviada pela interface administrativa não é persistida no banco. No desenvolvimento/local, o fluxo anterior permanece disponível por conveniência.


## Proteção contra spoofing de proxy

O rate limit e o audit log não confiam em `X-Forwarded-For` por padrão. Para deployments atrás de proxy reverso confiável, habilite `TRUST_PROXY_HEADERS=1`; fora desse cenário, mantenha desativado para evitar que um cliente forje o IP e contorne limites por endereço.


## Gate de lint progressivo

O CI aplica Ruff obrigatoriamente ao núcleo Level 6 (`portal_core`, configuração, scripts e testes). O `curso_ingles_app/app.py` continua coberto por compilação e testes funcionais, mas ainda não entra no gate completo de lint porque contém o monólito legado em processo de migração para Blueprints. A cada módulo extraído, ele deve passar a entrar no gate de lint.
