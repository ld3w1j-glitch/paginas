from __future__ import annotations
import os, re, zipfile, json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple

BASE_RULES = """Você é meu arquiteto técnico, gerente de projeto, programador, revisor, documentador e professor.
Antes de responder qualquer pedido técnico, faça diagnóstico, arquitetura, implementação organizada, teste, documentação e entrega funcional.
Regras obrigatórias: preservar funcionalidades existentes, não travar por ambiguidade, assumir solução prática, economizar tokens, explicar riscos, validar no Windows e preparar Railway quando solicitado.
"""

WORK_MODES = {
    "novo": "Criar projeto do zero com arquitetura profissional.",
    "erro": "Corrigir erro com causa provável, arquivos afetados e correção mínima.",
    "visual": "Melhorar interface sem quebrar funcionalidades.",
    "funcionalidade": "Adicionar funcionalidade preservando o projeto existente.",
    "railway": "Preparar para Railway com deploy seguro.",
    "documentacao": "Criar ou atualizar documentação.",
    "continuidade": "Continuar projeto anterior usando contexto salvo.",
    "auto": "Detectar automaticamente o tipo de tarefa.",
}

TARGETS = {
    "chatgpt": "O prompt será usado no ChatGPT. Pode pedir arquivos, ZIP, validação e explicação curta.",
    "claude": "O prompt será usado no Claude. Pode ser mais estruturado e longo, com contexto detalhado.",
    "gemini": "O prompt será usado no Gemini. Seja direto, objetivo e bem delimitado.",
    "cursor": "O prompt será usado em editor/IDE. Foque em arquivos afetados e patch mínimo.",
    "generico": "Prompt genérico para qualquer IA.",
}

EXPECTED = {
    "explicacao": "Apenas explicação clara.",
    "arquivo": "Arquivo corrigido ou arquivos mínimos necessários.",
    "codigo": "Código completo organizado.",
    "zip": "Projeto final organizado para ZIP.",
    "arquitetura": "Plano de arquitetura antes do código.",
    "passo": "Correção ou implementação com passo a passo.",
}

@dataclass
class PromptData:
    pedido: str
    contexto: str = ""
    arquivos: str = ""
    erro_codigo: str = ""
    modo: str = "novo"
    destino: str = "chatgpt"
    resultado: str = "zip"
    economico: bool = False
    preservar: bool = True
    railway: bool = False
    equipe: bool = False
    projeto_nome: str = ""
    modelo_extra: str = ""
    zip_analysis: str = ""


def score_request(data: PromptData) -> Tuple[int, List[str]]:
    score = 45
    missing = []
    if data.pedido and len(data.pedido.strip()) > 20: score += 15
    else: missing.append("pedido principal mais detalhado")
    if data.contexto.strip(): score += 10
    else: missing.append("contexto do projeto")
    if data.arquivos.strip() or data.zip_analysis.strip(): score += 10
    else: missing.append("estrutura/arquivos existentes")
    if data.resultado: score += 8
    if data.modo: score += 7
    if data.erro_codigo.strip(): score += 5
    return min(score, 100), missing


