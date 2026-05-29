# Fase 4E.4 — Templates isolados por Blueprint

## Problema

Após converter módulos para Blueprints, havia vários arquivos chamados `index.html`, `login.html` e outros nomes genéricos em Blueprints diferentes.

Quando o Flask/Jinja procurava `index.html`, podia encontrar o template do portal central antes do template do Prompt Profissional. O efeito visual era: o usuário clicava para entrar no Prompt, a tela piscava e continuava parecendo estar na central.

No Financeiro, algumas rotas ainda chamavam `dashboard.html` e `reports.html`, mas os arquivos já estavam em `financeiro/dashboard.html` e `financeiro/reports.html`, gerando `TemplateNotFound`.

## Correção

- Prompt agora renderiza `prompt/index.html`, `prompt/login.html` e `prompt/admin.html`.
- Editor Admin agora renderiza `editor_admin/index.html`, `editor_admin/admin_login.html` e demais páginas internas.
- Financeiro agora renderiza `financeiro/dashboard.html` e `financeiro/reports.html`.

## Resultado esperado

- Entrar novamente no Prompt abre a interface correta do Prompt, não a central.
- Dashboard e relatórios do Financeiro deixam de gerar erro 500 por template ausente.
