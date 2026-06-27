"""CLI runner for Scouting AI."""

from __future__ import annotations

import argparse

from src.scouting.scouting_history import list_scouting_history
from src.scouting.scouting_narrator import generate_scouting_narrative
from src.scouting.scouting_report import save_scouting_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera reportes de Scouting AI.")
    parser.add_argument("--match-id", type=int, help="Match ID para scouting individual.")
    parser.add_argument("--player-id", type=int, help="Player ID para scouting individual.")
    parser.add_argument("--match-a", type=int, help="Match ID del Jugador A.")
    parser.add_argument("--player-a", type=int, help="Player ID del Jugador A.")
    parser.add_argument("--match-b", type=int, help="Match ID del Jugador B.")
    parser.add_argument("--player-b", type=int, help="Player ID del Jugador B.")
    parser.add_argument("--no-api", action="store_true", help="Desactiva OpenAI API.")
    parser.add_argument("--save", action="store_true", help="Guarda reporte profesional Markdown y JSON.")
    parser.add_argument("--html", action="store_true", help="Genera HTML al guardar.")
    parser.add_argument("--docx", action="store_true", help="Genera DOCX al guardar.")
    parser.add_argument("--pdf", action="store_true", help="Genera PDF al guardar.")
    parser.add_argument("--history", action="store_true", help="Lista historial de scouting.")
    args = parser.parse_args()

    if args.history:
        return args

    individual = args.match_id is not None or args.player_id is not None
    comparative = any(value is not None for value in (args.match_a, args.player_a, args.match_b, args.player_b))
    if individual and comparative:
        parser.error(
            "Usa modo individual (--match-id/--player-id) o comparativo (--match-a/--player-a/--match-b/--player-b), no ambos."
        )
    if individual:
        if args.match_id is None or args.player_id is None:
            parser.error("El modo individual requiere --match-id y --player-id.")
    else:
        required = {
            "--match-a": args.match_a,
            "--player-a": args.player_a,
            "--match-b": args.match_b,
            "--player-b": args.player_b,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            parser.error("Faltan argumentos: " + ", ".join(missing))
    return args


def main() -> None:
    args = parse_args()
    if args.history:
        print_history(list_scouting_history(player_id=args.player_id))
        return

    if args.match_id is not None:
        result = generate_scouting_narrative(
            args.match_id,
            args.player_id,
            use_api=not args.no_api,
        )
    else:
        result = generate_scouting_narrative(
            args.match_a,
            args.player_a,
            args.match_b,
            args.player_b,
            use_api=not args.no_api,
        )
    print_result(result)
    if args.save or args.html or args.docx or args.pdf:
        paths = save_scouting_report(
            result,
            include_html=args.html,
            include_docx=args.docx,
            include_pdf=args.pdf,
            use_api=not args.no_api,
        )
        print("\nRutas guardadas")
        for label in ("markdown", "html", "json", "pdf", "docx"):
            if paths.get(label):
                print(f"- {label}: {paths[label]}")
        print(f"- pdf_status: {paths.get('pdf_status')}")
        if paths.get("pdf_warning_message"):
            print(f"  pdf_warning: {paths.get('pdf_warning_message')}")
        if paths.get("pdf_error_message"):
            print(f"  pdf_error: {paths.get('pdf_error_message')}")
        print(f"- docx_status: {paths.get('docx_status')}")
        if paths.get("docx_error_message"):
            print(f"  docx_error: {paths.get('docx_error_message')}")
        print(f"- history_status: {paths.get('history_status')}")
        if paths.get("history_error_message"):
            print(f"  history_error: {paths.get('history_error_message')}")


def print_result(result: dict) -> None:
    summary = result.get("context_summary", {})
    print("Scouting AI")
    print(f"mode={result.get('mode')} | status={result.get('status')} | model={result.get('model')}")
    print(f"Jugador A: {summary.get('player_a')} ({summary.get('team_a')}) | {summary.get('match_a')}")
    if result.get("mode") == "comparativo":
        print(f"Jugador B: {summary.get('player_b')} ({summary.get('team_b')}) | {summary.get('match_b')}")
    warnings = result.get("warnings", [])
    if warnings:
        print("\nWarnings")
        for warning in warnings:
            print(f"- {warning}")
    language_warnings = result.get("language_warnings", [])
    if language_warnings:
        print("\nLanguage warnings")
        for warning in language_warnings:
            print(f"- {warning}")
    print("\nNarrativa Markdown")
    print(str(result.get("narrative_markdown") or ""))


def print_history(rows: list[dict]) -> None:
    if not rows:
        print("No scouting history found.")
        return
    print("Scouting history")
    print(
        "generated_at | mode | player_a | player_b | generated_by | status | "
        "pdf_status | docx_status | language_warnings | markdown_path"
    )
    for row in rows:
        print(
            f"{row.get('generated_at')} | {row.get('mode')} | {row.get('player_name_a')} | "
            f"{row.get('player_name_b') or '-'} | {row.get('generated_by')} | {row.get('status')} | "
            f"{row.get('pdf_status')} | {row.get('docx_status')} | "
            f"{row.get('language_warnings_count')} | {row.get('markdown_path')}"
        )


if __name__ == "__main__":
    main()