def analyze_error(text: str) -> Dict[str, str]:
    t = (text or "").lower()
    if not t.strip():
        return {"detected": "não", "cause": "Nenhum erro informado", "solution": "Cole o erro completo quando precisar de diagnóstico."}
    rules = [
        ("powershell_activate", ["activate.ps1", "execution_policies", "pssecurityexception"], "PowerShell bloqueou ativação do venv", "Usar INICIAR_SISTEMA.bat, CMD com activate.bat ou Set-ExecutionPolicy RemoteSigned -Scope CurrentUser."),
        ("module_not_found", ["modulenotfounderror", "no module named"], "Dependência não instalada no ambiente usado", "Instalar com venv\\Scripts\\python.exe -m pip install -r requirements.txt e rodar com o mesmo Python."),
        ("import_error", ["importerror", "cannot import name"], "Importação incompatível ou função inexistente", "Verificar versão da biblioteca e substituir import por função existente."),
        ("pg_config", ["pg_config executable not found", "psycopg2"], "Driver PostgreSQL tentando compilar no Windows", "Evitar psycopg2 local; usar SQLite no PC e pg8000/psycopg no Railway."),
        ("port", ["address already in use", "porta", "port is in use"], "Porta ocupada", "Trocar PORT ou encerrar processo que está usando a porta."),
        ("database_url", ["database_url", "postgres://"], "Configuração de banco no deploy", "Normalizar postgres:// para postgresql+pg8000:// e configurar variáveis no Railway."),
        ("gemini_quota", ["resource_exhausted", "quota exceeded", "http 429", "current quota", "free_tier_requests", "free_tier_input_token_count"], "Cota da API Google Gemini esgotada ou indisponível para esta chave", "Aguardar, trocar modelo/chave, verificar cota no Google AI Studio ou configurar faturamento. O gerador local continua funcionando sem API."),
        ("gemini_model", ["model not found", "gemini", "generatecontent"], "Modelo Gemini inválido ou indisponível", "Listar modelos ou configurar GEMINI_MODEL para um modelo atual disponível."),
    ]
    for code, keys, cause, solution in rules:
        if any(k in t for k in keys):
            return {"detected": code, "cause": cause, "solution": solution}
    if "traceback" in t:
        return {"detected": "traceback", "cause": "Erro Python indicado por traceback", "solution": "Ler a última linha do traceback e verificar o arquivo/linha indicados."}
    return {"detected": "não", "cause": "Nenhum erro conhecido detectado automaticamente", "solution": "Analisar manualmente o log completo."}


def analyze_zip(file_storage) -> str:
    names = []
    with zipfile.ZipFile(file_storage) as zf:
        for n in zf.namelist():
            if not n.endswith('/'):
                names.append(n)
    names = names[:500]
    tech = []
    joined = "\n".join(names).lower()
    if "requirements.txt" in joined or any(n.endswith(".py") for n in names): tech.append("Python")
    if "flask" in joined or "run.py" in joined or any("templates/" in n for n in names): tech.append("Flask provável")
    if "package.json" in joined: tech.append("Node/JavaScript")
    if "procfile" in joined or "railway.json" in joined: tech.append("Railway já iniciado")
    if any("static/" in n for n in names): tech.append("Frontend separado em static")
    risks = []
    for key in ["requirements.txt", "run.py", "Procfile", "railway.json", ".env.example"]:
        if key.lower() not in joined: risks.append(f"Verificar ausência de {key}")
    tree = "\n".join(names[:80])
    return f"Tecnologias detectadas: {', '.join(tech) or 'não identificado'}\nRiscos/atenções: {', '.join(risks) or 'nenhum risco básico detectado'}\n\nArquivos principais detectados:\n{tree}"


