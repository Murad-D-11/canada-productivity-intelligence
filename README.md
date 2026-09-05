# Canada Productivity Intelligence

Decision support for understanding where Canadian labour productivity is heading,
which factors contribute to the model's forecast, and how the forecast responds
to what-if changes in eligible inputs.

The product turns public Statistics Canada data into an explainable, next-quarter
productivity forecast and a scenario simulator, so users can explore where
productivity movements may warrant further investigation.

> Government data → ETL → PostgreSQL → feature engineering → ML forecasting → explainability → scenario simulation → React web app

Every number shown comes from ingested data or real model output. The platform
never fabricates data, forecasts, drivers, or metrics.

## What it is

A working prototype that:

- ingests real Statistics Canada labour-productivity data,
- trains and validates a forecasting model with strict temporal discipline,
- forecasts next-quarter labour productivity by industry,
- explains each forecast with exact per-feature model contributions,
- lets users run what-if scenarios on eligible inputs,
- and presents it as a clean economic-intelligence web app.

## Growing Canada connection (i.e. theme of the project)

Productivity growth is the foundation of long-run living standards, and Canada's
productivity has lagged. This tool makes the public data legible: it shows the
recent trajectory, projects the next quarter, ranks industries by projected
change, and lets an analyst probe what the model responds to. It is a way to turn
open government data into decision support and to surface areas worth a closer
look, not a source of investment advice or causal claims.

## Features

- **Productivity data** — real Statistics Canada series by industry, quarterly.
- **Forecasting** — one-step-ahead (next quarter) labour productivity forecast.
- **Model drivers** — exact, per-forecast feature contributions (association).
- **Scenario simulation** — adjust eligible inputs, compare baseline vs scenario.
- **Industry analysis** — national comparison ranked by predicted change.
- **Overview + methodology** — national snapshot and transparent model details.

## Architecture

```
frontend/   React + TypeScript + Vite + Tailwind + Recharts (pages, charts, API clients)
backend/    Node + Express + TypeScript API (Prisma), bridges to the ML model
ml/         Python package (cpi_ml): ETL, features, forecasting, explainability, CLI
prisma/     Shared Prisma schema (PostgreSQL)
docs/       Architecture, methodology, UI documentation
```

- **Frontend** calls the backend REST API; it never builds ML feature vectors.
- **Backend** owns feature retrieval (reads the ML-ready feature rows from
  PostgreSQL via Prisma) and calls the Python model through a small JSON
  stdin/stdout bridge (`python -m cpi_ml.bridge`) — the simplest integration
  that keeps Python internals out of the frontend.
- **Database** is PostgreSQL (Prisma schema), holding ingested observations, the
  feature matrix, and model registry tables.
- **ML pipeline** is a standalone Python package with a CLI for ingest, feature
  generation, training, prediction, and explanation.

## Data

Official Government of Canada sources only:

- **Statistics Canada** — table 36-10-0207-01 (product 36100207), *Labour
  productivity and related measures by industry*. Provides the forecast target
  (labour productivity) plus jobs and compensation used as features. Quarterly,
  national (Canada). [Reference](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610020701)
