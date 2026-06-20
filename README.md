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
   `- ingestion/
      |- ingestion_log.py
      |- download_competitions.py
      |- download_matches.py
      |- download_events.py
      |- download_lineups.py
      |- download_360.py
      `- run_ingestion.py
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
# NarradorFutbol
