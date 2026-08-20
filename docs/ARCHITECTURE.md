# Arquitetura Level 6

O Portal mantém as telas existentes, mas começa a separar infraestrutura e regras de negócio do arquivo legado de rotas.

```text
Browser
  -> Flask
     -> segurança (CSRF, sessão, rate limit, RBAC)
     -> routes/blueprints
        -> services
           -> SQLAlchemy/PostgreSQL ou SQLite
           -> AI providers
           -> workspace isolado por usuário
```

## Regra de evolução

Novas regras de negócio devem ir para `portal_core/services/`. Novas áreas independentes devem preferir Blueprints em `portal_core/blueprints/`. O arquivo `curso_ingles_app/app.py` continua compatível, porém deve encolher progressivamente.
