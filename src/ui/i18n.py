"""Lightweight bilingual UI helpers for Narrador Futbol."""

from __future__ import annotations

from collections.abc import Mapping
from functools import wraps
from typing import Any

LANGUAGE_SESSION_KEY = "narrador_language"
DEFAULT_LANGUAGE = "es"
SUPPORTED_LANGUAGES = {"es", "en"}

TONE_LABELS_EN = {
    "cronica_emocionante": "Exciting match report",
    "analisis_tecnico": "Technical analysis",
    "resumen_ejecutivo": "Executive summary",
    "scouting": "Scouting",
    "television": "Television",
}

STYLE_LABELS_EN = {
    "tactico": "Tactical narrator",
    "television": "Broadcast narrator",
    "periodistico": "Journalistic narrator",
    "scouting": "Scouting narrator",
    "ejecutivo": "Executive narrator",
}

_EN_TRANSLATIONS: dict[str, str] = {
    "% completados": "% completed",
    "360 disponibles": "360 available",
    "360 no disponibles": "360 unavailable",
    "Aceptar invitación": "Accept invitation",
    "a": "to",
    "Abre la página `Login` en la barra lateral.": "Open the `Login` page from the sidebar.",
    "Activar usuario": "Activate user",
    "Administración de usuarios": "User administration",
    "Advertencias": "Warnings",
    "Advertencias de Scouting AI": "Scouting AI warnings",
    "Advertencias de calidad": "Quality warnings",
    "Advertencias de comparación": "Comparison warnings",
    "Advertencias factuales": "Factual warnings",
    "Advertencias o fallos detectados": "Warnings or failures detected",
    "Análisis": "Analysis",
    "Análisis avanzado": "Advanced analysis",
    "Análisis técnico": "Technical analysis",
    "Alineaciones": "Lineups",
    "Arquetipo A": "Archetype A",
    "Arquetipo B": "Archetype B",
    "Arquetipo principal": "Primary archetype",
    "Arquetipo secundario": "Secondary archetype",
    "Arbitro": "Referee",
    "Árbitro": "Referee",
    "Asistencias": "Assists",
    "Ataque": "Attack",
    "Ataques peligrosos": "Dangerous attacks",
    "Audiencia": "Audience",
    "Aún no hay historial de scouting.": "There is no scouting history yet.",
    "Benchmark": "Benchmark",
    "Calidad básica": "Basic quality",
    "Calor": "Heat",
    "Carries": "Carries",
    "carril": "lane",
    "Cerrar sesión": "Log out",
    "Claridad": "Clarity",
    "Cobertura": "Coverage",
    "Compara dos partidos transformados para revisar diferencias de volumen, eficacia, dominio e impacto.": (
        "Compare two transformed matches to review differences in volume, efficiency, dominance, and impact."
    ),
    "Comparación contra referencia": "Comparison against reference",
    "Comparación de estilos v2": "v2 style comparison",
    "Comparación de tonos": "Tone comparison",
    "Comparación directa": "Direct comparison",
    "Comparador de jugadores": "Player comparison",
    "Comparador de partidos": "Match comparison",
    "Comparar estilos": "Compare styles",
    "Comparar jugadores": "Compare players",
    "Comparar partidos": "Compare matches",
    "Comparar tonos": "Compare tones",
    "Comparativo": "Comparative",
    "Competencia": "Competition",
    "Completados": "Completed",
    "Con gol": "With goal",
    "Con tiro": "With shot",
    "Conclusión": "Conclusion",
    "Construyendo revisión...": "Building review...",
    "Confirmar contraseña": "Confirm password",
    "Contraseña": "Password",
    "Contexto AI": "AI context",
    "Crear contraseña": "Create password",
    "Creación": "Creation",
    "Credenciales inválidas o usuario inactivo.": "Invalid credentials or inactive user.",
    "Crónica emocionante": "Exciting match report",
    "Datos": "Data",
    "Bajar": "Download",
    "Bajar datos": "Download data",
    "Datos base": "Base data",
    "Datos generales": "General data",
    "Debilidades": "Weaknesses",
    "Defensa": "Defense",
    "Defensivo": "Defensive",
    "Desactivar usuario": "Deactivate user",
    "Descargar DOCX": "Download DOCX",
    "Descargar HTML": "Download HTML",
    "Descargar JSON": "Download JSON",
    "Descargar Markdown": "Download Markdown",
    "Descargar PDF": "Download PDF",
    "Desglose xG": "xG breakdown",
    "Detectado": "Detected",
    "Diferencias": "Differences",
    "Diferencia B-A": "B-A difference",
    "Diferencia del intervalo": "Interval difference",
    "Diferencial acumulado": "Cumulative differential",
    "Diferencial acumulado de xG": "Cumulative xG differential",
    "Dominio comparado": "Compared dominance",
    "Dominio estimado": "Estimated dominance",
    "DOCX": "DOCX",
    "Duelos": "Duels",
    "Ejecución benchmark sin API": "Run benchmark without API",
    "Ejecutar benchmark sin API": "Run benchmark without API",
    "Ejecutando benchmark y regresión narrativa...": "Running benchmark and narrative regression...",
    "Ejecutando validación genérica...": "Running generic validation...",
    "Ejecutivo": "Executive",
    "Email": "Email",
    "Email a invitar": "Email to invite",
    "Emoción": "Excitement",
    "English": "English",
    "Entrar": "Sign in",
    "Equipo": "Team",
    "Equipo no disponible": "Team unavailable",
    "Equipo para mapa de pases progresivos": "Team for progressive pass map",
    "Equipo para presiones": "Team for pressures",
    "Equipo para red de pases": "Team for pass network",
    "Errores recientes": "Recent errors",
    "Español": "Spanish",
    "Estadísticas por equipo": "Team statistics",
    "Estadísticas principales": "Main statistics",
    "Estado": "Status",
    "Estado de DuckDB": "DuckDB status",
    "Estados": "Statuses",
    "Estadio": "Stadium",
    "Estilo": "Style",
    "Estilo v2": "v2 style",
    "Estilos v2": "v2 styles",
    "Estructura": "Structure",
    "Evaluación de calidad": "Quality evaluation",
    "Evaluar calidad": "Evaluate quality",
    "Evento": "Event",
    "Eventos": "Events",
    "eventos": "events",
    "Eventos descargados": "Events downloaded",
    "Eventos importantes": "Important events",
    "Eventos más importantes": "Most important events",
    "Eventos ofensivos": "Attacking events",
    "Explorador local para revisar la ingesta, los partidos transformados y las metricas futbolisticas generadas desde StatsBomb Open Data.": (
        "Local explorer for reviewing ingestion, transformed matches, and football metrics generated from StatsBomb Open Data."
    ),
    "Explorador local para revisar la ingesta, los partidos transformados y las métricas futbolísticas generadas desde StatsBomb Open Data.": (
        "Local explorer for reviewing ingestion, transformed matches, and football metrics generated from StatsBomb Open Data."
    ),
    "Export v2": "v2 export",
    "Exportar contexto analítico": "Export analytical context",
    "Exportar JSON": "Export JSON",
    "Exportar PDF de esta pestaña": "Export PDF for this tab",
    "Factualidad": "Factuality",
    "Fact guard generó advertencias.": "Fact guard generated warnings.",
    "Fact guard sin advertencias.": "Fact guard with no warnings.",
    "Faltante": "Missing",
    "Faltas cometidas": "Fouls committed",
    "Faltas recibidas": "Fouls won",
    "Fecha": "Date",
    "Fecha contiene": "Date contains",
    "Fecha no disponible": "Date unavailable",
    "Ficha del partido": "Match brief",
    "Flujo recomendado": "Recommended flow",
    "Formatos adicionales": "Additional formats",
    "Formatos base generados": "Generated base formats",
    "Fortalezas": "Strengths",
    "Fortalezas A": "Strengths A",
    "Fortalezas B": "Strengths B",
    "Fortalezas y debilidades": "Strengths and weaknesses",
    "Generar DOCX": "Generate DOCX",
    "Generar HTML": "Generate HTML",
    "Generar JSON": "Generate JSON",
    "Generar Markdown": "Generate Markdown",
    "Generar PDF": "Generate PDF",
    "Generar Scouting AI v2": "Generate Scouting AI v2",
    "Generar invitación": "Generate invitation",
    "Generar narrativa v2": "Generate v2 narrative",
    "Generar narración": "Generate narrative",
    "Generar reporte": "Generate report",
    "Genera una narración para el partido seleccionado.": "Generate a narrative for the selected match.",
    "Generando narrativa comparativa...": "Generating comparative narrative...",
    "Generando narrativa comparativa de jugadores...": "Generating player comparison narrative...",
    "Generando narrativa especializada...": "Generating specialized narrative...",
    "Generando narración...": "Generating narrative...",
    "Generando perfil táctico v2...": "Generating v2 tactical profile...",
    "Generando reporte final...": "Generating final report...",
    "Generando scouting comparativo...": "Generating comparative scouting...",
    "Generando scouting individual de Jugador A...": "Generating individual scouting for Player A...",
    "Generando scouting individual de Jugador B...": "Generating individual scouting for Player B...",
    "Gol": "Goal",
    "Goles": "Goals",
    "Gol al": "Goal at",
    "Gráficas avanzadas": "Advanced charts",
    "Guardar Scouting AI v2": "Save Scouting AI v2",
    "Guardar narrativa v2": "Save v2 narrative",
    "Guardar narración": "Save narrative",
    "Guardar reporte": "Save report",
    "Guardar resultado": "Save result",
    "Guardar revisión": "Save review",
    "Guardar scouting profesional": "Save professional scouting",
    "Guardar validación": "Save validation",
    "Historial de reportes": "Report history",
    "Historial de scouting": "Scouting history",
    "Impacto": "Impact",
    "Impact score": "Impact score",
    "Ingesta": "Ingestion",
    "Ingresa el identificador de StatsBomb para descargar y preparar un solo partido.": (
        "Enter the StatsBomb identifier to download and prepare a single match."
    ),
    "Inicia sesión para usar el Narrador Inteligente de Fútbol.": "Sign in to use the Intelligent Football Narrator.",
    "Iniciar sesión": "Sign in",
    "Inicio": "Home",
    "Intervalo": "Interval",
    "Entradas al tercio final": "Final-third entries",
    "Invitación aceptada y sesión iniciada.": "Invitation accepted and session started.",
    "Invitación enviada por SMTP con enlace y token.": "Invitation sent by SMTP with link and token.",
    "Invitaciones recientes": "Recent invitations",
    "Jugador": "Player",
    "Jugador A": "Player A",
    "Jugador B": "Player B",
    "Jugador no disponible": "Player unavailable",
    "Jugador para mapa de calor": "Player for heatmap",
    "Jugadores": "Players",
    "Jugadores de impacto": "Impact players",
    "Jugadores destacados": "Featured players",
    "Jugadores top": "Top players",
    "La base existe, pero no se pudo leer.": "The database exists, but could not be read.",
    "La contraseña debe tener al menos 10 caracteres.": "Password must be at least 10 characters long.",
    "La ruta no apunta a un archivo descargable": "The path does not point to a downloadable file",
    "La validación genérica no generó advertencias.": "Generic validation produced no warnings.",
    "Las contraseñas no coinciden.": "Passwords do not match.",
    "Lectura táctica comparada": "Compared tactical reading",
    "Lectura del dominio": "Dominance read",
    "Limitaciones A": "Limitations A",
    "Limitaciones B": "Limitations B",
    "Lineups descargados": "Lineups downloaded",
    "Limpiar": "Clear",
    "Local": "Home",
    "local": "home",
    "LOCAL": "HOME",
    "Mapa de calor de eventos": "Event heatmap",
    "Mapa de calor de eventos o jugador": "Event or player heatmap",
    "Mapa de eventos de presión y counterpress. Maneja partidos sin presiones registradas.": (
        "Pressure and counterpress event map. Handles matches without recorded pressures."
    ),
    "Mapa de pases": "Pass map",
    "Mapa de pases |": "Pass map |",
    "Mapa de presiones": "Pressure map",
    "Mapa de recuperaciones y pérdidas": "Recoveries and losses map",
    "Mapa de tiros": "Shot map",
    "Mapa de tiros avanzado": "Advanced shot map",
    "Mapa de tiros sobre cancha StatsBomb 120x80 y evolución de xG acumulado.": (
        "Shot map on a StatsBomb 120x80 pitch and cumulative xG evolution."
    ),
    "Marcador": "Score",
    "Markdown, HTML y JSON se generan siempre al guardar el reporte.": (
        "Markdown, HTML, and JSON are always generated when saving the report."
    ),
    "Mejor ocasión": "Best chance",
    "Métrica": "Metric",
    "Métricas comparativas": "Comparative metrics",
    "Métricas rápidas": "Quick metrics",
    "Minuto inicial": "Start minute",
    "Modo": "Mode",
    "Momentum por intervalos": "Interval momentum",
    "Momentum score": "Momentum score",
    "Momento clave": "Key moment",
    "Momento del partido": "Match moment",
    "Momentos clave": "Key moments",
    "Momentos Jugador A": "Player A moments",
    "Momentos Jugador B": "Player B moments",
    "Narración AI": "AI narrative",
    "Narración guardada": "Narrative saved",
    "Narrador AI": "AI Narrator",
    "Narrador AI v2": "AI Narrator v2",
    "Narrador Inteligente de Futbol": "Intelligent Football Narrator",
    "Narrador Inteligente de Fútbol": "Intelligent Football Narrator",
    "Narrativa": "Narrative",
    "Narrativa básica": "Basic narrative",
    "Narrativa comparativa": "Comparative narrative",
    "Narrativa comparativa de jugadores": "Player comparison narrative",
    "Narrativa generada con avisos.": "Narrative generated with notices.",
    "Narrativa v2 guardada.": "v2 narrative saved.",
    "Número de partido *": "Match number *",
    "No existe `data/analytics/statsbomb.duckdb`.": "`data/analytics/statsbomb.duckdb` does not exist.",
    "No hay datos suficientes para red de pases.": "There is not enough data for a pass network.",
    "No hay equipos disponibles para construir red de pases.": "There are no teams available to build a pass network.",
    "No hay errores recientes registrados.": "No recent errors registered.",
    "No hay jugadores disponibles para uno de los partidos seleccionados.": (
        "There are no available players for one of the selected matches."
    ),
    "No hay jugadores transformados para el Partido A.": "There are no transformed players for Match A.",
    "No hay jugadores transformados para el Partido B.": "There are no transformed players for Match B.",
    "No hay métricas de dominio para este partido.": "No dominance metrics are available for this match.",
    "No hay partidos con esos filtros.": "No matches match those filters.",
    "No hay partidos transformados.": "There are no transformed matches.",
    "No hay partidos transformados para analizar.": "There are no transformed matches to analyze.",
    "No hay partidos transformados para graficar.": "There are no transformed matches to chart.",
    "No se detectaron anomalías.": "No anomalies detected.",
    "No se detectaron eventos importantes para este partido.": "No important events were detected for this match.",
    "No se detectaron momentos clave.": "No key moments were detected.",
    "No se generó ningún formato adicional en esta corrida.": "No additional format was generated in this run.",
    "No se pudo leer la bitacora de ingesta.": "Could not read the ingestion log.",
    "No se pudo leer la bitácora de ingesta.": "Could not read the ingestion log.",
    "No se pudo exportar PDF": "Could not export PDF",
    "No se pudo guardar scouting": "Could not save scouting",
    "No": "No",
    "Objetivo": "Objective",
    "Ofensivo": "Attacking",
    "OPENAI_API_KEY no está configurada. Narrador AI v2 usará fallback local.": (
        "OPENAI_API_KEY is not configured. AI Narrator v2 will use the local fallback."
    ),
    "OPENAI_API_KEY no está configurada. Scouting AI usará fallback local.": (
        "OPENAI_API_KEY is not configured. Scouting AI will use the local fallback."
    ),
    "OPENAI_API_KEY no está configurada. Se generará narrativa local de respaldo.": (
        "OPENAI_API_KEY is not configured. A local fallback narrative will be generated."
    ),
    "Origen": "Origin",
    "Otros pases": "Other passes",
    "Partido": "Match",
    "Partido A": "Match A",
    "Partido B": "Match B",
    "Partidos": "Matches",
    "Partidos en bitacora": "Matches in log",
    "Partidos transformados": "Transformed matches",
    "Partido descargado": "Downloaded match",
    "Listo para bajar un partido.": "Ready to download a match.",
    "Pase": "Passing",
    "Pase de asistencia": "Assist pass",
    "Pases": "Passes",
    "Pases clave": "Key passes",
    "Pases progresivos": "Progressive passes",
    "PDF exportado": "PDF exported",
    "Perfil por grupos": "Profile by groups",
    "Precisión pase": "Pass accuracy",
    "Perfil táctico y arquetipos inferidos desde métricas observadas del partido.": (
        "Tactical profile and archetypes inferred from observed match metrics."
    ),
    "Periodístico": "Journalistic",
    "Presión": "Pressure",
    "Presiones": "Pressures",
    "Profundidad táctica": "Tactical depth",
    "Progresion": "Progression",
    "Progresión": "Progression",
    "Pérdidas": "Losses",
    "Radar comparativo": "Comparative radar",
    "Rec/pérdidas": "Rec/losses",
    "Recuperaciones": "Recoveries",
    "Recuperaciones/pérdidas": "Recoveries/losses",
    "Recuperaciones y pérdidas": "Recoveries and losses",
    "Red de pases": "Pass network",
    "Red de pases simple": "Simple pass network",
    "Recomendaciones": "Recommendations",
    "Reporte final": "Final report",
    "Reporte guardado.": "Report saved.",
    "Resumen": "Summary",
    "Resumen de pases": "Pass summary",
    "Resumen ejecutivo": "Executive summary",
    "Resultado v2": "v2 result",
    "Revisión guardada": "Saved review",
    "Rol": "Role",
    "Rol observado A": "Observed role A",
    "Rol observado B": "Observed role B",
    "Riesgos de interpretación": "Interpretation risks",
    "Rutas generadas": "Generated paths",
    "Scouting comparativo": "Comparative scouting",
    "Scouting individual A": "Individual scouting A",
    "Scouting individual B": "Individual scouting B",
    "Scouting profesional guardado.": "Professional scouting saved.",
    "Score dominio": "Dominance score",
    "Score de momentum": "Momentum score",
    "Score normalizado por grupo": "Normalized score by group",
    "Scores de arquetipo": "Archetype scores",
    "Selecciona un equipo específico para construir la red de pases.": "Select a specific team to build the pass network.",
    "Seleccionar partido": "Select match",
    "Secundario A": "Secondary A",
    "Secundario B": "Secondary B",
    "Sesión iniciada.": "Session started.",
    "Sin debilidades <= 30": "No weaknesses <= 30",
    "Sin datos para momentum": "No momentum data",
    "Sin eventos con coordenadas para mapa de calor": "No events with coordinates for heatmap",
    "Sin fact warnings.": "No fact warnings.",
    "Sin fortalezas >= 70": "No strengths >= 70",
    "Sin fortalezas dominantes": "No dominant strengths",
    "Sin goles registrados.": "No goals registered.",
    "Sin limitaciones dominantes": "No dominant limitations",
    "Sin momentum": "No momentum",
    "Sin narración disponible.": "Narrative unavailable.",
    "Sin nodos de pase con coordenadas": "No pass nodes with coordinates",
    "Sin nombres": "No names",
    "Sin pases progresivos con coordenadas": "No progressive passes with coordinates",
    "Sin pases con coordenadas": "No passes with coordinates",
    "Sin presiones con coordenadas": "No pressures with coordinates",
    "Sin recuperaciones o pérdidas con coordenadas": "No recoveries or losses with coordinates",
    "Sin tiros": "No shots",
    "Sin tiros a gol": "No shots on target",
    "Sin tiros con coordenadas validas": "No shots with valid coordinates",
    "Sin tiros para calcular xG": "No shots to calculate xG",
    "Sin tarjetas amarillas registradas.": "No yellow cards registered.",
    "Sin tarjetas rojas registradas.": "No red cards registered.",
    "Sin xG": "No xG",
    "Sin zonas calculadas con coordenadas": "No calculated zones with coordinates",
    "SMTP configurado.": "SMTP configured.",
    "SMTP invitaciones": "SMTP invitations",
    "SMTP no está configurado o falló; usa este enlace/token para desarrollo local.": (
        "SMTP is not configured or failed; use this link/token for local development."
    ),
    "SMTP sin configurar.": "SMTP not configured.",
    "Status": "Status",
    "Transformación": "Transformation",
    "* Campo obligatorio": "* Required field",
    "Style quality warnings": "Style quality warnings",
    "Sí": "Yes",
    "Tabla": "Table",
    "Tablas de respaldo y export del contexto analítico para futuras fases.": (
        "Backup tables and analytical context export for future phases."
    ),
    "Táctica": "Tactics",
    "Táctico": "Tactical",
    "Tarjetas amarillas": "Yellow cards",
    "Tarjetas rojas": "Red cards",
    "Televisión": "Television",
    "Temporada": "Season",
    "Tiro fallado": "Missed shot",
    "Tiro": "Shot",
    "Tiros": "Shots",
    "Tiros a gol": "Shots on target",
    "Tiros a gol sin gol": "Shots on target without goal",
    "Tiros fallados": "Missed shots",
    "Tiros y xG": "Shots and xG",
    "Todavia no existe `data/metadata/ingestion_log.duckdb`.": (
        "`data/metadata/ingestion_log.duckdb` does not exist yet."
    ),
    "Todavía no hay reportes registrados en historial.": "There are no reports in history yet.",
    "Token de invitación": "Invitation token",
    "Tipo": "Type",
    "Todos": "All",
    "Todas": "All",
    "Top jugadores": "Top players",
    "Validación": "Validation",
    "Validación futbolística": "Football validation",
    "Validación genérica": "Generic validation",
    "Validar partido": "Validate match",
    "Valor": "Value",
    "Visita": "Away",
    "VISITA": "AWAY",
    "Visitante": "Away",
    "visitante": "away",
    "Visitante - local": "Away - home",
    "Vista previa Markdown": "Markdown preview",
    "Warnings": "Warnings",
    "Warnings de lenguaje": "Language warnings",
    "Warnings v2": "v2 warnings",
    "xG acumulado": "Cumulative xG",
    "xG visitante-local": "Away-home xG",
    "xG visitante": "Away xG",
    "xG local": "Home xG",
    "Zonas": "Zones",
    "Zonas de dominio o presencia": "Dominance or presence zones",
    "Usuario para activar/desactivar": "User to activate/deactivate",
    "Usuarios": "Users",
    "usar OpenAI API": "Use OpenAI API",
}

