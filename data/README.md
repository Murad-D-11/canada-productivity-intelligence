# Data Directory

This directory holds the local data lake used by the ETL and ML pipelines. It
follows a conventional layered structure. **No raw or processed data is
committed to git** (see `.gitignore`); only the folder structure is tracked.

## Layout

| Folder        | Purpose                                                                 |
| ------------- | ----------------------------------------------------------------------- |
| `raw/`        | Untouched responses fetched from official sources (StatCan WDS, GeoMet).|
| `interim/`    | Partially cleaned / reshaped intermediate artifacts.                    |
| `processed/`  | Analysis-ready tables loaded into PostgreSQL.                           |
| `reference/`  | Small, version-controlled lookup tables (industry codes, geographies).  |

## Provenance rules

1. Every file in `raw/` must retain the original source payload unmodified.
2. Each fetch records its source URL, request parameters, and retrieval
   timestamp in a sidecar `*.meta.json` file.
3. Target values (productivity measures) are never interpolated silently. Any
   imputation is explicit, flagged, and documented in `docs/methodology.md`.

## Sources

- Statistics Canada Web Data Service (WDS) — labour and multifactor productivity.
- Environment and Climate Change Canada MSC GeoMet — climate/weather covariates.
- Canadian Survey on Business Conditions — business sentiment covariates.
