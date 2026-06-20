# Narrador Inteligente de Futbol

Base de ingesta para construir un narrador inteligente de futbol usando datos abiertos de StatsBomb.

Esta primera iteracion solo cubre el cimiento del proyecto:

- descarga de datos StatsBomb Open Data
- guardado raw en JSON, sin transformaciones analiticas
- indice maestro de partidos
- bitacora persistente de ingesta en DuckDB

No incluye todavia Streamlit, transformaciones analiticas a DuckDB, graficas ni narracion AI.

## Instalacion

El proyecto usa `uv` como manejador de dependencias y ejecucion.

```bash
uv sync
```

StatsBomb Open Data no requiere credenciales. Puedes copiar `.env.example` a `.env` si quieres cambiar la ruta de datos.

## Ejecutar ingesta

Descargar todo:

```bash
uv run python -m src.ingestion.run_ingestion
```

Limitar partidos para una prueba rapida:

```bash
uv run python -m src.ingestion.run_ingestion --limit 5
```

Forzar redescarga de archivos existentes:

```bash
uv run python -m src.ingestion.run_ingestion --force
```

Reintentar solo partidos con algun estado `failed` en la bitacora:

```bash
uv run python -m src.ingestion.run_ingestion --retry-failed
```

## Estructura

```text
narrador-futbol/
|- README.md
|- pyproject.toml
|- uv.lock
|- requirements.txt
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
|  `- metadata/
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
   |  |- match_summary.py
   |  |- team_stats.py
   |  |- player_stats.py
   |  |- shot_analysis.py
   |  |- pass_analysis.py
   |  |- possession_analysis.py
   |  |- momentum.py
   |  |- key_moments.py
   |  |- ai_context.py
   |  `- run_analysis.py
   `- ui/
      |- formatters.py
      `- charts.py
```

## Raw JSON

Los archivos en `data/raw/` son copias de las respuestas de StatsBomb guardadas como JSON. La idea es conservar una capa raw reproducible antes de cualquier transformacion.

Rutas principales:

- `data/raw/competitions/competitions.json`
- `data/raw/matches/competition-{competition_id}.season-{season_id}.json`
- `data/raw/events/events.match-{match_id}.json`
- `data/raw/lineups/lineups.match-{match_id}.json`
- `data/raw/three-sixty/three-sixty.match-{match_id}.json`

## Indice maestro y bitacora

Cada corrida reconstruye el indice maestro de partidos desde los JSON de matches:

- `data/metadata/all_matches.csv`
- `data/metadata/all_matches.parquet`

La bitacora persistente vive en:

- `data/metadata/ingestion_log.duckdb`

Tabla: `ingestion_log`

Estados validos:

- `pending`
- `downloaded`
- `skipped_existing`
- `failed`
- `not_available`
- `transformed`

El proceso es reejecutable. Si un archivo ya existe y no usas `--force`, no se descarga otra vez y se registra `skipped_existing`.

## Transformacion analitica

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

Transformar un partido especifico:

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

La Fase 3 calcula metricas futbolisticas sobre `data/analytics/statsbomb.duckdb`.
No modifica raw JSON ni reconstruye la base; solo lee tablas y vistas analiticas.

Listar partidos transformados:

```bash
uv run python -m src.analytics.run_analysis --list-matches
```

Analizar un partido:

```bash
uv run python -m src.analytics.run_analysis --match-id 3754078
```

Exportar contexto analitico JSON:

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

## Ejecutar interfaz Streamlit

La Fase 4 agrega una interfaz local para revisar el estado del pipeline, listar partidos transformados y explorar el analisis de un partido.

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

- pagina principal con estado de `data/analytics/statsbomb.duckdb`
- pagina de ingesta con resumen de `ingestion_log.duckdb`
- pagina de partidos transformados con filtros basicos
- pagina de analisis con resumen, stats por equipo, top jugadores, tiros, pases, posesion, momentum, momentos clave y export JSON
# NarradorFutbol
