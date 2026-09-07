"""Evaluate the user-visible HTTP chat pipeline for quality, safety, and speed."""
from __future__ import annotations

import argparse
import json
import re
import statistics
import time
import uuid
from pathlib import Path
from typing import Any

import requests


ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
DEBUG_JUNK = ("RRF fusion", "BM25", "Cross-encoder reranker", "DATASET-1", "SQL-1", "[Error:")


def visible_answer(raw: str) -> str:
    """Mirror the citation cleanup performed by the React message renderer."""
    cleaned = re.sub(r"^\s*Sources?:.*$", "", raw, flags=re.IGNORECASE | re.MULTILINE)
    cleaned = re.sub(r"\[(?:DATASET|SQL|JOB)-[^\]]+\]", "", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def stream_answer(
    base: str,
    question: str,
    session_id: str,
    model: str,
    dump_ids: list[str] | None = None,
    timeout: float = 45,
) -> dict[str, Any]:
    payload = {
        "question": question,
        "session_id": session_id,
        "model": model,
        "filters": {},
    }
    if dump_ids is not None:
        payload['dump_ids'] = dump_ids
    answer: list[str] = []
    retrieval: dict[str, Any] = {}
    started = time.perf_counter()
    with requests.post(f"{base}/api/chat", json=payload, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        # A tiny chunk size measures when the browser receives [DONE], not
        # when requests' default 512-byte buffer happens to fill/close.
        for line in response.iter_lines(chunk_size=1, decode_unicode=True):
            if line == "data: [DONE]":
                break
            if not line or not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            if event.get("type") == "token":
                answer.append(event.get("token", ""))
            elif event.get("type") == "retrieval":
                retrieval = event.get("info", {})
    return {
        "answer": visible_answer("".join(answer).strip()),
        "retrieval": retrieval,
        "latency_s": round(time.perf_counter() - started, 3),
    }


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * pct
    lower, upper = int(index), min(int(index) + 1, len(ordered) - 1)
    fraction = index - lower
    return round(ordered[lower] * (1 - fraction) + ordered[upper] * fraction, 3)


def validate(case: dict[str, Any], result: dict[str, Any], total_jobs: int) -> list[str]:
    answer = result["answer"]
    folded = answer.casefold()
    retrieval = result["retrieval"]
    failures: list[str] = []

    if len(answer) < int(case.get("min_chars", 20)):
        failures.append("answer is empty or too short")
    for marker in DEBUG_JUNK:
        if marker.casefold() in folded:
            failures.append(f"leaks internal/debug marker: {marker}")

    expected_language = case.get("language")
    has_arabic = bool(ARABIC_RE.search(answer))
    if expected_language == "ar" and not has_arabic:
        failures.append("answer is not Arabic")
    if expected_language == "en" and has_arabic:
        failures.append("English answer unexpectedly contains Arabic prose")

    for value in case.get("contains_all", []):
        if str(value).casefold() not in folded:
            failures.append(f"missing required text: {value}")
    any_values = case.get("contains_any", [])
    if any_values and not any(str(value).casefold() in folded for value in any_values):
        failures.append(f"missing all alternative texts: {any_values}")
    for value in case.get("not_contains", []):
        if str(value).casefold() in folded:
            failures.append(f"contains forbidden text: {value}")

    expected_mode = case.get("expected_mode")
    if expected_mode:
        expected_modes = {expected_mode} if isinstance(expected_mode, str) else set(expected_mode)
        actual_mode = retrieval.get("mode")
        if actual_mode not in expected_modes:
            failures.append(f"mode {actual_mode!r} not in {sorted(expected_modes)}")

    if case.get("expect_total") and f"{total_jobs:,}" not in answer and str(total_jobs) not in answer:
        failures.append(f"answer does not contain exact total {total_jobs:,}")
    if case.get("must_have_evidence"):
        evidence_count = retrieval.get("evidence_count")
        semantic_hits = retrieval.get("semantic_hits", [])
        if not isinstance(evidence_count, int) or evidence_count <= 0:
            failures.append("missing positive evidence count")
        if case.get("must_show_examples") and not semantic_hits:
            failures.append("missing evidence examples")
    if case.get("expect_abstention"):
        abstention_terms = (
            "no data", "outside the dataset scope", "outside the selected job-market dataset", "cannot give a reliable answer",
            "insufficient evidence", "لا توجد بيانات", "لا توجد أدلة كافية",
            "خارج نطاق البيانات", "لا أستطيع", "لا يمكنني",
        )
        if not any(term.casefold() in folded for term in abstention_terms):
            failures.append("expected a clear abstention/scope limitation")

    max_latency = float(case.get("max_latency_s", 2.0))
    if result["latency_s"] > max_latency:
        failures.append(f"latency {result['latency_s']}s exceeds {max_latency}s")
    if not retrieval.get("trace_id"):
        failures.append("missing feedback trace id")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--benchmark", type=Path, default=Path(__file__).parent / "evaluation" / "bilingual_benchmark.json")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "reports" / "live_evaluation.json")
    parser.add_argument("--ids", nargs="*", help="Run only selected benchmark case IDs")
    parser.add_argument("--timeout", type=float, default=45)
    parser.add_argument("--delay", type=float, default=0.0, help="Delay between cases (use 2.1 to stay below the API's 30/minute limit)")
    args = parser.parse_args()

    benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
    datasets = requests.get(f"{args.base_url}/api/datasets", timeout=30).json()
    total_jobs = sum(int(item.get("count", 0)) for item in datasets.get("dumps", []))
    models = requests.get(f"{args.base_url}/api/models", timeout=30).json()
    model = models["default"]
    selected_ids = set(args.ids or [])
    cases = [case for case in benchmark["questions"] if not selected_ids or case["id"] in selected_ids]

    sessions: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    for index, case in enumerate(cases, 1):
        if index > 1 and args.delay > 0:
            time.sleep(args.delay)
        conversation = case.get("conversation", case["id"])
        session_id = sessions.setdefault(conversation, uuid.uuid4().hex)
        try:
            result = stream_answer(
                args.base_url, case["question"], session_id, model,
                dump_ids=case.get("dump_ids"), timeout=args.timeout,
            )
            failures = validate(case, result, total_jobs)
            row = {
                **case,
                "passed": not failures,
                "failures": failures,
                "latency_s": result["latency_s"],
                "answer": result["answer"],
                "mode": result["retrieval"].get("mode"),
                "scope": result["retrieval"].get("scope"),
                "evidence_count": result["retrieval"].get("evidence_count"),
                "evidence_examples": len(result["retrieval"].get("semantic_hits", [])),
                "trace_id": result["retrieval"].get("trace_id"),
            }
        except Exception as exc:
            row = {**case, "passed": False, "failures": [f"request failed: {type(exc).__name__}: {exc}"], "latency_s": args.timeout}
        rows.append(row)
        print(f"[{index:02}/{len(cases)}] {'PASS' if row['passed'] else 'FAIL'} {case['id']} ({row['latency_s']}s)", flush=True)

    latencies = [float(row["latency_s"]) for row in rows]
    grouped: dict[str, dict[str, int]] = {}
    for row in rows:
        key = f"{row['language']}:{row['category']}"
        grouped.setdefault(key, {"passed": 0, "total": 0})
        grouped[key]["total"] += 1
        grouped[key]["passed"] += int(row["passed"])
    report = {
        "benchmark_version": benchmark["version"],
        "live_pipeline": True,
        "base_url": args.base_url,
        "model": model,
        "total_jobs": total_jobs,
        "passed": sum(int(row["passed"]) for row in rows),
        "total": len(rows),
        "latency_s": {
            "median": round(statistics.median(latencies), 3) if latencies else 0,
            "p95": percentile(latencies, 0.95),
            "max": round(max(latencies), 3) if latencies else 0,
        },
        "groups": grouped,
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{report['passed']}/{report['total']} passed; p95={report['latency_s']['p95']}s -> {args.output}")
    raise SystemExit(0 if report["passed"] == report["total"] else 1)


if __name__ == "__main__":
    main()
