from __future__ import annotations

import json
import random
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

IRREGULAR_AFTER_DID = {
    "went": "go",
    "saw": "see",
    "did": "do",
    "had": "have",
    "made": "make",
    "took": "take",
    "came": "come",
    "got": "get",
    "was": "be",
    "were": "be",
    "bought": "buy",
    "thought": "think",
    "wrote": "write",
    "spoke": "speak",
}

THIRD_PERSON_FORMS = {
    "go": "goes",
    "do": "does",
    "have": "has",
    "study": "studies",
    "watch": "watches",
    "work": "works",
    "live": "lives",
    "like": "likes",
    "want": "wants",
    "need": "needs",
    "play": "plays",
    "speak": "speaks",
    "read": "reads",
    "write": "writes",
    "depend": "depends",
}

TO_BASE = {value: key for key, value in THIRD_PERSON_FORMS.items()}
TO_BASE.update({"is": "be", "are": "be", "went": "go", "saw": "see", "made": "make", "took": "take"})

SCENARIOS = {
    "free": {
        "title": "Conversa livre",
        "role": "Professor particular",
        "goal": "Praticar qualquer assunto no nível do aluno.",
        "opening": "Tell me about your day in English.",
    },
    "job-interview": {
        "title": "Entrevista de emprego",
        "role": "Entrevistador de uma empresa",
        "goal": "Treinar apresentação, experiência, pontos fortes e objetivos profissionais.",
        "opening": "Good morning. Could you introduce yourself?",
    },
    "restaurant": {
        "title": "Restaurante",
        "role": "Atendente de um restaurante",
        "goal": "Pedir mesa, escolher pratos, fazer perguntas e pagar a conta.",
        "opening": "Good evening. Do you have a reservation?",
    },
    "airport": {
        "title": "Aeroporto",
        "role": "Funcionário do check-in",
        "goal": "Fazer check-in, despachar bagagem e entender orientações de embarque.",
        "opening": "Hello. May I see your passport and ticket, please?",
    },
    "hotel": {
        "title": "Hotel",
        "role": "Recepcionista do hotel",
        "goal": "Confirmar reserva, pedir informações e resolver problemas no quarto.",
        "opening": "Welcome. How can I help you today?",
    },
    "shopping": {
        "title": "Compras",
        "role": "Vendedor de uma loja",
        "goal": "Perguntar preço, tamanho, cor, desconto e forma de pagamento.",
        "opening": "Hello. Are you looking for anything in particular?",
    },
    "doctor": {
        "title": "Consulta médica",
        "role": "Profissional de saúde em uma simulação educativa",
        "goal": "Descrever sintomas e compreender perguntas básicas, sem diagnóstico real.",
        "opening": "What brings you here today?",
    },
    "directions": {
        "title": "Pedindo informações",
        "role": "Morador da cidade",
        "goal": "Pedir e compreender direções, distâncias e meios de transporte.",
        "opening": "Hi. Where do you need to go?",
    },
}


def _replace_after_did(match: re.Match) -> str:
    auxiliary = match.group(1)
    verb = IRREGULAR_AFTER_DID[match.group(2).lower()]
    return f"{auxiliary} {verb}"


def _replace_third_person(match: re.Match) -> str:
    subject = match.group(1)
    verb = THIRD_PERSON_FORMS[match.group(2).lower()]
    return f"{subject} {verb}"


def _replace_modal_base(match: re.Match) -> str:
    return f"{match.group(1)} {TO_BASE.get(match.group(2).lower(), match.group(2).lower())}"


def _replace_question_base(match: re.Match) -> str:
    return f"{match.group(1)} {match.group(2)} {TO_BASE.get(match.group(3).lower(), match.group(3).lower())}"


