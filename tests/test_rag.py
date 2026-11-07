import pytest
from services.rag_service import rag_service, LANG_MESSAGES


def test_rag_index_loaded():
    assert rag_service.loaded is True
    assert len(rag_service.chunks) >= 30


def test_rag_search_relevance():
    hits = rag_service.search("When to apply DAP?", k=3, crop="Wheat", fertilizer="DAP")
    assert len(hits) > 0
    sources = [h["source"].lower() for h in hits]
    # dap.md or wheat.md or application-methods should be present
    assert any("dap" in s or "wheat" in s or "application" in s or "practice" in s for s in sources)


def test_rag_fallback_offline(monkeypatch):
    from services.llm_client import llm_client
    monkeypatch.setattr(llm_client, "api_key", "")
    monkeypatch.setattr(llm_client, "client", None)
    # Without Gemini API key, answer() falls back gracefully with relevant passages
    context = {
        "crop": "Wheat",
        "soil": "Loamy",
        "fertilizer": "DAP",
        "confidence": 0.92,
        "nitrogen": 12,
        "phosphorous": 36,
        "potassium": 0,
    }
    res = rag_service.answer("How should I apply DAP?", prediction_context=context, language="en")
    assert res["fallback"] is True
    assert len(res["sources"]) > 0
    assert LANG_MESSAGES["en"]["fallback"] in res["answer"]


def test_rag_multilingual_fallback(monkeypatch):
    from services.llm_client import llm_client
    monkeypatch.setattr(llm_client, "api_key", "")
    monkeypatch.setattr(llm_client, "client", None)
    context = {
        "crop": "Paddy",
        "soil": "Clayey",
        "fertilizer": "Urea",
        "confidence": 0.89,
        "nitrogen": 35,
        "phosphorous": 0,
        "potassium": 0,
    }
    res_te = rag_service.answer("యూరియా ఎప్పుడు వేయాలి?", prediction_context=context, language="te")
    assert res_te["fallback"] is True
    assert LANG_MESSAGES["te"]["fallback"] in res_te["answer"]

    res_hi = rag_service.answer("यूरिया कब डालना चाहिए?", prediction_context=context, language="hi")
    assert res_hi["fallback"] is True
    assert LANG_MESSAGES["hi"]["fallback"] in res_hi["answer"]


def test_rag_live_answer():
    from services.llm_client import llm_client
    if not llm_client.configured:
        pytest.skip("Gemini API key not configured")
    context = {
        "crop": "Wheat",
        "soil": "Loamy",
        "fertilizer": "DAP",
        "confidence": 0.92,
        "nitrogen": 12,
        "phosphorous": 36,
        "potassium": 0,
    }
    res = rag_service.answer("How should I apply DAP?", prediction_context=context, language="en")
    assert res["fallback"] is False
    assert len(res["sources"]) > 0
    assert len(res["answer"]) > 20