_EN_TRANSLATIONS.update(
    {
        "Apertura": "Opening",
        "Bajada": "Standfirst",
        "Conclusion": "Conclusion",
        "Conclusion scouting": "Scouting conclusion",
        "Claves": "Keys",
        "Claves del resultado": "Result keys",
        "Cronica": "Chronicle",
        "Directivos y presentaciones": "Executives and presentations",
        "Dominio y xG": "Dominance and xG",
        "Entrenadores y analistas": "Coaches and analysts",
        "Explicar como se gano o perdio desde la estructura del partido.": (
            "Explain how the match was won or lost through its structure."
        ),
        "Evaluar jugadores relevantes y su impacto en el partido.": (
            "Evaluate relevant players and their impact on the match."
        ),
        "Figura": "Figure",
        "Hallazgos clave": "Key findings",
        "Implicaciones": "Implications",
        "Jugadores observados": "Observed players",
        "Lectores de nota deportiva": "Sports article readers",
        "Lectura tactica": "Tactical read",
        "Narrador ejecutivo": "Executive narrator",
        "Narrador periodistico": "Journalistic narrator",
        "Narrador scouting": "Scouting narrator",
        "Narrador tactico": "Tactical narrator",
        "Narrador televisivo": "Broadcast narrator",
        "Narrar el partido con claridad, ritmo y emocion controlada.": (
            "Narrate the match with clarity, rhythm, and controlled excitement."
        ),
        "Presion y momentum": "Pressure and momentum",
        "Producir una cronica publicable del partido.": "Produce a publishable match chronicle.",
        "Resumir hallazgos clave con implicaciones accionables.": (
            "Summarize key findings with actionable implications."
        ),
        "Riesgos": "Risks",
        "Riesgos de lectura": "Reading risks",
        "Ritmo del partido": "Match rhythm",
        "Rol tactico": "Tactical role",
        "Titular sugerido": "Suggested headline",
        "Transmision deportiva": "Sports broadcast",
        "Visores y direccion deportiva": "Scouts and sporting direction",
        "accionable": "actionable",
        "ataques peligrosos": "dangerous attacks",
        "breve, claro y accionable": "brief, clear, and actionable",
        "claves": "keys",
        "conclusion": "conclusion",
        "conclusiones sin evidencia": "unsupported conclusions",
        "declara limitaciones": "states limitations",
        "detalle minuto a minuto": "minute-by-minute detail",
        "dinamico, claro y emocionante": "dynamic, clear, and exciting",
        "distingue volumen de eficacia": "distinguishes volume from efficiency",
        "dominio": "dominance",
        "evita inventar contexto externo": "avoids inventing external context",
        "exageracion emocional": "emotional exaggeration",
        "exceso de bullets": "too many bullets",
        "explica fases del partido": "explains match phases",
        "frases de transmision": "broadcast phrases",
        "implicaciones": "implications",
        "jerga excesiva": "excessive jargon",
        "jugadores": "players",
        "jugadores de impacto": "impact players",
        "lenguaje robotico": "robotic language",
        "mantiene energia narrativa": "keeps narrative energy",
        "mantiene trazabilidad con metricas": "keeps traceability with metrics",
        "no sacrifica factualidad": "does not sacrifice factuality",
        "nombra roles y riesgos": "names roles and risks",
        "observacional, concreto y orientado a decision": "observational, concrete, and decision-oriented",
        "ordena hechos y lectura": "organizes facts and interpretation",
        "parrafos largos": "long paragraphs",
        "parrafos demasiado largos": "overly long paragraphs",
        "periodistico, fluido y verificable": "journalistic, fluid, and verifiable",
        "permite decidir rapido": "supports quick decision-making",
        "preciso, sobrio y analitico": "precise, sober, and analytical",
        "presion": "pressure",
        "prioriza evidencia del partido": "prioritizes match evidence",
        "proyecciones futuras sin evidencia": "future projections without evidence",
        "riesgos": "risks",
        "ritmo": "rhythm",
        "rol tactico": "tactical role",
        "se entiende en voz alta": "works when read aloud",
        "separa rendimiento de potencial": "separates performance from potential",
        "tablas": "tables",
        "tecnicismos excesivos": "excessive technical language",
        "tiene enfoque editorial": "has an editorial angle",
        "usa bullets cuando conviene": "uses bullets when useful",
    }
)