RULES = (
    {
        "key": "age-with-be",
        "pattern": re.compile(r"\bI have (\d{1,3}) years(?: old)?\b", re.IGNORECASE),
        "replacement": lambda match: f"I am {match.group(1)} years old",
        "explanation": "Para falar idade em inglês, usamos o verbo to be: I am ... years old.",
    },
    {
        "key": "agree-without-be",
        "pattern": re.compile(r"\bI am agree\b", re.IGNORECASE),
        "replacement": "I agree",
        "explanation": "Agree já é um verbo; por isso, não usamos am antes dele.",
    },
    {
        "key": "sure-with-be",
        "pattern": re.compile(r"\bI have sure\b", re.IGNORECASE),
        "replacement": "I am sure",
        "explanation": "Em inglês, sure funciona como adjetivo e acompanha o verbo to be: I am sure.",
    },
    {
        "key": "modal-without-do",
        "pattern": re.compile(r"\bI (?:do not|don't) can\b", re.IGNORECASE),
        "replacement": "I can't",
        "explanation": "Can é um verbo modal. A negativa é can't ou cannot, sem o auxiliar do.",
    },
    {
        "key": "base-after-did",
        "pattern": re.compile(
            r"\b(did not|didn't) (went|saw|did|had|made|took|came|got|was|were|bought|thought|wrote|spoke)\b",
            re.IGNORECASE,
        ),
        "replacement": _replace_after_did,
        "explanation": "Depois de did ou didn't, o verbo principal volta para a forma base.",
    },
    {
        "key": "third-person-negative",
        "pattern": re.compile(r"\b(he|she|it) (?:do not|don't)\b", re.IGNORECASE),
        "replacement": lambda match: f"{match.group(1)} doesn't",
        "explanation": "Com he, she ou it no presente negativo, usamos doesn't.",
    },
    {
        "key": "third-person-present",
        "pattern": re.compile(
            r"\b(he|she|it) (go|do|have|study|watch|work|live|like|want|need|play|speak|read|write|depend)\b",
            re.IGNORECASE,
        ),
        "replacement": _replace_third_person,
        "explanation": "No presente simples, o verbo recebe -s, -es ou -ies com he, she e it.",
    },
    {
        "key": "people-are",
        "pattern": re.compile(r"\bpeople is\b", re.IGNORECASE),
        "replacement": "people are",
        "explanation": "People é plural em inglês, portanto combina com are.",
    },
    {
        "key": "comparative-no-more",
        "pattern": re.compile(r"\bmore better\b", re.IGNORECASE),
        "replacement": "better",
        "explanation": "Better já é o comparativo de good; não usamos more antes dele.",
    },
    {
        "key": "days-use-on",
        "pattern": re.compile(
            r"\bin (Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
            re.IGNORECASE,
        ),
        "replacement": lambda match: f"on {match.group(1)}",
        "explanation": "Usamos a preposição on antes dos dias da semana.",
    },
    {
        "key": "depend-on",
        "pattern": re.compile(r"\bdepend(?:s)? of\b", re.IGNORECASE),
        "replacement": lambda match: "depends on" if match.group(0).lower().startswith("depends") else "depend on",
        "explanation": "A combinação natural é depend on, e não depend of.",
    },
    {
        "key": "married-to",
        "pattern": re.compile(r"\bmarried with\b", re.IGNORECASE),
        "replacement": "married to",
        "explanation": "Para indicar com quem alguém é casado, usamos married to.",
    },
    {
        "key": "take-a-photo",
        "pattern": re.compile(r"\bmake a (photo|picture)\b", re.IGNORECASE),
        "replacement": lambda match: f"take a {match.group(1)}",
        "explanation": "Em inglês, a combinação habitual é take a photo/picture.",
    },
    {
        "key": "state-with-be",
        "pattern": re.compile(r"\bI have (hungry|thirsty|afraid)\b", re.IGNORECASE),
        "replacement": lambda match: f"I am {match.group(1).lower()}",
        "explanation": "Hungry, thirsty e afraid são estados expressos com o verbo to be.",
    },
    {
        "key": "continuous-form",
        "pattern": re.compile(r"\bI am work\b", re.IGNORECASE),
        "replacement": "I am working",
        "explanation": "Depois de am em uma ação em andamento, usamos o verbo com -ing.",
    },
    {
        "key": "negative-needs-do",
        "pattern": re.compile(r"\bI no (understand|know|want|need|like|have)\b", re.IGNORECASE),
        "replacement": lambda match: f"I don't {match.group(1).lower()}",
        "explanation": "No presente simples, a negativa com I usa don't antes do verbo principal.",
    },
    {
        "key": "continuous-go",
        "pattern": re.compile(r"\b(I|you|we|they) (am|is|are) go\b", re.IGNORECASE),
        "replacement": lambda match: f"{match.group(1)} {match.group(2)} going",
        "explanation": "Depois do verbo to be em uma ação em andamento, usamos going.",
    },
    {
        "key": "base-after-modal",
        "pattern": re.compile(
            r"\b(can|could|should|would|will|must) (goes|works|lives|likes|wants|needs|plays|speaks|reads|writes|has|does|studies|watches)\b",
            re.IGNORECASE,
        ),
        "replacement": _replace_modal_base,
        "explanation": "Depois de um verbo modal, usamos o verbo principal na forma base, sem -s.",
    },
    {
        "key": "base-after-question-auxiliary",
        "pattern": re.compile(
            r"\b(does|did) (he|she|it|you|we|they) (goes|works|likes|wants|needs|has|does|studies|went|saw|made|took)\b",
            re.IGNORECASE,
        ),
        "replacement": _replace_question_base,
        "explanation": "Depois de does ou did em uma pergunta, o verbo principal fica na forma base.",
    },
    {
        "key": "uncountable-information",
        "pattern": re.compile(r"\binformations\b", re.IGNORECASE),
        "replacement": "information",
        "explanation": "Information é incontável em inglês e normalmente não recebe plural.",
    },
    {
        "key": "uncountable-advice",
        "pattern": re.compile(r"\badvices\b", re.IGNORECASE),
        "replacement": "advice",
        "explanation": "Advice é incontável; para contar, usamos a piece of advice.",
    },
    {
        "key": "information-determiner",
        "pattern": re.compile(r"\b(these|those) information\b", re.IGNORECASE),
        "replacement": lambda match: f"{'this' if match.group(1).lower() == 'these' else 'that'} information",
        "explanation": "Como information é incontável e singular, usamos this information ou that information.",
    },
    {
        "key": "much-information",
        "pattern": re.compile(r"\bmany information\b", re.IGNORECASE),
        "replacement": "much information",
        "explanation": "Com o substantivo incontável information, usamos much em vez de many.",
    },
    {
        "key": "information-is",
        "pattern": re.compile(r"\binformation are\b", re.IGNORECASE),
        "replacement": "information is",
        "explanation": "Information é incontável e combina com o verbo no singular.",
    },
    {
        "key": "many-people",
        "pattern": re.compile(r"\b(?:much|very much) people\b", re.IGNORECASE),
        "replacement": "many people",
        "explanation": "People é contável e plural; por isso usamos many people.",
    },
    {
        "key": "easier-comparative",
        "pattern": re.compile(r"\bmore easy\b", re.IGNORECASE),
        "replacement": "easier",
        "explanation": "O comparativo de easy é easier.",
    },
    {
        "key": "do-homework",
        "pattern": re.compile(r"\b(make|makes) ((?:my|your|his|her|our|their|the)\s+)?homework\b", re.IGNORECASE),
        "replacement": lambda match: f"{'does' if match.group(1).lower() == 'makes' else 'do'} {match.group(2) or ''}homework",
        "explanation": "A combinação natural é do homework.",
    },
    {
        "key": "make-a-mistake",
        "pattern": re.compile(r"\bdo a mistake\b", re.IGNORECASE),
        "replacement": "make a mistake",
        "explanation": "A combinação natural é make a mistake.",
    },
    {
        "key": "turn-on-light",
        "pattern": re.compile(r"\bopen the light\b", re.IGNORECASE),
        "replacement": "turn on the light",
        "explanation": "Para ligar a luz, usamos turn on the light.",
    },
    {
        "key": "turn-off-light",
        "pattern": re.compile(r"\bclose the light\b", re.IGNORECASE),
        "replacement": "turn off the light",
        "explanation": "Para apagar a luz, usamos turn off the light.",
    },
    {
        "key": "explain-to-me",
        "pattern": re.compile(r"\bexplain me\b", re.IGNORECASE),
        "replacement": "explain to me",
        "explanation": "Quando indicamos a pessoa depois de explain, usamos explain to someone.",
    },
    {
        "key": "listen-to",
        "pattern": re.compile(r"\blisten (music|the music|me|him|her|us|them)\b", re.IGNORECASE),
        "replacement": lambda match: f"listen to {match.group(1)}",
        "explanation": "O verbo listen normalmente exige a preposição to antes do complemento.",
    },
    {
        "key": "go-home",
        "pattern": re.compile(r"\bgo to home\b", re.IGNORECASE),
        "replacement": "go home",
        "explanation": "Com home indicando destino, normalmente não usamos a preposição to.",
    },
    {
        "key": "arrive-home",
        "pattern": re.compile(r"\barrive (?:in|at) home\b", re.IGNORECASE),
        "replacement": "arrive home",
        "explanation": "Com home, usamos arrive home sem preposição.",
    },
    {
        "key": "discuss-without-about",
        "pattern": re.compile(r"\bdiscuss about\b", re.IGNORECASE),
        "replacement": "discuss",
        "explanation": "Discuss já inclui a ideia de falar sobre algo; about não é necessário.",
    },
    {
        "key": "enter-without-in",
        "pattern": re.compile(r"\benter in (the|a|an)\b", re.IGNORECASE),
        "replacement": lambda match: f"enter {match.group(1)}",
        "explanation": "Enter recebe o lugar diretamente, sem in: enter the room.",
    },
    {
        "key": "question-not-doubt",
        "pattern": re.compile(r"\bI have a doubt\b", re.IGNORECASE),
        "replacement": "I have a question",
        "explanation": "Para pedir esclarecimento, I have a question soa mais natural.",
    },
)


