# Segurança do Portal

## Padrões implementados

- cookies HttpOnly e SameSite=Lax; Secure em produção;
- CSRF em POST/PUT/PATCH/DELETE;
- validação de redirecionamento após login;
- rate limit básico para login, MCP e Chat Agente;
- MCP exige login;
- iniciar/parar runtime local de IA exige administrador;
- cabeçalhos de segurança nas respostas;
- workspace do Chat Agente separado por usuário;
- caminhos do agente limitados ao workspace;
- paths absolutos, traversal (`..`) e nomes sensíveis são rejeitados;
- arquivos gerados pelo agente possuem limites de tamanho por arquivo e por lote;
- audit log para ações sensíveis;
- segredos por variáveis de ambiente.

## Sandbox externo

O Python do portal não substitui sandbox de sistema operacional. Para agentes que executem código, o desenho recomendado no Windows é:

```text
Windows -> WSL2 -> ai-jail -> workspace Git dedicado -> worker do agente
```

Rede, Docker, GPU, display, SSH e credenciais devem permanecer desligados por padrão e entrar apenas como opt-in por tarefa.

## Segredos de IA

Em produção, `GOOGLE_API_KEY` é lida exclusivamente das variáveis de ambiente do servidor. A interface administrativa não persiste novas chaves Gemini no banco em produção. No modo local/desenvolvimento, a gravação pela interface continua disponível por conveniência.

## Proxy reverso e IP do cliente

`X-Forwarded-For` só entra no rate limit/auditoria quando `TRUST_PROXY_HEADERS=1`. Mantenha `0` ao expor o Flask diretamente; habilite apenas quando houver um proxy reverso confiável controlando esse cabeçalho.
