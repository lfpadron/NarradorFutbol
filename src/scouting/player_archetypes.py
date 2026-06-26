"""Player archetype definitions for Scouting AI v2."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerArchetype:
    name: str
    description: str
    relevant_metrics: tuple[str, ...]
    weights: dict[str, float]
    position_keywords: tuple[str, ...] = ()
    position_bonus: float = 0.0


ARCHETYPES: tuple[PlayerArchetype, ...] = (
    PlayerArchetype(
        name="Finalizador",
        description="Atacante orientado a tiro, xG y presencia en acciones de definición.",
        relevant_metrics=("xg", "shots", "goals", "impact_score"),
        weights={"xg": 0.3, "shots": 0.25, "goals": 0.25, "impact_score": 0.2},
        position_keywords=("forward", "striker", "wing"),
        position_bonus=3,
    ),
    PlayerArchetype(
        name="Creador",
        description="Jugador que genera ventajas mediante pases clave, asistencias y progresión.",
        relevant_metrics=("key_passes", "assists", "progressive_passes", "pass_accuracy_pct"),
        weights={"key_passes": 0.4, "assists": 0.2, "progressive_passes": 0.25, "pass_accuracy_pct": 0.15},
    ),
    PlayerArchetype(
        name="Organizador",
        description="Perfil de alta participación en construcción, volumen de pase y continuidad.",
        relevant_metrics=("passes", "pass_accuracy_pct", "progressive_passes", "events", "key_passes"),
        weights={"passes": 0.35, "pass_accuracy_pct": 0.2, "progressive_passes": 0.2, "events": 0.15, "key_passes": 0.1},
    ),
    PlayerArchetype(
        name="Recuperador",
        description="Jugador orientado a presión, duelos y acciones de recuperación o contención.",
        relevant_metrics=("pressures", "duels", "counterpressures", "events"),
        weights={"pressures": 0.45, "duels": 0.25, "counterpressures": 0.2, "events": 0.1},
    ),
    PlayerArchetype(
        name="Box-to-box",
        description="Perfil mixto que aparece en progresión, presión, volumen e impacto.",
        relevant_metrics=("pressures", "progressive_passes", "carries", "passes", "impact_score"),
        weights={"pressures": 0.22, "progressive_passes": 0.22, "carries": 0.16, "passes": 0.16, "impact_score": 0.24},
        position_keywords=("midfield",),
        position_bonus=2,
    ),
    PlayerArchetype(
        name="Extremo vertical",
        description="Atacante de banda que acelera, ataca espacios y amenaza en transición.",
        relevant_metrics=("carries", "carry_distance", "shots", "xg", "pressures", "impact_score"),
        weights={"carries": 0.24, "carry_distance": 0.23, "shots": 0.15, "xg": 0.13, "pressures": 0.12, "impact_score": 0.13},
        position_keywords=("wing", "wide"),
        position_bonus=10,
    ),
    PlayerArchetype(
        name="Extremo creativo",
        description="Atacante de banda que mezcla conducción, pase clave y creación.",
        relevant_metrics=("key_passes", "carries", "progressive_passes", "pass_accuracy_pct", "assists", "shots"),
        weights={"key_passes": 0.28, "carries": 0.2, "progressive_passes": 0.17, "pass_accuracy_pct": 0.1, "assists": 0.15, "shots": 0.1},
        position_keywords=("wing", "wide"),
        position_bonus=8,
    ),
    PlayerArchetype(
        name="Segundo delantero",
        description="Atacante que combina amenaza de remate, apoyo creativo e impacto cercano al área.",
        relevant_metrics=("xg", "shots", "key_passes", "goals", "impact_score"),
        weights={"xg": 0.23, "shots": 0.18, "key_passes": 0.16, "goals": 0.22, "impact_score": 0.21},
        position_keywords=("forward", "wing"),
        position_bonus=5,
    ),
    PlayerArchetype(
        name="Delantero objetivo",
        description="Referencia ofensiva asociada a remate, xG, duelos y fijación de centrales.",
        relevant_metrics=("shots", "xg", "goals", "duels", "impact_score"),
        weights={"shots": 0.25, "xg": 0.25, "goals": 0.25, "duels": 0.15, "impact_score": 0.1},
        position_keywords=("forward", "striker"),
        position_bonus=7,
    ),
    PlayerArchetype(
        name="Mediocentro constructor",
        description="Mediocampista de construcción con pase, progresión y continuidad.",
        relevant_metrics=("passes", "progressive_passes", "pass_accuracy_pct", "events", "key_passes"),
        weights={"passes": 0.32, "progressive_passes": 0.26, "pass_accuracy_pct": 0.2, "events": 0.12, "key_passes": 0.1},
        position_keywords=("midfield", "half"),
        position_bonus=3,
    ),
    PlayerArchetype(
        name="Mediocentro destructor",
        description="Mediocampista de contención enfocado en presión, duelos y ruptura del juego rival.",
        relevant_metrics=("pressures", "duels", "counterpressures", "events"),
        weights={"pressures": 0.38, "duels": 0.28, "counterpressures": 0.24, "events": 0.1},
        position_keywords=("midfield",),
        position_bonus=4,
    ),
    PlayerArchetype(
        name="Lateral ofensivo",
        description="Lateral con peso en progresión, conducción, pase clave y apoyo alto.",
        relevant_metrics=("progressive_passes", "carries", "key_passes", "passes", "pressures", "impact_score"),
        weights={"progressive_passes": 0.24, "carries": 0.18, "key_passes": 0.18, "passes": 0.16, "pressures": 0.1, "impact_score": 0.14},
        position_keywords=("back", "wing back"),
        position_bonus=4,
    ),
    PlayerArchetype(
        name="Lateral equilibrado",
        description="Lateral con mezcla de pase, progresión, presión y participación defensiva.",
        relevant_metrics=("passes", "progressive_passes", "pressures", "duels", "pass_accuracy_pct"),
        weights={"passes": 0.24, "progressive_passes": 0.22, "pressures": 0.2, "duels": 0.16, "pass_accuracy_pct": 0.18},
        position_keywords=("back", "wing back"),
        position_bonus=4,
    ),
    PlayerArchetype(
        name="Central constructor",
        description="Defensa central con salida limpia, volumen de pase y progresión desde atrás.",
        relevant_metrics=("passes", "pass_accuracy_pct", "progressive_passes", "events"),
        weights={"passes": 0.38, "pass_accuracy_pct": 0.28, "progressive_passes": 0.2, "events": 0.14},
        position_keywords=("center back", "central"),
        position_bonus=8,
    ),
    PlayerArchetype(
        name="Central defensivo",
        description="Defensa central de contención, duelos, presión situacional y protección del área.",
        relevant_metrics=("duels", "pressures", "events", "pass_accuracy_pct"),
        weights={"duels": 0.38, "pressures": 0.28, "events": 0.2, "pass_accuracy_pct": 0.14},
        position_keywords=("center back", "central"),
        position_bonus=8,
    ),
)


def list_archetypes() -> list[dict[str, object]]:
    return [
        {
            "name": archetype.name,
            "description": archetype.description,
            "relevant_metrics": list(archetype.relevant_metrics),
            "weights": archetype.weights,
        }
        for archetype in ARCHETYPES
    ]