_EN_TRANSLATIONS.update(
    {
        "alto": "high",
        "bajo": "low",
        "medio": "medium",
        "sin dato": "no data",
        "Amenaza de remate limitada en este partido": "Limited shooting threat in this match",
        "Atacante de banda que acelera, ataca espacios y amenaza en transición.": (
            "Wide attacker who accelerates, attacks space, and threatens in transition."
        ),
        "Atacante de banda que mezcla conducción, pase clave y creación.": (
            "Wide attacker who blends carrying, key passing, and creation."
        ),
        "Atacante orientado a tiro, xG y presencia en acciones de definición.": (
            "Attacker oriented toward shots, xG, and presence in finishing actions."
        ),
        "Atacante que combina amenaza de remate, apoyo creativo e impacto cercano al área.": (
            "Attacker who combines shooting threat, creative support, and impact near the box."
        ),
        "Box-to-box": "Box-to-box",
        "Central constructor": "Ball-playing center back",
        "Central defensivo": "Defensive center back",
        "Creador": "Creator",
        "Creación de ventaja": "Chance creation",
        "Creación directa limitada": "Limited direct creation",
        "Defensa central con salida limpia, volumen de pase y progresión desde atrás.": (
            "Center back with clean build-up, passing volume, and progression from deep."
        ),
        "Defensa central de contención, duelos, presión situacional y protección del área.": (
            "Defensive center back focused on containment, duels, situational pressure, and box protection."
        ),
        "Definición e incidencia ofensiva": "Finishing and attacking impact",
        "Delantero objetivo": "Target forward",
        "Extremo creativo": "Creative winger",
        "Extremo vertical": "Vertical winger",
        "Finalizador": "Finisher",
        "Impacto observable": "Observable impact",
        "Jugador orientado a presión, duelos y acciones de recuperación o contención.": (
            "Player oriented toward pressure, duels, and recovery or containment actions."
        ),
        "Jugador que genera ventajas mediante pases clave, asistencias y progresión.": (
            "Player who creates advantages through key passes, assists, and progression."
        ),
        "Lateral con mezcla de pase, progresión, presión y participación defensiva.": (
            "Fullback with a mix of passing, progression, pressure, and defensive involvement."
        ),
        "Lateral con peso en progresión, conducción, pase clave y apoyo alto.": (
            "Fullback with weight in progression, carrying, key passing, and high support."
        ),
        "Lateral equilibrado": "Balanced fullback",
        "Lateral ofensivo": "Attacking fullback",
        "Mediocampista de construcción con pase, progresión y continuidad.": (
            "Build-up midfielder with passing, progression, and continuity."
        ),
        "Mediocampista de contención enfocado en presión, duelos y ruptura del juego rival.": (
            "Holding midfielder focused on pressure, duels, and disrupting the opponent's play."
        ),
        "Mediocentro constructor": "Build-up midfielder",
        "Mediocentro destructor": "Ball-winning midfielder",
        "Organizador": "Organizer",
        "Participación defensiva baja": "Low defensive involvement",
        "Participación observable en el plan de partido": "Observable involvement in the match plan",
        "Perfil de alta participación en construcción, volumen de pase y continuidad.": (
            "High-involvement profile in build-up, passing volume, and continuity."
        ),
        "Perfil inferido a partir de métricas observadas en un solo partido; no equivale a posición oficial ni proyección de carrera.": (
            "Profile inferred from metrics observed in a single match; it is not an official position or career projection."
        ),
        "Perfil mixto que aparece en progresión, presión, volumen e impacto.": (
            "Mixed profile appearing in progression, pressure, volume, and impact."
        ),
        "Confianza baja: ningún arquetipo domina claramente con los datos disponibles.": (
            "Low confidence: no archetype clearly dominates with the available data."
        ),
        "Muestra de eventos baja; leer el arquetipo con cautela.": (
            "Low event sample; read the archetype with caution."
        ),
        "Presión y actividad sin balón": "Pressure and off-ball activity",
        "Progresión con pase o conducción": "Progression through passing or carrying",
        "Progresión limitada": "Limited progression",
        "Recuperador": "Ball winner",
        "Referencia ofensiva asociada a remate, xG, duelos y fijación de centrales.": (
            "Attacking reference associated with shooting, xG, duels, and pinning centre backs."
        ),
        "Jugador orientado a recuperar, presionar y sostener duelos defensivos.": (
            "Player oriented toward recoveries, pressure, and defensive duels."
        ),
        "Segundo delantero": "Second striker",
        "Volumen de pase y organización": "Passing volume and organization",
    }
)

