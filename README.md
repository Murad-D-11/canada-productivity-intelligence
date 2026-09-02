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

Prerequisites: Node ≥ 20, Python ≥ 3.11, Docker (for PostgreSQL).

```bash
# 0) Environment
cp .env.example .env               # fill in local values (no secrets committed)

# 1) Install
npm install                        # frontend + backend workspaces
cd ml && python -m venv .venv && .venv/Scripts/pip install -e ".[dev]" && cd ..

# 2) Database
docker compose up -d postgres      # PostgreSQL on localhost:5432
npm run prisma:generate            # generate the Prisma client
# apply migrations (from repo root):
npx prisma migrate deploy --schema prisma/schema.prisma

# 3) Data + model (Python CLI, from ml/)
cd ml
.venv/Scripts/python -m cpi_ml.cli ingest-statcan     # ingest StatCan 36100207
.venv/Scripts/python -m cpi_ml.cli generate-features  # build the feature matrix
.venv/Scripts/python -m cpi_ml.cli train-model        # train + select + save artifact
cd ..

# 4) Run the app
npm run dev:backend                # API on http://localhost:4000
npm run dev:frontend               # Web app on http://localhost:5173
```

The backend automatically finds the ML virtualenv (`ml/.venv`) to run the model.

### API endpoints

- `GET  /api/v1/overview` — industry comparison ranked by predicted change
- `POST /api/v1/forecast` — one-step-ahead forecast + top drivers for an industry
- `GET  /api/v1/models` — active model metadata + real metrics
- `GET  /api/v1/scenarios/features` — eligible scenario inputs for a series
- `POST /api/v1/scenarios/simulate` — baseline vs scenario forecast
- `GET  /api/v1/data/status` — ingestion coverage and freshness
- plus `GET /api/v1/industries`, `/measures`, `/productivity/history`

## Quality checks

```bash
npm run typecheck                          # TypeScript across workspaces
npm run lint                               # ESLint
npm test --workspace @cpi/backend          # Backend tests (Vitest; needs DB + model)
cd ml && pytest                            # ML tests
```

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

## License

MIT
