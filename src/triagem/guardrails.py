"""Regras locais compartilhadas pelo terminal e pela interface."""

import re
import unicodedata

MAX_CHARS = 3000
SCOPE = "Posso ajudar com a triagem de dengue, chikungunya e zika. Qual é sua dúvida sobre essas doenças?"
GREETING = "Olá! O que você está sentindo ou gostaria de saber sobre dengue, chikungunya ou zika?"
NO_EVIDENCE = "Não encontrei nos manuais informação suficiente para orientar com segurança. Se você está com sintomas, procure uma unidade de saúde para avaliação."
ALARM = ("Se o sinal descrito está acontecendo agora, procure um serviço de urgência imediatamente. "
         "Em uma emergência no Brasil, ligue para o SAMU (192).")
ALARM_TERMS = re.compile(
    r"\b(?:nao (?:consigo|consegue) respirar|falta de ar|dificuldade (?:para|de) respirar|"
    r"vomit(?:os? persistentes?|ando (?:sangue|sem parar)|ei sangue)|sangue nas fezes|"
    r"(?:gengiva|nariz) (?:esta |ta )?sangrando|sangramento (?:na gengiva|no nariz)|"
    r"dor (?:abdominal|na barriga) (?:muito )?(?:forte|intensa)|desmaiei)\b"
)
INSTRUCTION_OVERRIDE = re.compile(
    r"\b(?:ignore|ignorar|desconsidere|esqueca|ignore all)\b.{0,45}"
    r"\b(?:instrucoes|regras|instructions|prompt)\b|\b(?:revele|mostre|exiba)\b.{0,30}"
    r"\b(?:prompt de sistema|chave (?:de |da )?api)\b", re.S
)
DOSE = re.compile(r"\b\d+(?:[,.]\d+)?\s*(?:mg|mcg|µg|ml|comprimidos?|gotas?)\b", re.I)
DIAGNOSIS = re.compile(
    r"\b(?:voce (?:tem|esta com)|(?:seu |o )?diagnostico (?:e|confirmado (?:e|de))) "
    r"(?:dengue|chikungunya|zika)\b"
)
REFERENCE = r"\[[^\[\]\n]+, p\. \d+\]"


def normalize(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


def screen_input(text: str) -> str | None:
    normalized = normalize(text)
    for match in ALARM_TERMS.finditer(normalized):
        clause = re.split(r"[,.;!?\n]|\b(?:mas|porem|agora)\b", normalized[:match.start()])[-1]
        if not re.search(r"\b(?:sem|nao|nego|nunca)\s+(?:(?:tenho|tive|estou com|apresento)\s+)?$", clause):
            return ALARM
    if not text.strip() or len(text) > MAX_CHARS:
        return f"Descreva sua dúvida em uma mensagem de até {MAX_CHARS} caracteres."
    if INSTRUCTION_OVERRIDE.search(normalized):
        return SCOPE
    return None


def screen_answer(answer: str, context: str) -> str:
    available = set(re.findall("^(" + REFERENCE + ")", context, re.M))
    cited = set(re.findall(r"\[[^\[\]\n]*\]", answer))
    if not cited or not cited <= available or DOSE.search(answer) or DIAGNOSIS.search(normalize(answer)):
        return NO_EVIDENCE
    return answer.strip()