_EN_TRANSLATIONS.update(
    {
        "Compara jugadores dentro del mismo partido o entre partidos distintos con lectura estadística y contextual.": (
            "Compare players within the same match or across different matches with a statistical and contextual read."
        ),
        "Comparación de pases": "Passing comparison",
        "Comparación defensiva": "Defensive comparison",
        "Comparación ofensiva": "Attacking comparison",
        "Fórmula MVP: tiros * 3 + xG * 10 + entradas al tercio final * 1 + eventos ofensivos * 0.5.": (
            "MVP formula: shots * 3 + xG * 10 + final-third entries * 1 + attacking events * 0.5."
        ),
        "Funciona con cualquier partido transformado. Revisa consistencia interna, datos analíticos, reportes y narrativas sin exigir expectativas históricas.": (
            "Works with any transformed match. Checks internal consistency, analytical data, reports, and narratives without requiring historical expectations."
        ),
        "Impacto Partido A": "Match A impact",
        "Impacto Partido B": "Match B impact",
        "Match ID para validación genérica": "Match ID for generic validation",
        "Momentos Partido A": "Match A moments",
        "Momentos Partido B": "Match B moments",
        "Muestra hasta 350 flechas para mantener la interacción fluida.": (
            "Shows up to 350 arrows to keep interaction fluid."
        ),
        "Narrativas especializadas por audiencia.": "Audience-specific narratives.",
        "PASS: no se detectaron anomalías.": "PASS: no anomalies detected.",
        "Todos los checks pasaron.": "All checks passed.",
        "Usar OpenAI API para Scouting AI": "Use OpenAI API for Scouting AI",
        "Usa expectativas humanas conocidas; sirve para regresión narrativa y demos históricas controladas.": (
            "Uses known human expectations; useful for narrative regression and controlled historical demos."
        ),
        "Validación futbolística y regresión narrativa, con rutas separadas para casos curados y partidos genéricos.": (
            "Football validation and narrative regression, with separate paths for curated cases and generic matches."
        ),
        "WARNING: hay hallazgos para revisar.": "WARNING: findings require review.",
        "hay anomalías críticas o el estado no es reconocido.": (
            "there are critical anomalies or the status is not recognized."
        ),
        "xG, tiros, pases y posesión": "xG, shots, passes, and possession",
    }
)

