# Portal de Cursos · Flask

Módulo integrado ao portal principal em `/curso-ingles/`.

## Instalação local

```bash
pip install -r ../requirements.txt
python ../run.py
```

## Acesso administrador

O login administrador vem das variáveis de ambiente do portal:

```text
ADMIN_USER=seu_usuario_admin
ADMIN_PASSWORD=sua_senha_admin_forte
SECRET_KEY=uma_chave_longa
```

Não deixe senha real escrita no código, README ou histórico.

## Banco de dados

Em produção/Railway, configure um banco persistente:

```text
DATABASE_URL=postgresql://...
```

Ou, caso queira separar somente o curso:

```text
CURSO_INGLES_DATABASE_URL=postgresql://...
```

Se `CURSO_INGLES_DATABASE_URL` não existir, o curso usa `DATABASE_URL`. SQLite local é apenas fallback de desenvolvimento.
