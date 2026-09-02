import pandas as pd
import pytest

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


def test_contract_employment_by_sector_ranks_sector_contract_share():
    rows = [
        ("Technology", "Contract"),
        *(("Technology", "Full-Time") for _ in range(9)),
        ("Consulting", "Contract"),
        ("Consulting", "Contract"),
        ("One-off category", "Contract"),
    ]
    frame = pd.DataFrame(rows, columns=["_sector_norm", "_employment_norm"]).assign(
        job_title="Example role",
        company="Example employer",
        _country="Qatar",
        _timeline="Jun 2026",
        _dump_id="q_jun",
        category=lambda value: value["_sector_norm"],
        skills="",
        salary="",
        description="",
        url="",
        _career_norm="Mid-Level",
    )

    result = build_fast_answer(
        frame,
        "Which sectors rely most heavily on contract employment?",
    )

    assert result is not None
    assert result["intent"] == "employment-by-sector"
    assert "| Consulting | 2 | 2 | 100.0% |" in result["answer"]
    assert "| Technology | 1 | 10 | 10.0% |" in result["answer"]
    assert "One-off category" not in result["answer"]


def test_contract_employment_by_country_ranks_country_contract_share():
    rows = [
        ("Qatar", "Contract"),
        *(("Qatar", "Full-Time") for _ in range(9)),
        ("UAE", "Contract"),
        ("UAE", "Contract"),
    ]
    frame = pd.DataFrame(rows, columns=["_country", "_employment_norm"]).assign(
        job_title="Example role",
        company="Example employer",
        _timeline="Jun 2026",
        _dump_id="jun",
        _sector_norm="Technology",
        category="Technology",
        skills="",
        salary="",
        description="",
        url="",
        _career_norm="Mid-Level",
    )

    result = build_fast_answer(
        frame,
        "Which countries rely most heavily on contract employment?",
    )

    assert result is not None
    assert result["intent"] == "employment-by-country"
    assert "| UAE | 2 | 2 | 100.0% |" in result["answer"]
    assert "| Qatar | 1 | 10 | 10.0% |" in result["answer"]


def test_grouped_employment_answer_explains_when_only_tiny_groups_match():
    frame = pd.DataFrame(
        [("One-off category", "Contract")],
        columns=["_sector_norm", "_employment_norm"],
    ).assign(
        job_title="Example role",
        company="Example employer",
        _country="Qatar",
        _timeline="Jun 2026",
        _dump_id="q_jun",
        category=lambda value: value["_sector_norm"],
        skills="",
        salary="",
        description="",
        url="",
        _career_norm="Mid-Level",
    )

    result = build_fast_answer(frame, "Which sectors rely on contract employment?")

    assert result is not None
    assert "No groups meet the minimum base size in the selected scope." in result["answer"]


def test_unsupported_grouped_career_question_falls_through_to_full_rag():
    result = build_fast_answer(
        _df(),
        "Which sectors have the highest share of senior roles?",
    )

    assert result is None


def test_unsupported_grouped_language_question_falls_through_to_full_rag():
    result = build_fast_answer(
        _df(),
        "Which sectors require Arabic most often?",
    )

    assert result is None


@pytest.mark.parametrize(
    ("prompt", "expected_intent"),
    [
        ("Which sectors rely most on full-time employment?", "employment-by-sector"),
        ("Which sectors rely most on part-time employment?", "employment-by-sector"),
        ("Which sectors rely most on internships?", "employment-by-sector"),
        ("Which sectors rely most on freelance work?", "employment-by-sector"),
        ("Which sectors rely most on temporary employment?", "employment-by-sector"),
        ("Which sectors rely most on remote employment?", "employment-by-sector"),
        ("Which sectors rely most on volunteers?", "employment-by-sector"),
        ("Which sources rely most on contract employment?", "employment-by-source"),
    ],
)
def test_grouped_employment_router_supports_related_patterns(prompt, expected_intent):
    frame = _df().assign(
        _employment_norm=["Full-Time", "Part-Time", "Internship", "Freelance", "Temporary", "Remote"],
        _source=["Bayt", "Bayt", "Bayt", "LinkedIn", "LinkedIn", "LinkedIn"],
    )

    result = build_fast_answer(frame, prompt)

    assert result is not None
    assert result["intent"] == expected_intent
    assert result["answer"].splitlines()[0] != "## Employment types"


@pytest.mark.parametrize(
    "prompt",
    [
        "Which sectors offer the highest salaries?",
        "Which sectors have the most jobs requiring a bachelor's degree?",
        "Which sectors have the highest share of women?",
    ],
)
def test_unsupported_sector_cross_tabs_fall_through_to_full_rag(prompt):
    assert build_fast_answer(_df(), prompt) is None


def test_bayt_linkedin_engineering_comparison_uses_both_sources():
    rows = [
        ("Structural Engineer", "Engineering", "Bayt", "May 2026", "Contract", "Mid-Level"),
        ("Mechanical Engineer", "Engineering", "Bayt", "May 2026", "Full-Time", "Senior"),
        ("Software Engineer", "Technology", "LinkedIn", "Jun 2026", "Full-Time", "Entry-Level"),
        ("Data Analyst", "Technology", "LinkedIn", "Jun 2026", "Full-Time", "Mid-Level"),
    ]
    frame = pd.DataFrame(
        rows,
        columns=[
            "job_title",
            "_sector_norm",
            "_source",
            "_timeline",
            "_employment_norm",
            "_career_norm",
        ],
    ).assign(
        company="Example employer",
        _country="Qatar",
        _dump_id="all",
        category=lambda value: value["_sector_norm"],
        skills="",
        salary="",
        description="",
        url="",
    )

    result = build_fast_answer(
        frame,
        "Compare hiring patterns between Bayt and LinkedIn for engineering jobs.",
    )

    assert result is not None
    assert result["intent"] == "source-comparison"
    assert "| Bayt | 2 |" in result["answer"]
    assert "| LinkedIn | 1 |" in result["answer"]
    assert "3 matching postings" in result["answer"]
    assert "Data Analyst" not in result["answer"]


def test_engineering_comparison_by_source_uses_source_comparison():
    frame = pd.DataFrame(
        [
            ("Structural Engineer", "Engineering", "Bayt", "May 2026", "Contract", "Mid-Level"),
            ("Software Engineer", "Technology", "LinkedIn", "Jun 2026", "Full-Time", "Senior"),
        ],
        columns=[
            "job_title",
            "_sector_norm",
            "_source",
            "_timeline",
            "_employment_norm",
            "_career_norm",
        ],
    ).assign(
        company="Example employer",
        _country="Qatar",
        _dump_id="all",
        category=lambda value: value["_sector_norm"],
        skills="",
        salary="",
        description="",
        url="",
    )

    result = build_fast_answer(frame, "Compare engineering hiring patterns by source.")

    assert result is not None
    assert result["intent"] == "source-comparison"
    assert "| Bayt | 1 |" in result["answer"]
    assert "| LinkedIn | 1 |" in result["answer"]


def test_deterministic_answer_respects_explicit_dashboard_filters():
    result = build_fast_answer(
        _df(),
        "How many total job postings are available?",
        explicit_filters={"sector": "Technology", "career_level": "Entry-Level"},
    )

    assert result is not None
    assert "**4**" in result["answer"]
    assert "4 postings" in result["scope"]