_EN_PHRASE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("Sesión activa:", "Active session:"),
    ("Sesión:", "Session:"),
    ("Rol:", "Role:"),
    ("PDF exportado:", "PDF exported:"),
    ("JSON exportado:", "JSON exported:"),
    ("PDF:", "PDF:"),
    ("DOCX:", "DOCX:"),
    ("Historial:", "History:"),
    ("Narración guardada:", "Narrative saved:"),
    ("Revisión guardada:", "Review saved:"),
    ("Benchmark guardado:", "Benchmark saved:"),
    ("Validación guardada:", "Validation saved:"),
    ("Comparación guardada:", "Comparison saved:"),
    ("Usuario desactivado:", "User deactivated:"),
    ("Usuario activado:", "User activated:"),
    ("Invitación generada para", "Invitation generated for"),
    ("No se pudo exportar PDF:", "Could not export PDF:"),
    ("No se pudo crear invitación:", "Could not create invitation:"),
    ("No se pudo enviar por SMTP:", "Could not send via SMTP:"),
    ("No se pudo generar con API;", "Could not generate with API;"),
    ("No se pudo ejecutar benchmark:", "Could not run benchmark:"),
    ("No se pudo ejecutar la validación genérica:", "Could not run generic validation:"),
    ("No se pudo guardar la validación genérica:", "Could not save generic validation:"),
    ("No se pudo comparar partidos:", "Could not compare matches:"),
    ("No se pudo comparar jugadores:", "Could not compare players:"),
    ("No se pudo generar narrativa comparativa:", "Could not generate comparative narrative:"),
    ("No se pudo generar scouting individual A:", "Could not generate individual scouting A:"),
    ("No se pudo generar scouting individual B:", "Could not generate individual scouting B:"),
    ("No se pudo generar scouting comparativo:", "Could not generate comparative scouting:"),
    ("No se pudo guardar scouting:", "Could not save scouting:"),
    ("No se pudo generar Scouting AI v2:", "Could not generate Scouting AI v2:"),
    ("No se pudo guardar Scouting AI v2:", "Could not save Scouting AI v2:"),
    (
        "hay anomalías críticas o el estado no es reconocido.",
        "there are critical anomalies or the status is not recognized.",
    ),
    ("Mejor tono sugerido:", "Suggested best tone:"),
    ("Mejor estilo sugerido:", "Suggested best style:"),
    ("Audiencia:", "Audience:"),
    ("Objetivo:", "Objective:"),
    ("Minuto", "Minute"),
    ("Equipo:", "Team:"),
    ("Jugador:", "Player:"),
    ("Resultado:", "Outcome:"),
    ("Diferencia:", "Difference:"),
    ("Diferencia del intervalo:", "Interval difference:"),
    ("Diferencial acumulado:", "Cumulative differential:"),
    ("xG local", "Home xG"),
    ("xG visitante", "Away xG"),
    ("Gol de ", "Goal by "),
    ("Ocasión clara de ", "Big chance by "),
    ("Cambio de ", "Substitution by "),
    ("Penalti de ", "Penalty by "),
    ("Asistencia de ", "Assist by "),
    (" anota con xG ", " scores with xG "),
    ("Tiro de ", "Shot by "),
    (" con xG ", " with xG "),
    ("; resultado: ", "; outcome: "),
    (" para ", " for "),
    (" recibe ", " receives "),
    ("Sale ", "Off: "),
    ("; entra ", "; on: "),
    ("Penalti para ", "Penalty for "),
    (" asiste a ", " assists "),
)

