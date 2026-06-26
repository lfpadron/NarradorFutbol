# Narrador Inteligente de Fútbol

Base de ingesta para construir un narrador inteligente de fútbol usando datos abiertos de StatsBomb.

El proyecto ya cubre las primeras capas del sistema:

- descarga de datos StatsBomb Open Data
- guardado raw en JSON, sin transformaciones analíticas
- índice maestro de partidos
- bitácora persistente de ingesta en DuckDB
- transformación analítica a DuckDB
- métricas futbolísticas
- interfaz Streamlit básica
- TUI local de control
- Narrador AI v1 con fallback local sin credenciales
- Narrador AI v2 con estilos especializados por audiencia
- reportes finales en Markdown, HTML y JSON
- exportadores profesionales en PDF y DOCX
- comparador de partidos con narrativa comparativa
- comparador de jugadores para preparar Scouting AI
- Scouting AI v1.1 con fallback local, lenguaje profesional y export profesional
- Scouting AI v2 con perfil táctico, arquetipos y comparación avanzada

La app conserva los datos raw sin modificaciones y genera los entregables derivados en `data/`.

## Instalación

El proyecto usa `uv` como manejador de dependencias y ejecución.

```bash
uv sync
```

StatsBomb Open Data no requiere credenciales. Puedes copiar `.env.example` a `.env` si quieres cambiar la ruta de datos.

## Ejecutar ingesta

Descargar todo:

```bash
uv run python -m src.ingestion.run_ingestion
```

Limitar partidos para una prueba rápida:

```bash
uv run python -m src.ingestion.run_ingestion --limit 5
```

Forzar redescarga de archivos existentes:

```bash
uv run python -m src.ingestion.run_ingestion --force
```

Reintentar solo partidos con algún estado `failed` en la bitácora:

```bash
uv run python -m src.ingestion.run_ingestion --retry-failed
```

Descargar eventos, alineaciones y 360 de un partido específico:

```bash
uv run python -m src.ingestion.run_ingestion --match-id 7534
```

## Estructura

```text
narrador-futbol/
|- README.md
|- pyproject.toml
|- uv.lock
|- requirements.txt
|- control_tui.bat
|- .gitignore
|- .env.example
|- app/
|  |- streamlit_app.py
|  `- pages/
|     |- 01_Ingesta.py
|     |- 02_Partidos.py
|     `- 03_Analisis.py
|- data/
|  |- raw/
|  |  |- competitions/
|  |  |- matches/
|  |  |- events/
|  |  |- lineups/
|  |  `- three-sixty/
|  |- metadata/
|  |- reports/
|  `- comparisons/
`- src/
   |- config.py
   |- ingestion/
   |  |- ingestion_log.py
   |  |- download_competitions.py
   |  |- download_matches.py
   |  |- download_events.py
   |  |- download_lineups.py
   |  |- download_360.py
   |  `- run_ingestion.py
   |- transform/
   |  |- build_duckdb.py
   |  |- normalize_competitions.py
   |  |- normalize_matches.py
   |  |- normalize_lineups.py
   |  |- normalize_events.py
   |  |- normalize_360.py
   |  `- schema.py
   |- analytics/
   |  |- db.py
   |  |- advanced_metrics.py
   |  |- dangerous_attacks.py
   |  |- dominance_analysis.py
   |  |- match_validation.py
   |  |- match_summary.py
   |  |- team_stats.py
   |  |- player_stats.py
   |  |- shot_analysis.py
   |  |- pass_analysis.py
   |  |- pressure_analysis.py
   |  |- possession_analysis.py
   |  |- momentum.py
   |  |- key_moments.py
   |  |- xg_analysis.py
   |  |- ai_context.py
   |  `- run_analysis.py
   |- narrative/
   |  |- config.py
   |  |- prompt_builder.py
   |  |- narrator.py
   |  |- templates.py
   |  |- fact_guard.py
   |  |- quality_checker.py
   |  |- tone_comparison.py
   |  |- review_report.py
   |  |- narrative_store.py
   |  `- run_narrator.py
   |- narrative_v2/
   |  |- style_profiles.py
   |  |- prompt_builder_v2.py
   |  |- narrator_v2.py
   |  |- section_builder.py
   |  |- style_evaluator.py
   |  `- run_narrator_v2.py
   |- benchmark/
   |  |- benchmark_cases.py
   |  |- benchmark_checks.py
   |  |- generic_validation.py
   |  |- generic_narrative_checks.py
   |  |- generic_report.py
   |  |- narrative_regression.py
   |  |- benchmark_runner.py
   |  |- benchmark_report.py
   |  `- run_benchmark.py
   |- comparison/
   |  |- match_comparison.py
   |  |- comparison_narrative.py
   |  |- comparison_report.py
   |  |- run_match_comparison.py
   |  |- player_comparison.py
   |  |- player_comparison_narrative.py
   |  |- player_comparison_report.py
   |  `- run_player_comparison.py
   |- scouting/
   |  |- player_archetypes.py
   |  |- tactical_profile.py
   |  |- scouting_context.py
   |  |- scouting_exporter.py
   |  |- scouting_history.py
   |  |- scouting_language_guard.py
   |  |- scouting_prompt.py
   |  |- scouting_narrator.py
   |  |- scouting_report.py
   |  |- scouting_v2.py
   |  |- scouting_v2_report.py
   |  |- run_scouting.py
   |  `- run_scouting_v2.py
   |- reports/
   |  |- report_builder.py
   |  |- markdown_report.py
   |  |- html_report.py
   |  |- pdf_report.py
   |  |- docx_report.py
   |  |- report_history.py
   |  |- report_store.py
   |  `- run_report.py
   |- ui/
   |  |- formatters.py
   |  |- charts.py
   |  `- pitch_charts.py
   `- tui/
      `- control_tui.py
