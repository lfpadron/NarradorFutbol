"""Generate AI or local fallback match narratives."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from openai import OpenAI, OpenAIError

from src.analytics.ai_context import build_ai_match_context
from src.ingestion.utils import to_jsonable
from src.narrative.config import get_openai_api_key, get_openai_model, sampling_parameters, validate_tone
from src.narrative.fact_guard import validate_narrative_against_context
from src.narrative.prompt_builder import build_match_narrative_prompt
from src.narrative.templates import generate_fallback_narrative
from src.ui.i18n import is_english


def generate_match_narrative(
    match_id: int,
    tone: str = "cronica_emocionante",
    use_api: bool = True,
    language: str = "es",
    model: str | None = None,
) -> dict[str, Any]:
    tone = validate_tone(tone)
    context = build_ai_match_context(match_id)
    model = model or get_openai_model()
    warnings: list[str] = []
    status = "fallback"

    api_key = get_openai_api_key()
    if use_api and api_key:
        prompt = build_match_narrative_prompt(context, tone, language=language)
        try:
            client = OpenAI(api_key=api_key)
            response = client.responses.create(
                model=model,
                input=prompt,
                **sampling_parameters(model, temperature=0.4),
            )
            narrative_markdown = _extract_response_text(response).strip()
            status = "generated"
        except OpenAIError as exc:
            narrative_markdown = generate_fallback_narrative(context, tone, language=language)
            warnings.append(
                _warning(
                    "OpenAI API falló; se usó fallback local.", "OpenAI API failed; local fallback used.", language, exc
                )
            )
        except Exception as exc:  # Defensive fallback for SDK/network edge cases.
            narrative_markdown = generate_fallback_narrative(context, tone, language=language)
            warnings.append(
                _warning(
                    "No se pudo generar con API; se usó fallback local.",
                    "Could not generate with API; local fallback used.",
                    language,
                    exc,
                )
            )
    else:
        narrative_markdown = generate_fallback_narrative(context, tone, language=language)
        if use_api and not api_key:
            warnings.append(
                "OPENAI_API_KEY is not configured; local narrative used."
                if is_english(language)
                else "OPENAI_API_KEY no está configurada; se usó narrativa local."
            )
        elif not use_api:
            warnings.append(
                "OpenAI API use is disabled; local narrative used."
                if is_english(language)
                else "Uso de OpenAI API desactivado; se usó narrativa local."
            )

    warnings.extend(validate_narrative_against_context(narrative_markdown, context))
    summary = context.get("match_summary", {})
    return to_jsonable(
        {
            "match_id": match_id,
            "tone": tone,
            "language": language,
            "model": model,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "narrative_markdown": narrative_markdown,
            "warnings": warnings,
            "context_summary": {
                "home_team_name": summary.get("home_team_name"),
                "away_team_name": summary.get("away_team_name"),
                "home_score": summary.get("home_score"),
                "away_score": summary.get("away_score"),
            },
        }
    )


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text)
    output = getattr(response, "output", None)
    if output:
        chunks: list[str] = []
        for item in output:
            for content in getattr(item, "content", []) or []:
                text = getattr(content, "text", None)
                if text:
                    chunks.append(str(text))
        if chunks:
            return "\n".join(chunks)
    return str(response)


def _warning(spanish: str, english: str, language: str, exc: Exception) -> str:
    message = english if is_english(language) else spanish
    detail = "Detail" if is_english(language) else "Detalle"
    return f"{message} {detail}: {exc}"