_TEXT_METHODS = {
    "title",
    "header",
    "subheader",
    "caption",
    "info",
    "warning",
    "error",
    "success",
    "markdown",
    "text",
    "code",
    "button",
    "checkbox",
    "toggle",
    "text_input",
    "number_input",
    "form_submit_button",
    "download_button",
    "expander",
    "spinner",
}
_OPTION_METHODS = {"selectbox", "radio", "multiselect", "select_slider", "segmented_control"}
_PATCHED = False


def normalize_language(language: object | None) -> str:
    value = str(language or DEFAULT_LANGUAGE).strip().lower()
    return value if value in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def current_language() -> str:
    try:
        import streamlit as st

        stored_language = st.session_state.get(LANGUAGE_SESSION_KEY)
        query_language = None
        try:
            query_language = st.query_params.get("lang")
        except Exception:
            query_language = None
        language = normalize_language(stored_language or query_language)
        st.session_state.setdefault(LANGUAGE_SESSION_KEY, language)
        return language
    except Exception:
        return DEFAULT_LANGUAGE


def is_english(language: object | None = None) -> bool:
    return normalize_language(language or current_language()) == "en"


def ai_language_name(language: object | None = None) -> str:
    return "English" if is_english(language) else "español de México"


def tone_display_name(tone: str, fallback: str | None = None, language: object | None = None) -> str:
    if is_english(language):
        return TONE_LABELS_EN.get(tone, fallback or tone)
    return fallback or tone


