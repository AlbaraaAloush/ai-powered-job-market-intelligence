import pandas as pd

from analytics import AnalyticsEngine
from rag_engine import RAGEngine


def _engine():
    engine = RAGEngine.__new__(RAGEngine)
    engine.analytics = AnalyticsEngine(pd.DataFrame({
        "_country": ["Qatar", "UAE", "Saudi Arabia"],
        "_timeline": ["May 2026", "Jun 2026", "Jun 2026"],
    }))
    return engine


def test_planning_extracts_scope_without_an_llm_client():
    engine = _engine()  # deliberately has no _internal_client
    result = engine._normalize_decomposed("Find machine-learning roles in Qatar in Jun 2026")
    assert result["filters"] == {"_country": "Qatar", "_timeline": "Jun 2026"}
    assert result["semantic_query"] == "Find machine-learning roles in Qatar in Jun 2026"


def test_multi_country_comparison_does_not_collapse_to_one_country():
    result = _engine()._normalize_decomposed("Compare technology roles in Qatar and the UAE")
    assert "_country" not in result["filters"]


def test_new_standalone_question_does_not_inherit_stale_country():
    history = [{"role": "user", "content": "Show data roles in Qatar"}]
    result = _engine()._normalize_decomposed("Which companies posted the most jobs?", history)
    assert "_country" not in result["filters"]

