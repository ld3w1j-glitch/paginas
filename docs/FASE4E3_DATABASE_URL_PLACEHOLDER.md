# Fase 4E.3 - Correção de DATABASE_URL com placeholder

## Erro corrigido

```text
ValueError: invalid literal for int() with base 10: 'porta'
```

Esse erro acontece quando o `.env` ou variável do Windows/Railway está com uma URL de exemplo, por exemplo:

```env
DATABASE_URL=postgresql://usuario:senha@host:porta/banco
```

O trecho `porta` precisa ser um número real, como `5432`. Como estava escrito literalmente `porta`, o SQLAlchemy tentava converter isso para número e quebrava.

## Comportamento novo

Em ambiente local:

- Se a URL estiver com placeholder, o portal mostra aviso.
- O sistema usa SQLite local temporário para permitir teste.

Em produção/Railway:

- O portal não inicia com placeholder.
- Ele mostra mensagem clara pedindo uma URL real de Postgres.

## Exemplo local simples

Para testar local sem Postgres, remova `DATABASE_URL` do `.env` ou use:

```env
SECRET_KEY=chave_local_grande
ADMIN_USER=admin
ADMIN_PASSWORD=admin123forte
```

## Exemplo Railway/Postgres real

```env
DATABASE_URL=postgresql://usuario_real:senha_real@servidor_real.railway.internal:5432/railway
```