def build_prompt(data: PromptData) -> Dict[str, str | int | List[str]]:
    if data.erro_codigo and data.modo == "auto": data.modo = "erro"
    score, missing = score_request(data)
    error = analyze_error(data.erro_codigo)
    depth = "econômico e direto" if data.economico else "profissional, completo e organizado"
    preserve = "Preservar funcionalidades existentes. Não refazer o projeto sem necessidade. Alterar apenas arquivos necessários." if data.preservar else "Pode propor refatoração maior se fizer sentido."
    railway = "Preparar para Railway com PORT, gunicorn, Procfile, railway.json e variáveis de ambiente seguras." if data.railway else "Railway somente se for necessário ou solicitado."
    team = "Simule uma equipe técnica: arquiteto, backend, frontend, DevOps, revisor, documentador e professor." if data.equipe else "Atue como especialista técnico único, com raciocínio organizado."

    prompt = f"""# PROMPT PROFISSIONAL V6 — WORKSPACE EXECUTOR

## Projeto
{data.projeto_nome or 'Projeto não informado'}

## Pedido original
{data.pedido.strip()}

## Modo de trabalho
{WORK_MODES.get(data.modo, data.modo)}

## Destino do prompt
{TARGETS.get(data.destino, data.destino)}

## Resultado esperado
{EXPECTED.get(data.resultado, data.resultado)}

## Profundidade
Responder em modo {depth}.

## Regras fixas
{BASE_RULES}
- {preserve}
- {railway}
- {team}

## Contexto fixo do projeto
{data.contexto.strip() or 'Sem contexto adicional. Assuma a solução prática mais segura.'}

## Estrutura/arquivos existentes
{data.arquivos.strip() or 'Estrutura não informada. Caso gere código, criar estrutura organizada.'}

## Análise automática de ZIP, se houver
{data.zip_analysis.strip() or 'Nenhum ZIP analisado.'}

## Erro, traceback, log ou código relacionado
{data.erro_codigo.strip() or 'Nenhum erro/log informado.'}

## Diagnóstico automático de erro
Causa provável: {error.get('cause', 'não aplicável')}
Solução sugerida: {error.get('solution', 'não aplicável')}

## Modelo personalizado extra
{data.modelo_extra.strip() or 'Nenhum modelo personalizado aplicado.'}

## Ordem obrigatória da resposta
1. Diagnóstico resumido
2. Suposições usadas
3. Arquitetura ou plano de alteração
4. Arquivos que serão criados ou alterados
5. Implementação ou entrega
6. Como instalar e testar no Windows
7. Como subir para Railway, se aplicável
8. Erros comuns e soluções
9. Registro para HISTORICO_DO_PROJETO.md
10. Próximos passos recomendados

## Restrições importantes
- Não apagar funcionalidades existentes sem necessidade.
- Se a alteração for pequena, entregar apenas o arquivo necessário.
- Se afetar várias partes, entregar ZIP completo organizado.
- Ser sincero sobre limitações.
- Preferir solução funcional em vez de promessa futura.
"""
    short = f"""Atue como arquiteto/programador/revisor. Pedido: {data.pedido.strip()}
Contexto: {data.contexto.strip() or 'assuma solução prática'}
Modo: {WORK_MODES.get(data.modo, data.modo)}
Entregue: {EXPECTED.get(data.resultado, data.resultado)}
Preserve o projeto existente e informe arquivos afetados, teste Windows e Railway quando aplicável."""
    checklist = "\n".join([
        f"Qualidade do pedido: {score}/100",
        *(f"Faltando: {m}" for m in missing),
        "Inclui preservação do projeto" if data.preservar else "Preservação desativada",
        "Inclui Railway" if data.railway else "Railway não obrigatório",
        "Inclui análise de erro" if data.erro_codigo else "Sem erro informado",
        "Inclui análise de ZIP" if data.zip_analysis else "Sem ZIP analisado",
    ])
    history_entry = f"""## {datetime.now().strftime('%d/%m/%Y %H:%M')} - Prompt gerado v6
- Projeto: {data.projeto_nome or 'não informado'}
- Pedido: {data.pedido[:250]}
- Modo: {data.modo}
- Destino: {data.destino}
- Resultado esperado: {data.resultado}
- Qualidade: {score}/100
- Observações: {'; '.join(missing) if missing else 'pedido bem contextualizado'}
"""
    return {"prompt": prompt, "short": short, "checklist": checklist, "history_entry": history_entry, "score": score, "missing": missing, "error": error}


