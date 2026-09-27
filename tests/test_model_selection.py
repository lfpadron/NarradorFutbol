from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from src.narrative import narrator, review_report, tone_comparison
from src.narrative.config import SUPPORTED_MODELS
from src.narrative_v2 import narrator_v2
from src.narrative_v2.section_builder import STYLE_CONTEXT_KEYS
from src.reports import report_builder
from src.scouting import scouting_v2


@pytest.fixture
def api_calls(monkeypatch: pytest.MonkeyPatch) -> Mock:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    # An explicit selection must win over server configuration without modifying it.
    monkeypatch.setenv("OPENAI_MODEL", "server-default")
    create = Mock(return_value=SimpleNamespace(output_text="Home 1-0 Away"))
    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    for module in (narrator, narrator_v2, scouting_v2):
        monkeypatch.setattr(module, "OpenAI", Mock(return_value=client))
    context = {key: [] for keys in STYLE_CONTEXT_KEYS.values() for key in keys}
    context.update(
        match_summary={"home_team_name": "Home", "away_team_name": "Away", "home_score": 1, "away_score": 0},
        validation={"status": "PASS"},
        shot_summary={},
    )
    for module in (narrator, narrator_v2, tone_comparison, review_report, report_builder):
        monkeypatch.setattr(module, "build_ai_match_context", lambda match_id: context)
    monkeypatch.setattr(report_builder, "_get_match_metadata", lambda match_id: {})
    return create


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("route", ["narrator", "narrator_v2", "tones", "styles", "review", "report"])
def test_model_selection_reaches_every_generation_without_changing_prompts(api_calls, language, route):
    prompts = []
    for model in SUPPORTED_MODELS:
        api_calls.reset_mock()
        kwargs = {"use_api": True, "language": language, "model": model}
        if route == "narrator":
            result = narrator.generate_match_narrative(1, "television", **kwargs)
            assert result["model"] == model
        elif route == "narrator_v2":
            result = narrator_v2.generate_specialized_narrative(1, "television", **kwargs)
            assert result["model"] == model
        elif route == "tones":
            tone_comparison.compare_tones(1, **kwargs)
        elif route == "styles":
            narrator_v2.compare_specialized_styles(1, **kwargs)
        elif route == "review":
            review_report.build_review_report(1, **kwargs)
        else:
            result = report_builder.build_match_report(1, **kwargs)
            assert result["narrative"]["model"] == model
        assert api_calls.call_count == (5 if route in {"tones", "styles", "review"} else 1)
        for call in api_calls.call_args_list:
            assert call.kwargs["model"] == model
            if model.startswith("gpt-6-"):
                assert "temperature" not in call.kwargs
            else:
                assert call.kwargs["temperature"] == (0.35 if route in {"narrator_v2", "styles"} else 0.4)
        prompts.append([call.kwargs["input"] for call in api_calls.call_args_list])
    assert prompts[0] == prompts[1] == prompts[2]
    assert ("English" if language == "en" else "español") in prompts[0][0]


