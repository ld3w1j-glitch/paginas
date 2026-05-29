# Fase 4E — Estabilização antes de produção

Esta fase não tenta converter mais um módulo grande. O objetivo é reduzir risco antes de subir para Railway ou continuar a migração para Blueprints.

## O que foi adicionado

- `check_project.py`: verificador estático do projeto.
- Conferência de arquivos essenciais do deploy.
- Conferência de variáveis obrigatórias quando o ambiente é produção/Railway.
- Conferência para evitar `.db`, `.pyc` e `__pycache__` dentro do pacote.
- Conferência de sintaxe Python sem depender de Flask instalado.
- Conferência dos `url_for()` usados nos templates e rotas já migradas.
- Conferência dos arquivos estáticos chamados pelos templates.
- Conferência do `Procfile` apontando para `portal:application`.

## Como usar

Antes de rodar ou subir:

```bash
python check_project.py
```

Se aparecer `ERRO`, corrija antes de fazer deploy.

## Teste manual recomendado

Depois do check passar, rode:

```bash
python portal.py
```

Abra e teste:

- `/`
- `/health`
- `/system/programs`
- `/editor-admin`
- `/prompt`
- `/financeiro`
- `/curso-ingles`

## Próxima fase sugerida

Converter o `curso_ingles_app` para Blueprint real. Ele é o maior módulo, então o ideal é dividir em subpacotes primeiro:

- `curso_ingles_app/models.py`
- `curso_ingles_app/auth.py`
- `curso_ingles_app/agents.py`
- `curso_ingles_app/routes_portal.py`
- `curso_ingles_app/routes_portugues.py`
- `curso_ingles_app/routes_ingles.py`
- `curso_ingles_app/routes_admin.py`

Só depois disso registrar o curso no portal principal como Blueprint nativo.