def style_display_name(style_id: str, fallback: str | None = None, language: object | None = None) -> str:
    if is_english(language):
        return STYLE_LABELS_EN.get(style_id, fallback or style_id)
    return fallback or style_id


def t(value: Any, language: object | None = None) -> Any:
    return translate_text(value, language=language)


def translate_text(value: Any, language: object | None = None) -> Any:
    if not isinstance(value, str):
        return value
    if not is_english(language):
        return value

    if value in _EN_TRANSLATIONS:
        return _EN_TRANSLATIONS[value]

    for heading in ("#### ", "### ", "## ", "# "):
        if value.startswith(heading):
            return heading + str(translate_text(value[len(heading) :], language="en"))

    if value.startswith("- "):
        return "- " + str(translate_text(value[2:], language="en"))

    stripped = value.strip()
    if stripped != value and stripped in _EN_TRANSLATIONS:
        return value.replace(stripped, _EN_TRANSLATIONS[stripped], 1)

    translated = value
    for source, target in _EN_PHRASE_REPLACEMENTS:
        translated = translated.replace(source, target)
    return translated


def translate_mapping_keys(mapping: Mapping[Any, Any], language: object | None = None) -> dict[Any, Any]:
    if not is_english(language):
        return dict(mapping)
    return {translate_text(str(key), language="en"): value for key, value in mapping.items()}


