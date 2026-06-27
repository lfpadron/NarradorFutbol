"""Generate AI or local fallback match narratives."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from openai import OpenAI, OpenAIError

from src.analytics.ai_context import build_ai_match_context
from src.ingestion.utils import to_jsonable
from src.narrative.config import get_openai_api_key, get_openai_model, validate_tone
from src.narrative.fact_guard import validate_narrative_against_context
from src.narrative.prompt_builder import build_match_narrative_prompt
from src.narrative.templates import generate_fallback_narrative


def generate_match_narrative(
    match_id: int,
    tone: str = "cronica_emocionante",
    use_api: bool = True,
) -> dict[str, Any]:
    tone = validate_tone(tone)
    context = build_ai_match_context(match_id)
    model = get_openai_model()
    warnings: list[str] = []
    status = "fallback"

    api_key = get_openai_api_key()
    if use_api and api_key:
        prompt = build_match_narrative_prompt(context, tone)
        try:
            client = OpenAI(api_key=api_key)
            response = client.responses.create(
                model=model,
                input=prompt,
                temperature=0.4,
            )
            narrative_markdown = _extract_response_text(response).strip()
            status = "generated"
        except OpenAIError as exc:
            narrative_markdown = generate_fallback_narrative(context, tone)
            warnings.append(f"OpenAI API falló; se usó fallback local. Detalle: {exc}")
        except Exception as exc:  # Defensive fallback for SDK/network edge cases.
            narrative_markdown = generate_fallback_narrative(context, tone)
            warnings.append(f"No se pudo generar con API; se usó fallback local. Detalle: {exc}")
    else:
        narrative_markdown = generate_fallback_narrative(context, tone)
        if use_api and not api_key:
            warnings.append("OPENAI_API_KEY no está configurada; se usó narrativa local.")
        elif not use_api:
            warnings.append("Uso de OpenAI API desactivado; se usó narrativa local.")

    warnings.extend(validate_narrative_against_context(narrative_markdown, context))
    summary = context.get("match_summary", {})
    return to_jsonable(
        {
            "match_id": match_id,
            "tone": tone,
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
