"""CLI runner for Scouting AI v2."""

from __future__ import annotations

import argparse

from src.scouting.scouting_v2 import generate_scouting_v2
from src.scouting.scouting_v2_report import save_scouting_v2_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera perfiles tácticos y arquetipos de Scouting AI v2.")
    parser.add_argument("--match-id", type=int, help="Match ID para perfil individual.")
    parser.add_argument("--player-id", type=int, help="Player ID para perfil individual.")
    parser.add_argument("--match-a", type=int, help="Match ID del Jugador A.")
    parser.add_argument("--player-a", type=int, help="Player ID del Jugador A.")
    parser.add_argument("--match-b", type=int, help="Match ID del Jugador B.")
    parser.add_argument("--player-b", type=int, help="Player ID del Jugador B.")
    parser.add_argument("--save", action="store_true", help="Guarda Markdown y JSON.")
    parser.add_argument("--html", action="store_true", help="Genera HTML al guardar.")
    parser.add_argument("--docx", action="store_true", help="Genera DOCX al guardar.")
    parser.add_argument("--pdf", action="store_true", help="Genera PDF al guardar.")
    args = parser.parse_args()

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
    if args.match_id is not None:
        result = generate_scouting_v2(args.match_id, args.player_id)
    else:
        result = generate_scouting_v2(args.match_a, args.player_a, args.match_b, args.player_b)

    print_result(result)
    if args.save or args.html or args.docx or args.pdf:
        paths = save_scouting_v2_report(
            result,
            include_html=args.html,
            include_docx=args.docx,
            include_pdf=args.pdf,
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


def print_result(result: dict) -> None:
    profile_a = result.get("profile_a", {})
    print("Scouting AI v2")
    print(f"mode={result.get('mode')} | status={result.get('status')} | model={result.get('model')}")
    print(
        f"Jugador A: {profile_a.get('player_id')} | {profile_a.get('player_name')} "
        f"({profile_a.get('team_name')}) | {profile_a.get('archetype')} "
        f"({profile_a.get('confidence')}/100)"
    )
    profile_b = result.get("profile_b")
    if profile_b:
        print(
            f"Jugador B: {profile_b.get('player_id')} | {profile_b.get('player_name')} "
            f"({profile_b.get('team_name')}) | {profile_b.get('archetype')} "
            f"({profile_b.get('confidence')}/100)"
        )
    warnings = result.get("warnings", [])
    if warnings:
        print("\nWarnings")
        for warning in warnings:
            print(f"- {warning}")
    print("\nNarrativa Markdown")
    print(str(result.get("narrative_markdown") or ""))


if __name__ == "__main__":
    main()