def call_gemini(action: str, text: str, api_key: str | None = None, model_name: str | None = None) -> str:
    """Chama o Gemini pela API REST oficial, sem depender do pacote google-generativeai.

    Isso evita erro de instalação no Windows em caminhos longos, como:
    google/ai/generativelanguage_v1beta/.../grpc_asyncio.py
    """
    api_key = (api_key or os.getenv("GOOGLE_API_KEY") or "").strip()
    model_name = (model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash").strip()
    if not api_key:
        return "Configure a chave do Google Gemini na aba Configurações da API, no arquivo .env ou nas variáveis do Railway."

    instructions = {
        "melhorar": "Melhore este prompt, mantendo clareza e sem aumentar demais.",
        "reduzir": "Reduza este prompt mantendo o essencial.",
        "arquitetura": "Transforme em especificação técnica com arquitetura.",
        "erro": "Analise o erro e gere um plano de correção.",
        "chat": "Responda como arquiteto técnico e programador. Organize em diagnóstico, plano, arquivos e código quando necessário.",
    }.get(action, "Melhore este texto.")

    import json
    import urllib.parse
    import urllib.request
    import urllib.error

    prompt = f"{instructions}\n\n{text}"
    safe_model = urllib.parse.quote(model_name, safe="")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{safe_model}:generateContent?key={urllib.parse.quote(api_key)}"
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.4,
            "topP": 0.9,
            "maxOutputTokens": 4096,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
        candidates = result.get("candidates", [])
        if not candidates:
            return "Gemini respondeu sem conteúdo. Verifique o modelo configurado."
        parts = candidates[0].get("content", {}).get("parts", [])
        return "\n".join(part.get("text", "") for part in parts).strip() or "Sem resposta do Gemini."
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return _format_gemini_http_error(exc.code, detail, model_name)
    except Exception as exc:
        return f"Erro ao chamar Gemini: {exc}"


def _format_gemini_http_error(status_code: int, detail: str, model_name: str) -> str:
    """Transforma erros brutos da API em mensagens claras para o usuário final."""
    lower = (detail or "").lower()
    try:
        parsed = json.loads(detail) if detail else {}
        message = parsed.get("error", {}).get("message", "")
        status = parsed.get("error", {}).get("status", "")
    except Exception:
        message = detail or ""
        status = ""

    if status_code == 429 or "resource_exhausted" in lower or "quota" in lower:
        return f"""⚠️ Cota da API Google Gemini esgotada ou indisponível para esta chave.

O sistema está funcionando, mas o Google recusou a chamada por limite de uso/quota.

Modelo configurado: {model_name}
Código: HTTP 429 / RESOURCE_EXHAUSTED

O que fazer agora:
1. Aguarde alguns minutos e teste novamente.
2. Troque o modelo na aba Chave Google, por exemplo: gemini-2.5-flash, gemini-2.5-flash-lite ou gemini-2.5-pro.
3. Confira se sua chave está ativa no Google AI Studio e se o projeto tem cota disponível.
4. Se o limite gratuito estiver como 0, será necessário usar outra chave/projeto ou configurar faturamento/cota no Google.
5. Enquanto isso, use o Gerador de Prompt normal do sistema, que funciona sem chamar a API.

Mensagem resumida do Google:
{message[:500]}"""

    if status_code == 400 and ("api key" in lower or "key" in lower):
        return "A chave Google parece inválida ou mal formatada. Vá em Chave Google, cole a API Key novamente e teste a conexão."

    if status_code == 404 or "not found" in lower or "models/" in lower:
        return f"O modelo Gemini configurado não foi encontrado ou não está disponível para esta chave: {model_name}. Use a aba Chave Google e clique em Buscar modelos disponíveis. Como primeira tentativa, use gemini-2.5-flash ou gemini-2.5-flash-lite. O modelo antigo gemini-1.5-flash pode não estar liberado para sua chave/API."

    if status_code in (401, 403):
        return "A chamada foi recusada pelo Google. Verifique se a API Key está correta, ativa e autorizada para usar a Gemini API."

    return f"Erro HTTP ao chamar Gemini: {status_code}. Detalhe resumido: {message[:700] or detail[:700]}"



def list_gemini_models(api_key: str | None = None) -> Dict[str, object]:
    """Lista modelos disponíveis para a chave usando o endpoint oficial ListModels.

    Retorna apenas modelos que declaram suporte ao método generateContent, quando essa
    informação estiver presente na resposta.
    """
    import urllib.parse
    import urllib.request
    import urllib.error

    api_key = (api_key or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        return {"ok": False, "error": "Configure a Google API Key antes de buscar modelos.", "models": []}
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={urllib.parse.quote(api_key)}"
    request = urllib.request.Request(url, headers={"Content-Type": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = []
        for item in payload.get("models", []):
            name = (item.get("name") or "").replace("models/", "")
            methods = item.get("supportedGenerationMethods") or []
            if methods and "generateContent" not in methods:
                continue
            if name:
                models.append({
                    "name": name,
                    "display_name": item.get("displayName") or name,
                    "methods": methods,
                    "input_limit": item.get("inputTokenLimit"),
                    "output_limit": item.get("outputTokenLimit"),
                })
        preferred = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro", "gemini-2.0-flash"]
        models.sort(key=lambda m: (preferred.index(m["name"]) if m["name"] in preferred else 999, m["name"]))
        return {"ok": True, "models": models, "count": len(models)}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return {"ok": False, "error": _format_gemini_http_error(exc.code, detail, "ListModels"), "models": []}
    except Exception as exc:
        return {"ok": False, "error": f"Falha ao buscar modelos: {exc}", "models": []}

def build_chat_system_prompt(project_name: str = "", context: str = "", files: str = "", response_type: str = "gerar_arquivos") -> str:
    response_map = {
        "explicacao": "Priorize explicação clara, sem gerar arquivos se não for necessário.",
        "gerar_arquivos": "Quando fizer sentido, gere arquivos completos usando o formato obrigatório ---FILE---.",
        "corrigir_codigo": "Corrija código existente com patch mínimo, explicando arquivos afetados.",
        "preparar_zip": "Organize a resposta para gerar arquivos e baixar um ZIP final.",
        "analisar_erro": "Analise o erro, causa provável, correção mínima e como testar no Windows.",
        "aplicar_projeto": "Pense como workspace: gere apenas arquivos que devem ser criados ou substituídos no projeto original."
    }
    response_instruction = response_map.get(response_type, response_map["gerar_arquivos"])
    return f"""Você é um executor técnico dentro de um sistema de prompts.
Sua função é conversar com o usuário, entender o pedido, pensar como arquiteto técnico e entregar uma solução organizada.

TIPO DE RESPOSTA SOLICITADO:
{response_instruction}

REGRAS DE COMPORTAMENTO:
- Não responda de forma solta; siga uma ordem clara.
- Faça diagnóstico resumido, suposições, plano, arquivos afetados, implementação e teste.
- Se o usuário pedir código, entregue arquivos completos quando possível.
- Se estiver em modo aplicar projeto, gere caminhos exatamente iguais aos arquivos que devem entrar no ZIP final.
- Não invente que salvou arquivos; use o formato FILE para o sistema realmente extrair.
- Preserve funcionalidades existentes.
- Evite promessa futura; entregue a melhor solução possível na resposta atual.
- Para Flask, use estrutura app/, templates/, static/, requirements.txt e run.py quando criar projeto.
- Para Windows, explique como testar sem depender do PowerShell activate.
- Para Railway, use PORT, gunicorn, Procfile, railway.json e variáveis de ambiente quando aplicável.

FORMATO PARA CRIAR ARQUIVOS:
Quando gerar arquivos, use exatamente este formato para cada arquivo:

---FILE: caminho/do/arquivo.ext---
```linguagem
conteúdo do arquivo
```
---END FILE---

Isso permite que o sistema extraia os arquivos e gere um ZIP.

PROJETO ATUAL:
Nome: {project_name or 'não selecionado'}
Contexto:
{context or 'sem contexto salvo'}

Estrutura/arquivos conhecidos:
{files or 'estrutura não informada'}
"""


def extract_generated_files(text: str) -> List[Dict[str, str]]:
    files: List[Dict[str, str]] = []
    pattern = re.compile(r"---FILE:\s*(.*?)\s*---\s*```(?:[\w+-]*)?\n(.*?)\n```\s*---END FILE---", re.DOTALL | re.IGNORECASE)
    for match in pattern.finditer(text or ""):
        path = match.group(1).strip().replace("\\", "/")
        content = match.group(2)
        if path and ".." not in path and not path.startswith("/"):
            files.append({"path": path, "content": content})
    return files
