import pandas as pd

from fast_answers import build_fast_answer, canonical_skill


def _df():
    rows = [
        ("Data Analyst", "A", "Qatar", "May 2026", "Technology", "SQL; Python; Communication skills", "q_may"),
        ("Data Scientist", "B", "Qatar", "Jun 2026", "Technology", "Python; Machine Learning; Data Analysis", "q_jun"),
        ("Data Analyst", "C", "UAE", "May 2026", "Technology", "SQL; Power BI; communication", "u_may"),
        ("AI Engineer Graduate", "D", "UAE", "Jun 2026", "Engineering", "Python; Machine Learning; Communication", "u_jun"),
        ("Software Engineer Graduate", "E", "Saudi Arabia", "May 2026", "Technology", "Python; Git; Communication", "s_may"),
        ("Construction Manager", "F", "Saudi Arabia", "Jun 2026", "Construction", "Leadership; Project Management", "s_jun"),
    ]
    return pd.DataFrame(rows, columns=[
        "job_title", "company", "_country", "_timeline", "_sector_norm", "skills", "_dump_id",
    ]).assign(category=lambda frame: frame["_sector_norm"], salary="", description="", url="", _career_norm="Entry-Level")


def test_skill_normalization_merges_case_and_wording_variants():
    assert canonical_skill("communication skills") == "Communication"
    assert canonical_skill("Communication") == "Communication"
    assert canonical_skill("data analysis") == "Data Analysis"


def test_total_count_is_deterministic():
    result = build_fast_answer(_df(), "How many total job postings are available?")
    assert result is not None
    assert "**6**" in result["answer"]
    assert result["intent"] == "count"


def test_each_country_resets_stale_country_context():
    history = [{"role": "user", "content": "Show data roles in Qatar"}]
    result = build_fast_answer(_df(), "Count data analyst jobs in each country.", history)
    assert result is not None
    assert "Qatar" in result["answer"] and "UAE" in result["answer"]
    assert "| Qatar | 1 |" in result["answer"]
    assert "| UAE | 1 |" in result["answer"]


def test_referential_followup_inherits_country_but_not_global_postings():
    history = [{"role": "user", "content": "Which skills appear most often in data roles in Qatar?"}]
    result = build_fast_answer(_df(), "So as a recent AI graduate, what skills must I have?", history)
    assert result is not None
    assert "Qatar" in result["scope"]
    assert "6 postings" not in result["answer"]


def test_repeated_followup_keeps_recent_explicit_country_scope():
    history = [
        {"role": "user", "content": "Which skills appear most often in data roles in Qatar?"},
        {"role": "assistant", "content": "Python and SQL are common."},
        {"role": "user", "content": "So as a recent AI graduate, what skills must I have?"},
        {"role": "assistant", "content": "Prioritize Python."},
    ]
    result = build_fast_answer(_df(), "So as a recent AI graduate, what skills must I have?", history)
    assert result is not None and "Qatar" in result["scope"]


def test_skill_answer_has_no_duplicate_capitalization_or_internal_citation():
    result = build_fast_answer(_df(), "Which skills appear most often in data roles?")
    assert result is not None
    assert "Based on **3 matching postings**" in result["answer"]
    assert result["answer"].count("**Communication**") <= 1
    assert "DATASET-1" not in result["answer"]
    assert "BM25" not in result["answer"]


def test_no_result_job_search_does_not_pad_with_unrelated_jobs():
    result = build_fast_answer(_df(), "Find underwater archaeology jobs in Qatar.")
    assert result is not None
    assert result["intent"] == "job-search"
    assert "No matching vacancies" in result["answer"]
    assert result["evidence"] == []


def test_declining_sector_answer_uses_correct_month_order():
    result = build_fast_answer(_df(), "Which sectors experienced declining demand?")
    assert result is not None
    assert "| Sector | May 2026 | Jun 2026 |" in result["answer"]