- **Environment and Climate Change Canada — MSC GeoMet** — climate observations
  (temperature, precipitation, snowfall, wind). Wired as optional weather
  features but **not yet ingested**, so weather features are currently inactive.
  [Reference](https://eccc-msc.github.io/open-data/msc-geomet/ogc_api_en/)

## ML

- **Target:** next-quarter labour productivity (the value one quarter ahead).
- **Forecast horizon:** 1 quarter.
- **Resolution:** quarterly (the data's native reference period; not resampled).
- **Features (past-only):** `prodLag1`, `prodLag4`, `prodRollMean4`,
  `employmentGrowth`, `labourCostGrowth`, `quarter`, `month`. All are built with
  `shift(1)` so a predictor for period *t* uses only information available at or
  before *t*.
- **Models compared:** naive previous-value baseline, ridge regression
  (standardized + median-imputed), random forest.
- **Selected model:** **ridge** (lowest validation MAE).
- **Chronological validation:** time-ordered train / validation / test split on
  the shared period axis — never shuffled. Preprocessing is fit on training data
  only. Selection is by validation MAE; the winner is confirmed on a held-out
  test period.
- **Actual metrics** (real backtest; train 1997Q2–2014Q2, validation
  2014Q3–2020Q1, test 2020Q2–2025Q4):

  | model | val MAE | val RMSE | val R² | test MAE | test RMSE | test R² |
  |-------|--------:|---------:|-------:|---------:|----------:|--------:|
  | ridge (selected) | 2.816 | 6.711 | 0.693 | 3.332 | 6.207 | 0.392 |
  | naive baseline   | 2.840 | 6.763 | 0.688 | 3.096 | 5.265 | 0.563 |
  | random forest    | 3.825 | 9.346 | 0.405 | 4.861 | 7.919 | 0.010 |

  Reported honestly: ridge wins on validation but the naive baseline is stronger
  on the test window (which begins at the 2020 COVID shock). The model is a
  modest, transparent prototype, not a tuned-to-look-good result.
- **Explainability:** for the linear model each prediction decomposes exactly
  into a base value plus a per-feature contribution (`coef · scaled_value`), so
  drivers are exact and deterministic — no SHAP approximation needed.
- **Scenario limitations:** a scenario re-runs the model with altered eligible
  inputs and reports the change in the model's output. It is a model response,
  **not** a causal effect or a guarantee about the real economy.

## Running locally

Prerequisites: **Node ≥ 20**, **Python ≥ 3.11**, **Docker Desktop** (for
PostgreSQL). All commands are run from the repository root unless noted.

> Command style: examples use PowerShell/`cmd`-friendly paths (`ml\.venv\Scripts\...`).
> On macOS/Linux use `ml/.venv/bin/...` instead of `ml\.venv\Scripts\...`.

### First-time setup (once)

**1. Create your environment file.** Copy the template; the defaults already
work for local development (no secrets are committed).

```bash
# PowerShell
Copy-Item .env.example .env
# cmd
copy .env.example .env
# macOS/Linux
cp .env.example .env
```

**2. Install JavaScript dependencies** (frontend + backend workspaces):

```bash
npm install
```

**3. Create the Python ML environment.** A virtualenv is **not portable** — if
you moved/copied the project, recreate it here rather than reusing an old one.

```bash
cd ml
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"   # Windows
# .venv/bin/python -m pip install -e ".[dev]"         # macOS/Linux
cd ..
```

> Tip: use `python -m pip ...` (not `pip.exe ...`). It avoids a launcher error
> if the venv path ever changes.

**4. Start PostgreSQL and apply the schema:**

```bash
docker compose up -d postgres                          # DB on localhost:5432
docker ps --filter name=cpi-postgres                   # confirm it is healthy
npm run prisma:generate                                # generate the Prisma client
npx prisma migrate deploy --schema prisma/schema.prisma
```

**5. Load data and train the model** (Python CLI — see the full command
reference below). At minimum:

```bash
cd ml
.venv\Scripts\python.exe -m cpi_ml.cli ingest-statcan       # official productivity data
.venv\Scripts\python.exe -m cpi_ml.cli generate-features    # build the feature matrix
.venv\Scripts\python.exe -m cpi_ml.cli train-model          # train, select, save the model
cd ..
```

### Run the app (every session)

The database container must be running, then start two processes in two
terminals:

```bash
npm run dev:backend     # API   -> http://localhost:4000
npm run dev:frontend    # Web app -> http://localhost:5173
```

Open **http://localhost:5173**. The backend automatically finds the ML
virtualenv (`ml/.venv`) to run the model, so both must exist on the same
machine. Stop a server with `Ctrl+C`; stop the DB with `docker compose stop
postgres` (data is preserved) or `docker compose down` (removes the container).

## Operating the pipeline (ML CLI reference)

All pipeline operations run through the `cpi_ml` CLI from the `ml/` directory:

```bash
cd ml
.venv\Scripts\python.exe -m cpi_ml.cli <command> [options]
.venv\Scripts\python.exe -m cpi_ml.cli --help          # list all commands
.venv\Scripts\python.exe -m cpi_ml.cli <command> --help # options for one command
```

Every data command hits **live official endpoints** and never fabricates data.
Commands that touch the database require `DATABASE_URL` (from `.env`) and a
running Postgres.

### Inspection

```bash
# Show resolved configuration (endpoints, seed, artifacts dir, DB configured?)
.venv\Scripts\python.exe -m cpi_ml.cli config

# Show the configured official data sources
.venv\Scripts\python.exe -m cpi_ml.cli sources
```

### `ingest-statcan` — productivity data (required)

Ingests Statistics Canada table 36-10-0207-01 (labour productivity and related
measures) into PostgreSQL and writes a quality report to `docs/reports/`.

```bash
.venv\Scripts\python.exe -m cpi_ml.cli ingest-statcan
```

| Option | Default | Purpose |
|---|---|---|
| `--product-id <int>` | `36100207` | StatCan product/cube ID to ingest |
| `--incremental` | off | Only insert observations not already stored (skip duplicates) — use for refreshes |
| `--log-level <level>` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

### `ingest-weather` — weather data (optional)

Ingests Environment and Climate Change Canada (MSC GeoMet) weather observations.
**Optional** — the forecast model runs without it. If you ingest weather, you
must re-run `generate-features` and `train-model` for the model to use it.

```bash
# Quick, capped smoke ingest for a couple of provinces
.venv\Scripts\python.exe -m cpi_ml.cli ingest-weather --provinces ON,QC --max-per-province 200

# Fuller ingest over a date range
.venv\Scripts\python.exe -m cpi_ml.cli ingest-weather --start 2015-01-01 --end 2024-12-31
```

| Option | Default | Purpose |
|---|---|---|
| `--collection <id>` | `climate-monthly` | MSC GeoMet collection id |
| `--period <res>` | `MONTHLY` | Aggregate to `ANNUAL` / `QUARTERLY` / `MONTHLY` |
| `--provinces <codes>` | all provinces | Comma-separated province codes, e.g. `ON,QC,BC` |
| `--start <YYYY-MM-DD>` | none | Start date filter |
| `--end <YYYY-MM-DD>` | none | End date filter |
| `--max-per-province <int>` | none | Cap records per province (fast smoke ingest) |
| `--incremental` | off | Skip observations already stored |
| `--log-level <level>` | `INFO` | Logging verbosity |

> The MSC GeoMet API is external, so weather ingestion needs internet access and
> can take a while for large ranges. Start small with `--max-per-province`.

### `generate-features` — build the ML feature matrix (required)

Combines the ingested productivity (and weather, if present) data into the
ML-ready `FeatureSet` / `FeatureRow` tables. Re-run this whenever you ingest new
data.

```bash
.venv\Scripts\python.exe -m cpi_ml.cli generate-features
```

| Option | Default | Purpose |
|---|---|---|
| `--name <label>` | `productivity+weather@v1` | Feature-set name recorded for reproducibility |
| `--log-level <level>` | `INFO` | Logging verbosity |

### `train-model` — train, evaluate, select, save (required)

Trains the candidate models (naive, ridge, random forest), evaluates them with
chronological validation, selects the best by validation MAE, confirms on a
held-out test window, and saves a versioned artifact to `ml/artifacts/`. Prints
the full model comparison.

```bash
.venv\Scripts\python.exe -m cpi_ml.cli train-model
```

| Option | Default | Purpose |
|---|---|---|
| `--feature-set-id <id>` | most recent | Train on a specific feature set |
| `--horizon <int>` | `1` | Forecast horizon in quarters ahead |
| `--val-fraction <float>` | `0.2` | Share of the time span used for validation |
| `--test-fraction <float>` | `0.2` | Share of the time span used for the held-out test |
| `--log-level <level>` | `INFO` | Logging verbosity |

### `predict` — one-off forecast from the trained model

Runs the saved model on a feature vector and prints a structured JSON forecast.
(The web app does this for you; this is for scripting/debugging.)

```bash
.venv\Scripts\python.exe -m cpi_ml.cli predict --features "{\"prodLag1\": 105.2, \"prodLag4\": 103.1, \"prodRollMean4\": 104.0, \"employmentGrowth\": 0.004, \"labourCostGrowth\": 0.011, \"quarter\": 2, \"month\": 4}"
# or from a file:
.venv\Scripts\python.exe -m cpi_ml.cli predict --features-file features.json --forecast-period 2026-Q2
```

| Option | Default | Purpose |
|---|---|---|
| `--features <json>` | — | Feature values as a JSON object |
| `--features-file <path>` | — | JSON file with feature values (alternative to `--features`) |
| `--model-version <id>` | latest | Use a specific trained model version |
| `--forecast-period <label>` | none | Label recorded in the output |
| `--log-level <level>` | `WARNING` | Logging verbosity |

### `explain` — model contributions for a forecast

Prints the per-feature contributions behind a forecast (association, not
causation), or the global feature importance.

```bash
# Per-forecast drivers
.venv\Scripts\python.exe -m cpi_ml.cli explain --features-file features.json
# Global importance only (no feature vector needed)
.venv\Scripts\python.exe -m cpi_ml.cli explain --global
```

| Option | Default | Purpose |
|---|---|---|
| `--global` | off | Show only global feature importance |
| `--features <json>` / `--features-file <path>` | — | Feature values for a per-forecast explanation |
| `--model-version <id>` | latest | Explain a specific model version |
| `--forecast-period <label>` | none | Label recorded in the output |
| `--log-level <level>` | `WARNING` | Logging verbosity |

### Typical workflows

```bash
# Refresh productivity data and retrain end-to-end
.venv\Scripts\python.exe -m cpi_ml.cli ingest-statcan --incremental
.venv\Scripts\python.exe -m cpi_ml.cli generate-features
.venv\Scripts\python.exe -m cpi_ml.cli train-model

# Add weather, then rebuild features + model so the model can use it
.venv\Scripts\python.exe -m cpi_ml.cli ingest-weather --provinces ON,QC,BC
.venv\Scripts\python.exe -m cpi_ml.cli generate-features
.venv\Scripts\python.exe -m cpi_ml.cli train-model
```

## Using the web app

The UI follows one coherent flow, top to bottom:

1. **Canada Overview** — national snapshot plus a table of all industries ranked
   by the model's predicted next-quarter change. Click an industry to drill in.
2. **Forecast** — pick an industry and press **Generate Forecast** to see current
   vs forecast productivity, the expected change, the observed-vs-forecast chart,
   and **"What is driving this forecast?"** (expand a driver for its value, unit,
   and source).
3. **Test a Scenario** — adjust eligible inputs (e.g. `employmentGrowth`), press
   **Simulate**, and compare baseline vs scenario. **Reset to baseline** restores
   the real observed values.
4. **Methodology** — data sources, the pipeline, and the model's real metrics.
5. **Data Status** — live ingestion coverage and freshness.

## API endpoints

The frontend talks to these (all under `http://localhost:4000`):

- `GET  /api/v1/overview` — industry comparison ranked by predicted change
- `POST /api/v1/forecast` — one-step-ahead forecast + top drivers for an industry
- `GET  /api/v1/models` — active model metadata + real metrics
- `GET  /api/v1/scenarios/features` — eligible scenario inputs for a series
- `POST /api/v1/scenarios/simulate` — baseline vs scenario forecast
- `GET  /api/v1/data/status` — ingestion coverage and freshness
- plus `GET /api/v1/industries`, `/measures`, `/productivity/history`
- `GET  /healthz` — liveness check

Example forecast request:

```bash
curl -X POST http://localhost:4000/api/v1/forecast \
  -H "content-type: application/json" \
  -d '{"industry":"Agriculture, forestry, fishing and hunting","geography":"Canada","horizon":1}'
```

## Quality checks

```bash
npm run typecheck                          # TypeScript across workspaces
npm run lint                               # ESLint
npm test --workspace backend               # Backend tests (Vitest; needs DB + model)
cd ml && .venv\Scripts\python.exe -m pytest # ML tests
```

## Troubleshooting

- **`copy`/`Copy-Item` not recognized** — you're in the other shell. Use `copy`
  in cmd, `Copy-Item` in PowerShell.
- **Overwrite prompt when copying `.env`** — a `.env` already exists; answer `no`
  to keep your current config.
- **`Fatal error in launcher ... python.exe: The system cannot find the file`** —
  the Python venv was created at a different path (e.g. the project was moved).
  Delete and recreate it: `rmdir /s /q ml\.venv` then redo setup step 3.
- **Forecast/overview returns 503 or "model service unavailable"** — no trained
  model or the ML venv is missing. Run `train-model` (and `generate-features`
  before it, which needs `ingest-statcan` first), and ensure `ml/.venv` exists.
- **Backend can't reach the database** — confirm `docker ps` shows
  `cpi-postgres` healthy and `DATABASE_URL` in `.env` is correct.
- **"No weather data available ... Ingest weather to populate this overlay"** —
  expected; weather is optional and not ingested by default. Run `ingest-weather`
  if you want the overlay (see the CLI reference).
- **Forecasts take a couple of seconds** — expected; each spawns a short-lived
  Python process to run the model.

## Limitations

- **Predictive, not causal.** Drivers and scenario differences are model
  contributions (association), not causal effects.
- **National only.** The ingested data is Canada-wide; there is no provincial
  breakdown yet, so geographic comparison is national.
- **One-quarter horizon.** The model forecasts a single quarter ahead.
- **Weather inactive.** No weather has been ingested, so weather features are
  excluded.
- **Modest accuracy.** On the COVID-era test window the naive baseline edges out
  the learned model; treat forecasts as directional.
- **Public-data delays.** Official statistics are released and revised on a
  schedule and can lag the present.
- **No fabricated uncertainty.** Only point forecasts and real backtest error are
  shown; no invented confidence bands.


### Three technical points

- **Temporal leakage prevention.** Every feature is past-only (`shift(1)`), and
  preprocessing (imputation, scaling) is fit on the training fold only. The
  target is one quarter ahead, so training never sees the value it predicts.
- **Chronological validation.** Train/validation/test are split by time on the
  shared period axis — never shuffled — and the model is selected on validation
  then confirmed on a held-out test window, with metrics reported honestly.
- **Explainable forecasting on public data.** The backend ingests official
  StatCan data and serves an exact, per-forecast linear decomposition of each
  prediction — deterministic drivers with no black-box approximation.

### Three Growing Canada points

- **Productivity focus.** Directly targets labour productivity, the core driver
  of Canadian living standards.
- **Finding areas of opportunity.** Ranks industries by projected change and lets
  analysts probe drivers and scenarios to flag where to look closer.
- **Public data into decision support.** Converts scattered open government data
  into an explainable tool, with clear limits and no causal overreach.

## Documentation

- [Architecture](docs/architecture.md)
- [Methodology](docs/methodology.md)
- [ML package](ml/README.md)
- [Portfolio Page](https://github.com/Murad-D-11/canada-productivity-intelligence/blob/main/Murad_Dashdamirov_Portfolio.md)

## License

MIT
