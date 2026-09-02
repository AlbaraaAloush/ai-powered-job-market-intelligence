"""Evidence contracts shared by generation, tracing and live evaluation."""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict

PROMPT_VERSION = "rag-grounded-v3"
INDEX_SCHEMA_VERSION = "qdrant-job-v3"

_CITATION_RE = re.compile(r"\[(JOB-[A-Za-z0-9-]+|SQL-\d+|DATASET-\d+)\]")
_NUMBER_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{3,}(?:\.\d+)?)(?![\w.])")
_INJECTION_RE = re.compile(
    r"(?i)(ignore (?:all |the )?(?:previous|prior|system) instructions|system prompt|"
    r"developer message|reveal (?:your |the )?(?:prompt|secret)|act as|jailbreak|do not cite|"
    r"تجاهل (?:جميع )?التعليمات|اعرض (?:رسالة النظام|التعليمات|المعلومات السرية)|كشف (?:رسالة النظام|السر))"
)


def stable_source_id(result: dict) -> str:
    raw = str(result.get("source_id") or result.get("metadata", {}).get("source_id") or "unknown")
    safe = re.sub(r"[^A-Za-z0-9-]", "", raw)
    return "JOB-" + (safe[:36] or "unknown")


def sanitize_document(text: str) -> tuple[str, bool]:
    """Retrieved text is untrusted data. Flag instruction-like content without executing it."""
    detected = bool(_INJECTION_RE.search(text or ""))
    cleaned = (text or "").replace("<", "‹").replace(">", "›")
    if detected:
        cleaned = "[POTENTIAL PROMPT INJECTION REMOVED FROM SOURCE] " + _INJECTION_RE.sub("[REMOVED]", cleaned)
    return cleaned, detected


def is_prompt_injection(text: str) -> bool:
    return bool(_INJECTION_RE.search(text or ""))


@dataclass
class ValidationResult:
    passed: bool
    citations: list[str]
    invalid_citations: list[str]
    unsupported_numbers: list[str]
    reason: str = ""

    def to_dict(self):
        return asdict(self)


def validate_answer(answer: str, context: str, valid_source_ids: set[str]) -> ValidationResult:
    citations = _CITATION_RE.findall(answer or "")
    invalid = sorted({c for c in citations if c not in valid_source_ids})
    context_numbers = {n.replace(",", "") for n in _NUMBER_RE.findall(context or "")}
    answer_numbers = {n.replace(",", "") for n in _NUMBER_RE.findall(answer or "")}
    unsupported = sorted(answer_numbers - context_numbers)
    evidence_answer = bool((answer or "").strip()) and "insufficient evidence" not in (answer or "").lower()
    reason = ""
    if evidence_answer and valid_source_ids and not citations:
        reason = "answer_has_no_citation"
    elif invalid:
        reason = "invalid_citation"
    elif unsupported:
        reason = "unsupported_numerical_claim"
    return ValidationResult(not reason, citations, invalid, unsupported, reason)


def abstention_text(arabic: bool, reason: str = "insufficient_evidence") -> str:
    if arabic:
        return "لا توجد أدلة كافية في البيانات المحددة للإجابة بثقة. يرجى توسيع نطاق البيانات أو إعادة صياغة السؤال."
    return "There is insufficient evidence in the selected data to answer confidently. Please broaden the dataset scope or rephrase the question."