@pytest.fixture
def tactical_profiles(monkeypatch):
    def profile(match_id, player_id):
        return {
            "player_name": f"Player {player_id}",
            "player_id": player_id,
            "match_id": match_id,
            "archetype": "Organizador",
            "primary_archetype": {"name": "Organizador", "score": 80, "metrics": ["passes"]},
            "secondary_archetype": {"name": "Finalizador", "score": 45},
            "strengths": [],
            "weaknesses": [],
            "warnings": [],
        }

    monkeypatch.setattr(scouting_v2, "build_tactical_profile", profile)


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("comparative", [False, True])
def test_scouting_model_changes_only_narration(api_calls, tactical_profiles, language, comparative):
    args = (1, 10, 2, 20) if comparative else (1, 10)
    baseline = scouting_v2.generate_scouting_v2(*args, language=language)
    assert not api_calls.called  # Preserve existing local callers.
    prompts = []
    for model in SUPPORTED_MODELS:
        result = scouting_v2.generate_scouting_v2(*args, language=language, use_api=True, model=model)
        assert result["model"] == model
        assert result["status"] == "generated"
        assert result["narrative_markdown"] == "Home 1-0 Away"
        for key in ("profile_a", "profile_b", "comparison", "radar_metrics", "context_summary"):
            assert result[key] == baseline[key]
        call = api_calls.call_args.kwargs
        assert call["model"] == model
        assert ("temperature" in call) == (model == "gpt-4o-mini")
        assert baseline["narrative_markdown"] in call["input"]
        prompts.append(call["input"])
    assert prompts[0] == prompts[1] == prompts[2]
    assert ("English" if language == "en" else "español") in prompts[0]


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("failure", ["missing_key", "api_error", "empty_response"])
def test_scouting_preserves_local_fallback(api_calls, tactical_profiles, monkeypatch, language, failure):
    baseline = scouting_v2.generate_scouting_v2(1, 10, language=language)
    if failure == "missing_key":
        monkeypatch.delenv("OPENAI_API_KEY")
    elif failure == "api_error":
        api_calls.side_effect = RuntimeError("unavailable")
    else:
        api_calls.return_value = SimpleNamespace(output_text=" ")
    result = scouting_v2.generate_scouting_v2(1, 10, language=language, use_api=True, model="gpt-6-astra")
    assert result["narrative_markdown"] == baseline["narrative_markdown"]
    assert result["model"] == "local-tactical-profile-v2"
    assert result["status"] == "fallback"
    assert result["warnings"]
    assert ("local tactical profile" if language == "en" else "perfil táctico local") in result["warnings"][0]


@pytest.mark.parametrize("module,style", [(narrator, "television"), (narrator_v2, "television")])
def test_existing_callers_keep_configured_default(api_calls, module, style):
    generate = getattr(module, "generate_match_narrative", None) or module.generate_specialized_narrative
    result = generate(1, style)
    assert api_calls.call_args.kwargs["model"] == "server-default"
    assert result["model"] == "server-default"


def _model_selector_app():
    import streamlit as st

    from src.ui.i18n import LANGUAGE_SESSION_KEY, install_streamlit_i18n
    from src.ui.model_selector import render_model_selector

    install_streamlit_i18n()
    st.radio("Language", ["es", "en"], key=LANGUAGE_SESSION_KEY)
    for key in ("narrative_model", "narrative_v2_model", "scouting_v2_model"):
        render_model_selector(key)


@pytest.mark.parametrize("default", ["gpt-4o-mini", "gpt-6-astra", "gpt-6-luna", "custom-server-model"])
def test_dropdowns_are_independent_and_localized(monkeypatch, default):
    monkeypatch.setenv("OPENAI_MODEL", default)
    app = AppTest.from_function(_model_selector_app).run()
    assert not app.exception
    assert len(app.selectbox) == 3
    expected_default = default if default in SUPPORTED_MODELS else "gpt-4o-mini"
    for selector in app.selectbox:
        assert selector.label == "Modelo de IA"
        assert selector.options == ["gpt-4o-mini", "GPT-6 Astra", "GPT-6 Luna"]
        assert selector.value == expected_default
    app.selectbox(key="narrative_model").select("gpt-6-astra")
    app.selectbox(key="narrative_v2_model").select("gpt-6-luna")
    app.selectbox(key="scouting_v2_model").select("gpt-4o-mini")
    app.run()
    app.radio[0].set_value("en").run()
    assert not app.exception
    assert [selector.label for selector in app.selectbox] == ["AI model"] * 3
    assert [selector.value for selector in app.selectbox] == ["gpt-6-astra", "gpt-6-luna", "gpt-4o-mini"]
    app.radio[0].set_value("es").run()
    assert not app.exception
    assert [selector.value for selector in app.selectbox] == ["gpt-6-astra", "gpt-6-luna", "gpt-4o-mini"]
