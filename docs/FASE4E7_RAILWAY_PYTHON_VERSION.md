# Fase 4E.7 — Correção da versão Python no Railway

## Problema

O Railway/Railpack tentou instalar Python 3.12.8 e o build falhou por causa da verificação de artefatos do `mise`.

## Correção

Foi adicionado o arquivo `.python-version` na raiz do projeto com:

```txt
3.13.3
```

Também foi atualizado o `runtime.txt` para:

```txt
python-3.13.3
```

Assim o Railway deve usar Python 3.13.3 no build.

## Arquivos alterados

- `.python-version`
- `runtime.txt`
- `start.sh` marcado como executável
- `docs/FASE4E7_RAILWAY_PYTHON_VERSION.md`
- `README.md`
- `HISTORICO_DO_PROJETO.md`
