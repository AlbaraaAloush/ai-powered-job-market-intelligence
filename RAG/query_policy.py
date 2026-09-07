"""Input policy for the job-market assistant.

The assistant is intentionally narrow: it can answer questions grounded in the
selected labour-market postings, but must not turn unrelated, unsafe, or
privacy-invasive requests into a retrieval query.
"""
from __future__ import annotations

import re

_UNSAFE = re.compile(
    r"(?i)\b(?:how (?:to|do i) (?:hack|make a bomb|hurt|kill)|exploit\s+(?:a|the)?\s*(?:server|account|system)|"
    r"malware|ransomware|phishing|stolen password|credit card|doxx|doxing|"
    r"porn|sexual services?|nude|terrorist attack|suicide|self[- ]harm)\b|"
    r"\b(?:كيفية اختراق|صنع قنبلة|إيذاء|قتل|برمجيات خبيثة|كلمات المرور|بطاقات ائتمان|محتوى جنسي|انتحار)\b"
)
_UNRELATED = re.compile(
    r"(?i)\b(?:weather|temperature|sports?|football|recipe|restaurant|flight|visa advice|medical diagnosis|"
    r"legal advice|political campaign|election results|stock price|crypto|mars|astrology)\b|"
    r"\b(?:الطقس|رياضة|وصفة|مطعم|تأشيرة|تشخيص طبي|استشارة قانونية|انتخابات|أسهم|عملات رقمية)\b|المريخ"
)


def classify_question(question: str) -> str | None:
    """Return a refusal reason, or ``None`` when the query is in scope."""
    text = str(question or "").strip()
    if _UNSAFE.search(text):
        return "unsafe_request"
    if _UNRELATED.search(text):
        return "outside_dataset_scope"
    return None


def refusal_text(arabic: bool, reason: str) -> str:
    if arabic:
        if reason == "unsafe_request":
            return "لا أستطيع المساعدة في هذا النوع من الطلبات. أستطيع الإجابة عن أسئلة سوق العمل المبنية على بيانات الوظائف المحددة."
        return "هذا السؤال خارج نطاق البيانات المحددة للوظائف. أستطيع الإجابة عن سوق العمل في قطر والسعودية والإمارات فقط."
    if reason == "unsafe_request":
        return "I can’t help with that type of request. I can answer questions grounded in the selected job-market data."
    return "That question is outside the selected job-market dataset. I can answer questions about the Qatar, Saudi Arabia, and UAE labour markets."
