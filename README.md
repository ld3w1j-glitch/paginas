# Portal de Cursos

Versão independente do projeto, contendo somente o Portal de Cursos. Os módulos Financeiro, Prompt Profissional, Editor Admin e a antiga Central de Programas não fazem parte deste pacote.

## O que permanece no sistema

- página pública institucional;
- login e administração de usuários;
- curso de português;
- curso de inglês;
- laboratório complementar de inglês 4.1, com professor e tradução offline;
- módulos, provas, notas e progressão de acesso;
- documentos e páginas institucionais;
- Chat Agente com Gemini, Ollama ou modo local;
- banco SQLite para uso local e PostgreSQL para produção.

O portal abre diretamente em `http://127.0.0.1:5000/`.

## Complemento do curso de inglês · 4.1

Depois de entrar no portal, abra **Curso de inglês → Laboratório offline**. A nova área compartilha o mesmo login do portal, mas mantém histórico, erros e progresso separados para cada usuário.

O laboratório inclui:

- professor integrado que corrige estruturas frequentes sem internet;
- memória pedagógica individual com erros recorrentes e revisão espaçada;
- exercícios adaptativos criados a partir das frases do próprio aluno;
- oito cenários: conversa livre, entrevista, restaurante, aeroporto, hotel, compras, consulta simulada e direções;
- tradutor neural inglês→português OPUS-MT já incluído no pacote e executado no navegador;
- memória de correções do tradutor por usuário;
- sincronização de módulos, lições, palavras, pontuação e XP no banco do portal;
- integração opcional com Qwen/llama.cpp para conversação neural local;
- integração opcional com whisper.cpp para gravar, transcrever e pontuar a correspondência da pronúncia.

O professor integrado e o tradutor OPUS-MT funcionam assim que o portal é iniciado localmente. Nenhuma chave de API é necessária.

### Qwen local opcional

Coloque na pasta `ia_local`:

- `llama-server.exe` (Windows) ou `llama-server` (Linux/macOS);
- um modelo de instruções em formato `.gguf`, por exemplo um Qwen Instruct quantizado.

Abra o Laboratório, selecione o modelo, pressione **Iniciar Qwen** e altere o motor do professor para **Qwen local opcional**. Se o servidor neural falhar, o professor integrado assume automaticamente.

### Pronúncia com Whisper opcional

Coloque na pasta `voz_local`:

- `whisper-cli.exe`/`main.exe` ou o executável equivalente do whisper.cpp;
- um modelo em inglês no formato `ggml-*.bin`.

Reinicie o portal. A gravação será convertida em WAV de 16 kHz no navegador e processada localmente. Os pacotes Qwen e Whisper não estão incluídos no ZIP por causa do tamanho; as instruções também estão nas respectivas pastas.

## Executar no Windows

A maneira mais simples é dar dois cliques em `INICIAR_LOCAL.bat`. O arquivo cria o ambiente virtual, instala as dependências, abre o navegador e inicia o portal.

Também é possível executar manualmente pelo Prompt de Comando:

```bat
py -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe app.py
```

## Primeiro acesso local

Quando nenhuma variável de ambiente foi configurada, o acesso inicial de desenvolvimento é:

```text
Usuário: admin
Senha: admin-local-change-me
```

Troque essas credenciais antes de publicar o sistema. O painel administrador permite criar os demais usuários.

## Configuração

Copie `.env.example` para `.env` e preencha os valores. Em produção, configure pelo menos:

```text
SECRET_KEY=uma-chave-longa-e-aleatoria
ADMIN_USER=seu-usuario
ADMIN_PASSWORD=sua-senha-forte
DATABASE_URL=postgresql://usuario:senha@host:porta/banco
```

Também é aceita a variável `CURSO_INGLES_DATABASE_URL` no lugar de `DATABASE_URL`.

Para o Chat Agente, escolha uma opção:

- Gemini: defina `GOOGLE_API_KEY` e `GEMINI_MODEL`;
- Ollama local: defina `AI_PROVIDER=ollama`, `OLLAMA_BASE_URL` e `OLLAMA_MODEL`;
- sem IA externa: o portal continua funcionando no modo local de orientação.

## Railway

O pacote já contém `Procfile`, `railway.json`, `nixpacks.toml` e `start.sh`. O processo de produção inicia `app:application`, e a verificação de saúde usa `/health`.

Para não perder banco e arquivos entre deploys, use PostgreSQL e, se utilizar arquivos gerados pelo Chat Agente, configure `PERSISTENT_STORAGE_DIR` apontando para um volume persistente.

## Testes

```bat
venv\Scripts\python.exe -m pytest -q
```

Os testes confirmam que o portal abre, o login funciona, os cursos carregam e as rotas dos sistemas removidos retornam 404.

## Estrutura principal

```text
Portal-de-Cursos/
├── app.py
├── curso_ingles_app/
│   ├── content/
│   ├── static/
│   ├── templates/
│   └── app.py
├── ai_service.py
├── security_config.py
├── storage_service.py
├── requirements.txt
└── INICIAR_LOCAL.bat
```