def render_language_selector() -> str:
    import streamlit as st

    current = current_language()
    with st.sidebar:
        st.markdown(
            """
            <style>
            div[data-testid="stSidebarNav"] {
                display: none;
            }
            div[data-testid="stSidebar"] .narrador-language-label {
                margin: 0.1rem 0 0.35rem;
                color: #4b5563;
                font-size: 0.78rem;
                font-weight: 800;
                letter-spacing: 0;
                text-transform: uppercase;
            }
            div[data-testid="stSidebar"] .narrador-fallback-nav-link {
                display: block;
                margin: 0.2rem 0;
                padding: 0.45rem 0.7rem;
                border-radius: 6px;
                color: inherit;
                text-decoration: none;
                font-weight: 600;
            }
            div[data-testid="stSidebar"] .narrador-fallback-nav-link:hover {
                background: rgba(148, 163, 184, 0.18);
            }
            </style>
            <div class="narrador-language-label">Idioma / Language</div>
            """,
            unsafe_allow_html=True,
        )
        language_cols = st.columns(2)
        if language_cols[0].button(
            "🇲🇽 Español",
            key="language_selector_es",
            type="primary" if current == "es" else "secondary",
            use_container_width=True,
        ):
            _set_language("es")
        if language_cols[1].button(
            "🇺🇸 English",
            key="language_selector_en",
            type="primary" if current == "en" else "secondary",
            use_container_width=True,
        ):
            _set_language("en")
        st.divider()
    return current_language()


def install_streamlit_i18n() -> None:
    global _PATCHED
    if _PATCHED:
        return

    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return

    for name in _TEXT_METHODS | _OPTION_METHODS | {"tabs", "write", "metric", "dataframe"}:
        _patch_module_function(st, name)
        _patch_delta_method(DeltaGenerator, name)

    _PATCHED = True


def _set_language(language: str) -> None:
    import streamlit as st

    normalized = normalize_language(language)
    if st.session_state.get(LANGUAGE_SESSION_KEY) == normalized:
        return
    st.session_state[LANGUAGE_SESSION_KEY] = normalized
    try:
        st.query_params["lang"] = normalized
    except Exception:
        pass
    st.rerun()


def _patch_module_function(streamlit_module: Any, name: str) -> None:
    original = getattr(streamlit_module, name, None)
    if original is None or getattr(original, "_narrador_i18n_wrapped", False):
        return

    @wraps(original)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        localized_args, localized_kwargs = _localized_call(name, args, kwargs)
        return original(*localized_args, **localized_kwargs)

    wrapper._narrador_i18n_wrapped = True  # type: ignore[attr-defined]
    setattr(streamlit_module, name, wrapper)


def _patch_delta_method(delta_generator: Any, name: str) -> None:
    original = getattr(delta_generator, name, None)
    if original is None or getattr(original, "_narrador_i18n_wrapped", False):
        return

    @wraps(original)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        localized_args, localized_kwargs = _localized_call(name, args, kwargs)
        return original(self, *localized_args, **localized_kwargs)

    wrapper._narrador_i18n_wrapped = True  # type: ignore[attr-defined]
    setattr(delta_generator, name, wrapper)


def _localized_call(name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[tuple[Any, ...], dict[str, Any]]:
    localized_kwargs = dict(kwargs)
    localized_args = list(args)

    if name == "write":
        localized_args = [_translate_display_value(arg) for arg in localized_args]
        return tuple(localized_args), localized_kwargs

    if name == "tabs":
        if localized_args:
            localized_args[0] = _translate_iterable_labels(localized_args[0])
        elif "tabs" in localized_kwargs:
            localized_kwargs["tabs"] = _translate_iterable_labels(localized_kwargs["tabs"])
        return tuple(localized_args), localized_kwargs

    if name == "dataframe":
        if localized_args:
            localized_args[0] = _translate_dataframe(localized_args[0])
        elif "data" in localized_kwargs:
            localized_kwargs["data"] = _translate_dataframe(localized_kwargs["data"])
        return tuple(localized_args), localized_kwargs

    if name == "metric":
        for index in (0, 1):
            if len(localized_args) > index and isinstance(localized_args[index], str):
                localized_args[index] = translate_text(localized_args[index])
        for key in ("label", "value"):
            if isinstance(localized_kwargs.get(key), str):
                localized_kwargs[key] = translate_text(localized_kwargs[key])
        return tuple(localized_args), localized_kwargs

    if name in _OPTION_METHODS:
        _translate_label(localized_args, localized_kwargs)
        _install_format_func(localized_kwargs)
        return tuple(localized_args), localized_kwargs

    _translate_label(localized_args, localized_kwargs)
    return tuple(localized_args), localized_kwargs


def _translate_label(args: list[Any], kwargs: dict[str, Any]) -> None:
    if args and isinstance(args[0], str):
        args[0] = translate_text(args[0])
    elif isinstance(kwargs.get("label"), str):
        kwargs["label"] = translate_text(kwargs["label"])


def _install_format_func(kwargs: dict[str, Any]) -> None:
    original_format = kwargs.get("format_func")

    if original_format is None:
        kwargs["format_func"] = _format_option_label
        return

    def translated_format(option: Any) -> Any:
        rendered = original_format(option)
        return translate_text(rendered) if isinstance(rendered, str) else rendered

    kwargs["format_func"] = translated_format


def _format_option_label(option: Any) -> Any:
    return translate_text(option) if isinstance(option, str) else option


def _translate_iterable_labels(labels: Any) -> Any:
    if isinstance(labels, (list, tuple)):
        return [translate_text(label) if isinstance(label, str) else label for label in labels]
    return labels


def _translate_display_value(value: Any) -> Any:
    if isinstance(value, str):
        return translate_text(value)
    if isinstance(value, Mapping):
        return {translate_text(str(key)): val for key, val in value.items()}
    if isinstance(value, list):
        return [translate_text(item) if isinstance(item, str) else item for item in value]
    return value


def _translate_dataframe(value: Any) -> Any:
    if not is_english():
        return value
    try:
        import pandas as pd
    except Exception:
        return value

    if isinstance(value, pd.DataFrame):
        return value.rename(columns=lambda column: translate_text(str(column)))
    return value
