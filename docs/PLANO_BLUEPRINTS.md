# Plano de conversão para Blueprints

Estado atual: o portal ainda usa `DispatcherMiddleware`, mas já possui banco, storage e IA centralizados.

Próximo movimento seguro:

1. Criar `portal_app/create_app()` como factory única.
2. Converter cada programa em Blueprint com `url_prefix`:
   - `/prompt`
   - `/financeiro`
   - `/curso-ingles`
   - `/editor-admin`
3. Renomear endpoints que hoje usam nomes genéricos como `index`, `login` e `logout` para evitar colisão.
4. Manter um único `db.init_app(app)` na factory principal.
5. Manter `LoginManager` único somente depois de unificar o modelo de usuário ou criar loaders por namespace.
6. Rodar migrações antes de remover o modo compatível.

Motivo para não fazer em um único salto: `prompt_app`, `curso_ingles_app` e `editor_admin_app` usam endpoints genéricos em vários `url_for()`. Converter tudo de uma vez sem renomear endpoints pode quebrar navegação, login e sessão.