def _looks_portuguese(value: str) -> bool:
    lowered = value.lower()
    if re.search(r"[áàâãéêíóôõúç]", lowered):
        return True
    markers = {"como", "porque", "você", "voce", "quero", "preciso", "frase", "inglês", "ingles", "estou"}
    words = set(re.findall(r"[a-z]+", lowered))
    return len(words & markers) >= 2


def _normalize_sentence(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _mechanical_cleanup(value: str, corrections: list[dict]) -> str:
    cleaned = re.sub(r"\s+([,.!?;:])", r"\1", value)
    cleaned = re.sub(r"([,.!?;:])(?=[A-Za-z])", r"\1 ", cleaned)
    first_letter = re.search(r"[A-Za-z]", cleaned)
    if first_letter and first_letter.group(0).islower():
        position = first_letter.start()
        cleaned = cleaned[:position] + cleaned[position].upper() + cleaned[position + 1 :]
        corrections.append({
            "rule_key": "capitalization",
            "explanation": "Uma frase começa com letra maiúscula.",
        })
    if cleaned and cleaned[-1] not in ".!?":
        question_starters = ("what ", "where ", "when ", "why ", "who ", "how ", "do ", "does ", "did ", "can ", "could ", "would ", "will ", "are ", "is ")
        cleaned += "?" if cleaned.lower().startswith(question_starters) else "."
    return cleaned


def _distractor(corrected: str) -> str:
    replacements = (
        (" I am ", " I is "),
        ("I am ", "I is "),
        (" doesn't ", " don't "),
        (" are ", " is "),
        (" on ", " in "),
        (" better", " more better"),
        (" has ", " have "),
        (" goes ", " go "),
        (" works ", " work "),
    )
    padded = f" {corrected}"
    for old, new in replacements:
        if old in padded:
            return padded.replace(old, new, 1).strip()
    return corrected.rstrip(".?!") + "?"


def build_exercise(source: str, corrected: str, correction: dict) -> dict:
    options = []
    for candidate in (source.strip(), corrected.strip(), _distractor(corrected.strip())):
        if candidate and candidate not in options:
            options.append(candidate)
    random.Random(corrected).shuffle(options)
    return {
        "rule_key": correction.get("rule_key", "general"),
        "prompt": "Qual destas frases está correta?",
        "options": options,
        "answer": corrected.strip(),
        "explanation": correction.get("explanation", "Observe a estrutura da frase corrigida."),
    }


def integrated_tutor(message: str, level: str = "A1", scenario_key: str = "free") -> dict:
    source = _normalize_sentence(message)
    if not source:
        raise ValueError("Escreva uma frase ou pergunta para o professor.")
    if len(source) > 4000:
        raise ValueError("Envie no máximo 4.000 caracteres por mensagem.")
    if _looks_portuguese(source):
        return {
            "reply": (
                "No modo integrado, escreva uma frase em inglês e eu verificarei a estrutura. "
                "Para conversar livremente também em português, ative a IA local nas Configurações."
            ),
            "corrected_text": "",
            "corrections": [],
            "exercise": None,
            "engine": "Professor integrado offline",
        }

    corrected = source
    corrections: list[dict] = []
    for rule in RULES:
        corrected, count = rule["pattern"].subn(rule["replacement"], corrected)
        if count:
            corrections.append({
                "rule_key": rule["key"],
                "explanation": rule["explanation"],
            })
    corrected = _mechanical_cleanup(corrected, corrections)

    meaningful = [item for item in corrections if item["rule_key"] != "capitalization"]
    if meaningful:
        reply = (
            f"A ideia ficou compreensível. Uma forma correta e natural é: “{corrected}” "
            "Veja a explicação e faça a prática curta para fixar."
        )
        exercise = build_exercise(source, corrected, meaningful[0])
    else:
        prompts = {
            "A1": "Now add where or when this happens.",
            "A2": "Now rewrite it in the past.",
            "B1": "Now connect it to another idea using because or although.",
            "B2": "Now express the same idea in a more formal way.",
        }
        scenario = SCENARIOS.get(scenario_key, SCENARIOS["free"])
        if scenario_key != "free":
            reply = (
                f"A estrutura principal está adequada. Continuando a simulação de {scenario['title'].lower()}: "
                "Could you give me one more detail?"
            )
        else:
            reply = f"A estrutura principal está adequada. {prompts.get(level, prompts['A1'])}"
        exercise = None
    return {
        "reply": reply,
        "corrected_text": corrected,
        "corrections": corrections,
        "exercise": exercise,
        "engine": "Professor integrado offline",
    }


def _local_only_url(url: str) -> bool:
    try:
        return urlparse(url).hostname in {"127.0.0.1", "localhost", "::1"}
    except ValueError:
        return False


def local_tutor(
    message: str,
    url: str,
    model: str,
    level: str,
    objective: str,
    history: list[dict],
    student_context: dict,
    scenario_key: str,
) -> dict:
    if not _local_only_url(url):
        raise ValueError("Por segurança, o Professor Neural aceita somente localhost ou 127.0.0.1.")
    scenario = SCENARIOS.get(scenario_key, SCENARIOS["free"])
    context_json = json.dumps(student_context, ensure_ascii=False)
    system = (
        "Você é um professor particular de inglês para um brasileiro. Seja paciente, direto e didático. "
        f"Nível atual: {level or 'A1'}. Objetivo: {objective or 'conversação geral'}. "
        f"Cenário atual: {scenario['title']}. Você representa: {scenario['role']}. Meta: {scenario['goal']} "
        f"Memória pedagógica local do aluno: {context_json}. "
        "Converse em inglês quando isso ajudar e explique erros em português. Nunca invente que acessou a internet. "
        "Responda SOMENTE como JSON válido, sem markdown, com as chaves: reply, corrected_text, corrections e exercise. "
        "corrections é uma lista de objetos com rule_key e explanation. exercise pode ser null ou um objeto com "
        "rule_key, prompt, options (lista), answer e explanation. Faça no máximo um exercício curto por resposta."
    )
    messages = [{"role": "system", "content": system}]
    for item in history[-6:]:
        if item.get("role") in {"user", "assistant"} and item.get("content"):
            messages.append({"role": item["role"], "content": str(item["content"])[:2000]})
    messages.append({"role": "user", "content": message})
    payload = json.dumps(
        {
            "model": model or "local-model",
            "messages": messages,
            "temperature": 0.35,
            "max_tokens": 1000,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))
    content = result["choices"][0]["message"]["content"].strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE)
    parsed = json.loads(content)
    if not isinstance(parsed, dict) or not str(parsed.get("reply", "")).strip():
        raise ValueError("A IA local retornou uma resposta incompleta.")
    parsed["reply"] = str(parsed["reply"])[:8000]
    parsed["corrected_text"] = str(parsed.get("corrected_text", ""))[:4000]
    parsed["corrections"] = parsed.get("corrections") if isinstance(parsed.get("corrections"), list) else []
    parsed["exercise"] = parsed.get("exercise") if isinstance(parsed.get("exercise"), dict) else None
    parsed["engine"] = "Professor Neural local"
    return parsed


def tutor_response(
    message: str,
    settings: dict[str, str],
    level: str,
    objective: str,
    history: list[dict],
    student_context: dict | None = None,
    scenario_key: str = "free",
) -> dict:
    if settings.get("tutor_engine") != "local_ai":
        return integrated_tutor(message, level, scenario_key)
    try:
        return local_tutor(
            message,
            settings.get("local_ai_url", ""),
            settings.get("local_ai_model", "local-model"),
            level,
            objective,
            history,
            student_context or {},
            scenario_key,
        )
    except (
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
        urllib.error.URLError,
        OSError,
        TimeoutError,
    ) as exc:
        fallback = integrated_tutor(message, level, scenario_key)
        fallback["notice"] = f"A IA local não respondeu; continuei com o Professor integrado. Detalhe: {exc}"
        return fallback


def normalize_exercise_answer(value: str) -> str:
    return re.sub(r"[^a-z0-9']+", " ", value.lower()).strip()