```

## Raw JSON

Los archivos en `data/raw/` son copias de las respuestas de StatsBomb guardadas como JSON. La idea es conservar una capa raw reproducible antes de cualquier transformación.

Rutas principales:

- `data/raw/competitions/competitions.json`
- `data/raw/matches/competition-{competition_id}.season-{season_id}.json`
- `data/raw/events/events.match-{match_id}.json`
- `data/raw/lineups/lineups.match-{match_id}.json`
- `data/raw/three-sixty/three-sixty.match-{match_id}.json`

## Índice maestro y bitácora

Cada corrida reconstruye el índice maestro de partidos desde los JSON de matches:

- `data/metadata/all_matches.csv`
- `data/metadata/all_matches.parquet`

La bitácora persistente vive en:

- `data/metadata/ingestion_log.duckdb`

Tabla: `ingestion_log`

Estados válidos:

- `pending`
- `downloaded`
- `skipped_existing`
- `failed`
- `not_available`
- `transformed`

El proceso es reejecutable. Si un archivo ya existe y no usas `--force`, no se descarga otra vez y se registra `skipped_existing`.

## Transformación analítica

La Fase 2 transforma los JSON raw descargados a una base DuckDB local:

- `data/analytics/statsbomb.duckdb`

Construir o actualizar la base con los partidos que ya tengan archivo raw de events:

```bash
uv run python -m src.transform.build_duckdb
```

Prueba limitada:

```bash
uv run python -m src.transform.build_duckdb --limit 3 --force
```

Transformar un partido específico:

```bash
uv run python -m src.transform.build_duckdb --match-id 7298 --force
```

Tablas creadas:

- `competition`
- `season`
- `match`
- `team`
- `player`
- `lineup`
- `event`
- `pass`
- `shot`
- `carry`
- `duel`
- `pressure`
- `foul`
- `goalkeeper_action`
- `substitution`
- `event_relationship`
- `freeze_frame`
- `visible_area`
- `transformation_log`

Vistas creadas:

- `vw_match_summary`
- `vw_shots`
- `vw_goals`
- `vw_passes`
- `vw_team_event_counts`
- `vw_player_event_counts`
- `vw_ai_match_context`

Cada evento conserva el JSON original serializado en `event.raw_event_json`.

Ejemplos de consultas DuckDB:

```sql
SELECT * FROM vw_match_summary LIMIT 10;
SELECT * FROM vw_shots WHERE match_id = 7298;
SELECT * FROM vw_goals WHERE match_id = 7298;
SELECT COUNT(*) FROM event;
SELECT COUNT(*) FROM pass;
SELECT COUNT(*) FROM shot;
```

## Capa analytics

La Fase 3 calcula métricas futbolísticas sobre `data/analytics/statsbomb.duckdb`.
No modifica raw JSON ni reconstruye la base; solo lee tablas y vistas analíticas.

Listar partidos transformados:

```bash
uv run python -m src.analytics.run_analysis --list-matches
```

Analizar un partido:

```bash
uv run python -m src.analytics.run_analysis --match-id 3754078
```

Exportar contexto analítico JSON:

```bash
uv run python -m src.analytics.run_analysis --match-id 3754078 --export-json
```

El export se guarda en:

- `data/analytics/exports/analysis.match-{match_id}.json`

La salida incluye:

- `match_summary`
- `team_stats`
- `player_stats`
- `top_players`
- `shot_summary`
- `pass_summary`
- `possession_summary`
- `momentum`
- `key_moments`
- `dominance`
- `dominance_intervals`
- `dangerous_attacks`
- `impact_players`
- `xg_breakdown`
- `validation`
- `reference_comparison`

## Validación futbolística avanzada

La fase actual agrega una capa de enriquecimiento y validación sobre el partido transformado.
Estas métricas no modifican datos raw ni escriben tablas analíticas nuevas; se calculan leyendo DuckDB.

Métricas principales:

- dominio por equipo: tiros, xG, entradas al último tercio, pases progresivos y score de dominio
- intervalos de dominio cada 5 minutos
- ataques peligrosos por posesión
- desglose de xG por equipo
- jugadores de impacto
- validación automática de anomalías básicas
- comparación contra el partido referencia México vs Alemania 2018 (`match_id=7534`)

Ejemplo recomendado:

```bash
uv run python -m src.analytics.run_analysis --match-id 7534 --export-json
```

El JSON exportado `data/analytics/exports/analysis.match-7534.json` incluye los bloques avanzados para futuras fases de curaduría y narración.

## Narrador AI

La fase Narrador AI v1 genera una narración en Markdown desde el contexto curado de `src/analytics/ai_context.py`.
La IA no lee todos los eventos crudos; recibe resumen del partido, métricas, dominio, ataques peligrosos, momentos clave, jugadores de impacto y validación.

Variables opcionales en `.env`:

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

Si `OPENAI_API_KEY` no existe, el sistema no falla: usa una narrativa local de respaldo basada en plantilla.

Generar sin API:

```bash
uv run python -m src.narrative.run_narrator --match-id 7534 --no-api
```

Generar con API y guardar Markdown/JSON:

```bash
uv run python -m src.narrative.run_narrator --match-id 7534 --save
```

Cambiar tono:

```bash
uv run python -m src.narrative.run_narrator --match-id 7534 --tone analisis_tecnico
```

Archivos generados:

- `data/analytics/exports/narrative.match-7534.cronica_emocionante.md`
- `data/analytics/exports/narrative.match-7534.cronica_emocionante.json`

Tonos disponibles:

- `cronica_emocionante`
- `analisis_tecnico`
- `resumen_ejecutivo`
- `scouting`
- `television`

El `fact_guard` agrega advertencias simples si detecta posibles contradicciones con el contexto, como marcador distinto, empate inexistente, goleada no sustentada, penales o rojas no registradas.

## Narrador AI v2

Narrador AI v2 no reemplaza al narrador básico. Vive en `src/narrative_v2/` y genera narrativas especializadas por audiencia:

- `tactico`
- `television`
- `periodistico`
- `scouting`
- `ejecutivo`

Generar narrativa tactica sin API:

```bash
uv run python -m src.narrative_v2.run_narrator_v2 --match-id 7534 --style tactico --no-api
```

Generar narrativa scouting sin API:

```bash
uv run python -m src.narrative_v2.run_narrator_v2 --match-id 7534 --style scouting --no-api
```

Comparar todos los estilos:

```bash
uv run python -m src.narrative_v2.run_narrator_v2 --match-id 7534 --compare --no-api
```

Guardar narrativa v2:

```bash
uv run python -m src.narrative_v2.run_narrator_v2 --match-id 7534 --style periodistico --save --no-api
```

Las salidas guardadas usan sufijo de fecha/hora:

- `data/analytics/exports/narrative_v2.match-7534.tactico_YYYYMMDD_HHMMSS.md`
- `data/analytics/exports/narrative_v2.match-7534.tactico_YYYYMMDD_HHMMSS.json`

Si `OPENAI_API_KEY` está configurada y no usas `--no-api`, v2 usa el modelo de `OPENAI_MODEL`. Sin API, usa fallback local especializado para cada estilo.

## Benchmark futbolístico y validación genérica

La capa de benchmark valida que el sistema conserve consistencia factual, analítica y narrativa. Por default corre sin API para que funcione como prueba de regresión local.

Hay dos modos separados:

- **Benchmark curado:** compara contra expectativas humanas conocidas. Es ideal para regresión narrativa y demos controladas.
- **Validación genérica:** funciona con cualquier `match_id` ya transformado. No intenta probar verdad histórica externa; revisa consistencia interna, datos analíticos, generación de reportes y narrativas.

Caso inicial:

- `germany_mexico_2018`: Alemania 0-1 México, Copa Mundial 2018.

Ejecutar todos los benchmarks:

```bash
uv run python -m src.benchmark.run_benchmark
```

Ejecutar un caso específico:

```bash
uv run python -m src.benchmark.run_benchmark --case germany_mexico_2018
```

Guardar resultado curado en Markdown y JSON:

```bash
uv run python -m src.benchmark.run_benchmark --save
```

Validar cualquier partido transformado:

```bash
uv run python -m src.benchmark.run_benchmark --match-id 7534 --generic
```

Validar y guardar resultado genérico:

```bash
uv run python -m src.benchmark.run_benchmark --match-id 7534 --generic --save
```

El benchmark curado revisa:

- marcador y ganador esperados
- dominio/xG esperado
- jugadores relevantes
- claims narrativos prohibidos
- fact guard
- calidad narrativa básica
- comparación de Narrador AI v2

La validación genérica revisa:

- existencia del partido en DuckDB analítico
- eventos, equipos y marcador
- goles detectados contra marcador
- xG, tiros, coordenadas y jugadores
- dominio del partido
- generación de reporte final en memoria
- narrativa básica y Narrador AI v2

Salidas del benchmark curado:

- `data/benchmarks/results/benchmark_YYYYMMDD_HHMMSS.json`
- `data/benchmarks/results/benchmark_YYYYMMDD_HHMMSS.md`

Salidas de la validación genérica:

- `data/benchmarks/results/generic_validation.match-7534_YYYYMMDD_HHMMSS.json`
- `data/benchmarks/results/generic_validation.match-7534_YYYYMMDD_HHMMSS.md`

## Comparador de partidos

El comparador permite revisar dos partidos transformados lado a lado. Calcula diferencias de tiros, xG, goles, pases, posesión, dominio, momentum, ataques peligrosos, jugadores de impacto, momentos clave e intensidad.

Comparar dos partidos:

```bash
uv run python -m src.comparison.run_match_comparison --match-a 7534 --match-b 3754078
```

Generar narrativa comparativa local:

```bash
uv run python -m src.comparison.run_match_comparison --match-a 7534 --match-b 3754078 --narrative --no-api
```

Guardar comparación y narrativa:

```bash
uv run python -m src.comparison.run_match_comparison --match-a 7534 --match-b 3754078 --save --narrative --no-api
```

Salidas:

- `data/comparisons/comparison.match-7534_vs_3754078_YYYYMMDD_HHMMSS.json`
- `data/comparisons/comparison.match-7534_vs_3754078_YYYYMMDD_HHMMSS.md`

La pestaña **Comparador de partidos** en Streamlit permite elegir Partido A y Partido B, comparar métricas, revisar dominio e impacto, generar narrativa comparativa y guardar el resultado.

## Comparador de jugadores

El comparador de jugadores permite contrastar dos futbolistas dentro de un mismo partido o entre partidos distintos. Distingue volumen, eficiencia e impacto, y advierte cuando los roles son distintos para evitar lecturas absolutas.

La interfaz visual incluye:

- radar comparativo normalizado 0-100
- barras comparativas
- perfiles ofensivo, creación, pase, defensivo e impacto
- fortalezas y debilidades por jugador

Listar jugadores disponibles:

```bash
uv run python -m src.comparison.run_player_comparison --list-players --match-id 7534
```

Comparar dos jugadores:

```bash
uv run python -m src.comparison.run_player_comparison --match-a 7534 --player-a <PLAYER_ID_A> --match-b 7534 --player-b <PLAYER_ID_B>
```

Generar narrativa comparativa local:

```bash
uv run python -m src.comparison.run_player_comparison --match-a 7534 --player-a <PLAYER_ID_A> --match-b 7534 --player-b <PLAYER_ID_B> --narrative --no-api
```

Guardar comparación y narrativa:

```bash
uv run python -m src.comparison.run_player_comparison --match-a 7534 --player-a <PLAYER_ID_A> --match-b 7534 --player-b <PLAYER_ID_B> --save --narrative --no-api
```

Exportar datos visuales para radar y fortalezas:

```bash
uv run python -m src.comparison.run_player_comparison --match-a 7534 --player-a 5571 --match-b 7534 --player-b 5579 --export-visual-data
```

Salidas:

- `data/comparisons/player_comparison.match-7534.<PLAYER_ID_A>_vs_match-7534.<PLAYER_ID_B>_YYYYMMDD_HHMMSS.json`
- `data/comparisons/player_comparison.match-7534.<PLAYER_ID_A>_vs_match-7534.<PLAYER_ID_B>_YYYYMMDD_HHMMSS.md`
- `data/comparisons/player_visual_data.match-7534.5571_vs_match-7534.5579_YYYYMMDD_HHMMSS.json`

La pestaña **Comparador de jugadores** en Streamlit permite seleccionar Partido A, Jugador A, Partido B y Jugador B, revisar radar, barras, métricas ofensivas, creación, defensa, impacto, fortalezas/debilidades y generar una narrativa comparativa.

## Scouting AI

Scouting AI v1.1 genera reportes profesionales para un jugador individual o para comparar dos jugadores. Usa datos observados del partido, métricas del comparador de jugadores, radar, fortalezas y áreas de cautela.

Reglas de lenguaje:

- tono profesional, claro, sobrio y útil para cuerpo técnico;
- sin vocabulario altisonante, vulgar, ofensivo, gráfico o sensacionalista;
- sin metáforas violentas innecesarias ni ridiculización de jugadores, equipos o entrenadores;
- el bajo rendimiento se expresa como áreas de mejora o cautela;
- no predice carrera, no inventa minutos y no afirma futuro, fichajes o valor de mercado como hecho.

Con API, Scouting AI usa `OPENAI_API_KEY` y `OPENAI_MODEL`. Sin API, usa fallback local y pasa por el mismo guard de lenguaje.

Scouting individual sin API:

```bash
uv run python -m src.scouting.run_scouting --match-id 7534 --player-id 5571 --no-api
```

Scouting comparativo sin API:

```bash
uv run python -m src.scouting.run_scouting --match-a 7534 --player-a 5571 --match-b 7534 --player-b 5579 --no-api
```

Export profesional individual:

```bash
uv run python -m src.scouting.run_scouting --match-id 7534 --player-id 5571 --no-api --save --html --docx --pdf
```

Export profesional comparativo:

```bash
uv run python -m src.scouting.run_scouting --match-a 7534 --player-a 5571 --match-b 7534 --player-b 5579 --no-api --save --html --docx --pdf
```

Historial de scouting:

```bash
uv run python -m src.scouting.run_scouting --history
```

Filtrar historial por jugador:

```bash
uv run python -m src.scouting.run_scouting --history --player-id 5571
```

Salidas profesionales:

- `data/scouting/scouting.match-7534.5571_YYYYMMDD_HHMMSS.md`
- `data/scouting/scouting.match-7534.5571_YYYYMMDD_HHMMSS.html`
- `data/scouting/scouting.match-7534.5571_YYYYMMDD_HHMMSS.json`
- `data/scouting/scouting.match-7534.5571_YYYYMMDD_HHMMSS.docx`
- `data/scouting/scouting.match-7534.5571_YYYYMMDD_HHMMSS.pdf`
- `data/scouting/scouting.match-7534.5571_vs_match-7534.5579_YYYYMMDD_HHMMSS.*`
- `data/analytics/scouting_history.duckdb`

El PDF usa el flujo tolerante del exportador profesional: intenta WeasyPrint y, si el entorno de Windows no tiene librerías nativas, usa ReportLab. Si ambos fallan, no aborta el proceso; guarda los demás formatos y registra el error en historial.

### Scouting AI v2

Scouting AI v2 infiere perfiles tácticos y arquetipos desde métricas observadas. El objetivo no es adivinar la posición oficial del jugador, sino responder qué tipo de comportamiento mostró en el partido: amenaza ofensiva, creación, organización, progresión, presión, duelos e impacto.

Arquetipos MVP:

- Finalizador
- Creador
- Organizador
- Recuperador
- Box-to-box
- Extremo vertical
- Extremo creativo
- Segundo delantero
- Delantero objetivo
- Mediocentro constructor
- Mediocentro destructor
- Lateral ofensivo
- Lateral equilibrado
- Central constructor
- Central defensivo

Perfil individual:

```bash
uv run python -m src.scouting.run_scouting_v2 --match-id 7534 --player-id 5571
```

Comparación de arquetipos:

```bash
uv run python -m src.scouting.run_scouting_v2 --match-a 7534 --player-a 5571 --match-b 7534 --player-b 5579
```

Export profesional v2:

```bash
uv run python -m src.scouting.run_scouting_v2 --match-a 7534 --player-a 5571 --match-b 7534 --player-b 5579 --save --html --docx --pdf
```

Salidas:

- `data/scouting/scouting_v2.match-7534.5571_YYYYMMDD_HHMMSS.md`
- `data/scouting/scouting_v2.match-7534.5571_YYYYMMDD_HHMMSS.json`
- `data/scouting/scouting_v2.match-7534.5571_YYYYMMDD_HHMMSS.html`
- `data/scouting/scouting_v2.match-7534.5571_YYYYMMDD_HHMMSS.docx`
- `data/scouting/scouting_v2.match-7534.5571_YYYYMMDD_HHMMSS.pdf`
- `data/scouting/scouting_v2.match-7534.5571_vs_match-7534.5579_YYYYMMDD_HHMMSS.*`

En la muestra México vs Alemania 2018, el clasificador debe leer a Hirving Lozano como perfil ofensivo cercano a **Segundo delantero** o **Extremo vertical**, y a Joshua Kimmich como **Organizador** o **Mediocentro constructor**. La narrativa explica la razón y conserva advertencias contra interpretación absoluta.

## Evaluación del narrador

La fase Narrador AI v1.1 agrega evaluación local de calidad narrativa sin depender de otro LLM.
El objetivo es revisar si la narración es factual, coherente, útil para analistas, suficientemente emocionante y trazable al contexto analítico.

Evaluar una narrativa:

```bash
uv run python -m src.narrative.run_narrator --match-id 7534 --no-api --quality
```

Comparar todos los tonos:

```bash
uv run python -m src.narrative.run_narrator --match-id 7534 --no-api --compare-tones
```

Guardar reporte de revisión:

```bash
uv run python -m src.narrative.run_narrator --match-id 7534 --no-api --review-save
```

Archivos generados por la revisión:

- `data/analytics/exports/review.match-7534.md`
- `data/analytics/exports/review.match-7534.json`

El `quality_checker` usa heurísticas simples para puntuar:

- factualidad
- cobertura
- claridad
- emoción
- profundidad táctica

El reporte compara tonos, sugiere el mejor y lista advertencias/recomendaciones.

## Generar reporte final

La fase de reporte final exportable construye un entregable integral en Markdown, HTML y JSON.
El reporte combina datos generales, estadísticas principales, análisis avanzado, narración AI, evaluación de calidad narrativa, validación futbolística y trazabilidad.

Generar vista previa sin API:

```bash
uv run python -m src.reports.run_report --match-id 7534 --no-api
```

Generar y guardar archivos:

```bash
uv run python -m src.reports.run_report --match-id 7534 --save --no-api
```

Cambiar tono:

```bash
uv run python -m src.reports.run_report --match-id 7534 --tone analisis_tecnico --save --no-api
```

Salidas:

- `data/reports/report.match-7534.cronica_emocionante_YYYYMMDD_HHMMSS.md`
- `data/reports/report.match-7534.cronica_emocionante_YYYYMMDD_HHMMSS.html`
- `data/reports/report.match-7534.cronica_emocionante_YYYYMMDD_HHMMSS.json`

El HTML usa CSS embebido y puede abrirse directamente en navegador.

## Exportación PDF y DOCX

La Fase 7 completa el exportador profesional:

- PDF ejecutivo desde el HTML del reporte.
- DOCX editable con secciones y tablas principales.
- Historial de reportes en DuckDB.
- Auditoría básica con usuario, fecha, tono, rutas y estados PDF/DOCX.

Generar todo lo disponible:

```bash
uv run python -m src.reports.run_report --match-id 7534 --save --pdf --docx --no-api
```

Consultar historial:

```bash
uv run python -m src.reports.run_report --history
```

Consultar historial de un partido:

```bash
uv run python -m src.reports.run_report --history --match-id 7534
```

Salidas adicionales:

- `data/reports/report.match-7534.cronica_emocionante_YYYYMMDD_HHMMSS.pdf`
- `data/reports/report.match-7534.cronica_emocionante_YYYYMMDD_HHMMSS.docx`
- `data/analytics/report_history.duckdb`

Todos los formatos generados en una misma exportación comparten el mismo sufijo `_YYYYMMDD_HHMMSS`, por ejemplo `report.match-7534.cronica_emocionante_20260622_233028.html`.

El PDF intenta usar WeasyPrint primero. En Windows, si faltan librerías nativas como `libgobject`, usa un fallback con ReportLab para generar el archivo de todos modos. Si ambos motores fallan, el flujo no se rompe: se guardan Markdown/HTML/JSON/DOCX, se registra `pdf_status=failed` y el error queda en el historial.

El DOCX usa `python-docx` y debe funcionar localmente sin credenciales. El campo `generated_by` del historial usa `NARRADOR_USER_EMAIL`; si no existe, usa `local_user`.

## Ejecutar interfaz Streamlit

La Fase 4 agrega una interfaz local para revisar el estado del pipeline, listar partidos transformados y explorar el análisis de un partido.

```bash
uv run streamlit run app/streamlit_app.py
```

Flujo recomendado desde cero para una prueba corta:

```bash
uv run python -m src.ingestion.run_ingestion --limit 3
uv run python -m src.transform.build_duckdb --limit 3 --force
uv run python -m src.analytics.run_analysis --list-matches
uv run streamlit run app/streamlit_app.py
```

La app incluye:

- página principal con estado de `data/analytics/statsbomb.duckdb`
- página de ingesta con resumen de `ingestion_log.duckdb`
- página de partidos transformados con filtros básicos
- página de análisis con tabs, resumen, stats por equipo, top jugadores, tiros, pases, presión, posesión, momentum, análisis avanzado, Narrador AI con evaluación/comparación de tonos y reporte final, Narrador AI v2, Benchmark, Comparador de partidos, Comparador de jugadores, momentos clave y export JSON

Visualizaciones futbolísticas disponibles:

- mapa de tiros en cancha StatsBomb 120x80
- xG acumulado por equipo
- mapa de pases progresivos con flechas
- mapa de presiones
- red simple de pases por equipo
- momentum por intervalos con tooltip
- panel/timeline de momentos clave
- tablas de dominio, xG, ataques peligrosos, jugadores de impacto y validación

Dependencias visuales principales:

- `streamlit`
- `plotly`
- `mplsoccer`
- `matplotlib`

Ejecutar Streamlit:

```bash
uv run streamlit run app/streamlit_app.py
```

## TUI de control

La TUI permite controlar Streamlit desde terminal:

- ver estado encendido/apagado
- arrancar Streamlit
- abrir el navegador en `http://localhost:8501`
- apagar Streamlit
- ver logs del proceso

Desde la raíz del proyecto:

```bash
control_tui.bat
```

Comando equivalente:

```bash
uv run python -m src.tui.control_tui
```
