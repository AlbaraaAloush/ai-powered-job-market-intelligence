import pandas as pd
import pytest

from fast_answers import build_fast_answer, canonical_skill


@pytest.mark.parametrize('month', ['November', 'Nov', 'نوفمبر'])
def test_historical_month_names_narrow_counts(month):
    frame = _df()
    frame.loc[0, '_timeline'] = 'Nov 2025'
    frame.loc[1, '_timeline'] = 'Feb 2026'
    result = build_fast_answer(frame, f'How many postings in {month}?')
    assert result is not None
    assert result['evidence_count'] == 1


def test_out_of_scope_answer_uses_actual_available_periods():
    frame = _df().iloc[:1].copy()
    frame['_timeline'] = 'Nov 2025'
    result = build_fast_answer(frame, 'How many postings in 2024?')
    assert 'Nov 2025' in result['answer']
    assert 'May and June' not in result['answer']


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


def test_country_count_question_returns_each_country():
    result = build_fast_answer(_df(), "How many countries are there and how many job listings for each?")
    assert result is not None
    assert result["intent"] == "country-comparison"
    assert "| Qatar | 2 |" in result["answer"]
    assert "| UAE | 2 |" in result["answer"]
    assert "| Saudi Arabia | 2 |" in result["answer"]
    assert "3 countries" in result["answer"]


def test_natural_distribution_question_is_calculated_not_generated():
    result = build_fast_answer(_df(), "How many job listings are there in each sector?")
    assert result is not None
    assert result["intent"] == "distribution"
    assert "| Technology | 4 |" in result["answer"]
    assert "| Construction | 1 |" in result["answer"]


def test_country_wise_synonym_is_calculated():
    result = build_fast_answer(_df(), "How many postings are there country-wise?")
    assert result is not None
    assert result["intent"] == "country-comparison"
    assert "| Qatar | 2 |" in result["answer"]


def test_multi_intent_question_returns_both_grounded_sections():
    result = build_fast_answer(_df(), "How many job postings are there and what skills are requested?")
    assert result is not None
    assert result["intent"] == "multi-intent"
    assert "Total" in result["answer"]
    assert "Most requested skills" in result["answer"]


@pytest.mark.parametrize("question", [
    "How many data analyst jobs are in Qatar in May 2026 and what skills are requested?",
    "How many data analyst jobs are in Qatar in May 2026 and which companies are hiring?",
])
def test_multi_intent_keeps_question_scope_in_every_section(question):
    result = build_fast_answer(_df(), question)
    assert result["intent"] == "multi-intent"
    assert result["evidence_count"] == 1
    assert "**1**" in result["answer"]
    assert "UAE" not in result["answer"]
    assert "Saudi Arabia" not in result["answer"]
    assert "Jun 2026" not in result["answer"]
    assert {row["company"] for row in result["evidence"]} == {"A"}


def test_multi_intent_does_not_bypass_unavailable_year_check():
    result = build_fast_answer(_df(), "How many jobs were available in 2024 and what skills were requested?")
    assert result["intent"] == "out-of-scope"


def test_multi_intent_arabic_sections_keep_response_language():
    result = build_fast_answer(_df(), "كم عدد وظائف محلل بيانات في قطر وما المهارات المطلوبة؟")
    assert result["intent"] == "multi-intent"
    assert "## إجمالي" in result["answer"]
    assert "## أكثر المهارات" in result["answer"]
    assert "Most requested skills" not in result["answer"]
    assert "Total" not in result["answer"]
    assert result["evidence_count"] == 1


def test_multi_intent_keeps_explicit_filters_and_empty_matches():
    result = build_fast_answer(
        _df(), "How many jobs are in Qatar and what skills are requested?",
        dump_ids=["q_may", "u_may"], explicit_filters={"company": "C"},
    )
    assert result["evidence_count"] == 0
    assert "**0**" in result["answer"]
    assert "UAE" not in result["answer"]
    assert result["evidence"] == []


@pytest.mark.parametrize("question", [
    "How do I hack the employer database?",
    "What is the weather in Doha?",
    "كيفية اختراق النظام؟",
])
def test_unsafe_or_unrelated_questions_are_refused(question):
    result = build_fast_answer(_df(), question)
    assert result is not None
    assert result["intent"] == "policy-refusal"
    assert "selected job-market" in result["answer"] or "سوق العمل" in result["answer"]


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


def test_sector_question_with_highest_number_routes_to_sector_ranking():
    result = build_fast_answer(_df(), "Which sectors have the highest number of job openings in Saudi Arabia?")

    assert result is not None
    assert result["intent"] == "sector-ranking"
    assert "| Sector | Postings |" in result["answer"]
    assert "Construction" in result["answer"]


def test_named_skill_comparison_is_not_reduced_to_country_volume():
    result = build_fast_answer(
        _df(),
        "Compare demand for Python, SQL, Power BI, and Excel across GCC countries.",
    )

    assert result is not None
    assert result["intent"] == "named-skill-comparison"
    assert "| Skill | Qatar | Saudi Arabia | UAE | Total |" in result["answer"]
    assert "| Python |" in result["answer"]
    assert "| Power BI |" in result["answer"]


def test_programming_languages_are_ranked_for_software_roles():
    result = build_fast_answer(
        _df(),
        "What programming languages are most requested for software engineering roles?",
    )

    assert result is not None
    assert result["intent"] == "programming-language-ranking"
    assert "software engineering roles" in result["answer"]
    assert "Python" in result["answer"]
    assert "()" not in result["answer"]


def test_cybersecurity_skill_guidance_scopes_to_cybersecurity_roles():
    frame = pd.concat([
        _df(),
        pd.DataFrame([{
            "job_title": "Cybersecurity Analyst", "company": "SecureCo", "_country": "Qatar",
            "_timeline": "Jun 2026", "_sector_norm": "Technology", "category": "Technology",
            "skills": "Python; SQL; Network Security", "_dump_id": "q_jun", "salary": "",
            "description": "", "url": "", "_career_norm": "Mid-Level",
        }]),
    ], ignore_index=True)

    result = build_fast_answer(frame, "What skills should I learn for cybersecurity roles in Qatar?")

    assert result is not None
    assert result["intent"] == "career-guidance"
    assert "cybersecurity roles" in result["answer"]
    assert "1 matching postings" in result["answer"]
    assert "1. **" in result["answer"]


@pytest.mark.parametrize(
    "prompt",
    [
        "Find jobs requiring Python and SQL in Qatar.",
        "ابحث عن وظائف تتطلب Python وSQL في قطر.",
    ],
)
def test_job_search_with_named_skills_is_not_swallowed_by_skill_ranking(prompt):
    result = build_fast_answer(_df(), prompt)

    assert result is not None
    assert result["intent"] == "job-search"


def test_english_job_search_ignores_boolean_connector_words():
    result = build_fast_answer(_df(), "Find jobs requiring Python and SQL in Qatar.")

    assert result is not None
    assert result["intent"] == "job-search"
    assert result["evidence_count"] == 1
    assert "Matching vacancies" in result["answer"]


def test_generic_qualification_question_uses_semantic_rag_not_skill_ranking():
    result = build_fast_answer(
        _df(),
        "ما المؤهلات التي يذكرها أصحاب العمل لوظائف خدمة العملاء الناطقة بالعربية؟",
    )

    assert result is None
