# Architecture — Canada Productivity Intelligence

This document describes the system architecture, the flow of data through it,
and the rationale behind each major decision. Diagrams use Mermaid so they
render in GitHub and most Markdown viewers.

The end-to-end workflow is:

> Government Data → ETL → PostgreSQL → ML Forecasting → Explainability → Scenario Simulation → React Web App

---

## 1. System architecture

```mermaid
flowchart LR
  subgraph Sources["Official data sources"]
    SC["Statistics Canada WDS"]
    MSC["MSC GeoMet OGC API"]
    CSBC["Canadian Survey on\nBusiness Conditions"]
  end

  subgraph ML["ML service (Python)"]
    ETL["ETL + validation"]
    FEAT["Feature engineering\n(no look-ahead)"]
    FCAST["Forecasting\n(sklearn / XGBoost)"]
    XAI["Explainability\n(SHAP)"]
    SIM["Scenario engine"]
  end

  DB[("PostgreSQL")]

  subgraph API["Backend API (Node/Express)"]
    REST["REST endpoints"]
    PRISMA["Prisma ORM"]
  end

  WEB["React Web App\n(Vite + Tailwind + Recharts)"]

  SC --> ETL
  MSC --> ETL
  CSBC --> ETL
  ETL --> DB
  FEAT --> FCAST --> DB
  FCAST --> XAI --> DB
  DB --> FEAT
  SIM --> DB
  DB --> PRISMA --> REST --> WEB
  WEB -->|scenario request| REST --> SIM
```

**Why this shape.** The ML service and the API are separate concerns. The ML
service is a batch/pipeline system (fetch, train, explain) that writes results
into PostgreSQL. The API is a thin, stateless read layer over those results
plus an on-demand scenario endpoint. Keeping them decoupled means the web app
never blocks on model training, and the model pipeline can run on its own
schedule.

---

## 2. Component diagram

```mermaid
flowchart TB
  subgraph Frontend
    Router["React Router"]
    Pages["Pages: Overview, Industry Explorer,\nForecast, Drivers, Scenario, Methodology, Data Status"]
    UI["Design system (tokens + primitives)"]
    Charts["Recharts wrappers"]
    ApiClient["API client"]
  end

  subgraph Backend
    App["Express app factory"]
    Health["Health routes"]
    Meta["Meta route"]
    Domain["Domain routes\n(industries, forecasts, drivers, scenarios)"]
    Err["Error middleware"]
    PrismaClient["Prisma client"]
  end

  subgraph MLpkg["cpi_ml package"]
    Cfg["config"]
    DS["datasources (WDS, GeoMet)"]
    E["etl"]
    F["features"]
    Fc["forecasting"]
    X["explainability"]
    Cli["cli"]
  end

  Router --> Pages --> UI
  Pages --> Charts
  Pages --> ApiClient --> Domain
  App --> Health
  App --> Meta
  App --> Domain --> PrismaClient
  App --> Err
  Cli --> DS --> E --> F --> Fc --> X
```

**Why this shape.** Each layer has a single responsibility and a stable seam:
pages depend on an API client (not on fetch details), routes depend on Prisma
(not on SQL), and the ML CLI orchestrates independently testable modules. This
satisfies the modularity and testability requirements.

---

## 3. Data flow

```mermaid
sequenceDiagram
  participant SRC as Official source
  participant ETL as ETL (cpi_ml)
  participant DB as PostgreSQL
  participant ML as Forecasting + SHAP
  participant API as Express API
  participant WEB as React app

  ETL->>SRC: HTTP request (documented endpoint)
  SRC-->>ETL: Raw payload + status flags
  ETL->>ETL: Normalize, preserve nulls & flags
  ETL->>DB: Upsert observations (with provenance)
  ML->>DB: Read observations
  ML->>ML: Build features (past-only), backtest
  ML->>DB: Write forecasts + driver attributions
  WEB->>API: GET /api/forecasts
  API->>DB: Query via Prisma
  DB-->>API: Rows
  API-->>WEB: JSON
  WEB->>API: POST /api/scenarios (adjustments)
  API->>ML: Invoke scenario engine
  ML-->>API: Simulated outcome
  API-->>WEB: JSON
```

**Why this shape.** Provenance and source status flags travel with every
observation so the platform can be transparent about data quality and never
present imputed values as observed. Predictions are written to dedicated tables,
never mixed with observations.

---

## 4. Database flow (entity relationships)

```mermaid
erDiagram
  Geography ||--o{ ProductivityObservation : has
  Industry  ||--o{ ProductivityObservation : has
  Geography ||--o{ Covariate : has
  ModelVersion ||--o{ Forecast : produces
  ModelVersion ||--o{ DriverAttribution : produces
  Geography ||--o{ Forecast : scopes
  Industry  ||--o{ Forecast : scopes
  Geography ||--o{ ScenarioRun : scopes
  Industry  ||--o{ ScenarioRun : scopes

  Geography {
    string id PK
    string sgcCode
    string name
    enum level
  }
  Industry {
    string id PK
    string naicsCode
    string name
    string parentNaicsCode
  }
  ProductivityObservation {
    string id PK
    enum measure
    datetime periodStart
    float value "nullable, never imputed"
    string statusFlag
    datetime retrievedAt
  }
  ModelVersion {
    string id PK
    string version
    datetime trainingCutoff "guards look-ahead"
    json metricsJson "real backtest only"
  }
  Forecast {
    string id PK
    datetime forecastOrigin
    datetime targetPeriod
    float predicted
    float lowerBound
    float upperBound
  }
  DriverAttribution {
    string id PK
    string featureName
    float contribution "SHAP, association"
  }
  ScenarioRun {
    string id PK
    json adjustmentsJson
    float baselineValue
    float simulatedValue
  }
```

**Why this shape.** `ProductivityObservation.value` is nullable so genuinely
unreleased data stays null rather than being filled. `ModelVersion.trainingCutoff`
records the last period used in training, making look-ahead leakage auditable.
`Forecast.forecastOrigin` records the point from which a prediction was made.

---

## 5. ML flow

```mermaid
flowchart TB
  A["Load observations from DB"] --> B["Build features\n(lags, rolling means)"]
  B --> C{"Temporal guard:\nfeatures use only\npast periods?"}
  C -- no --> C1["Reject / fix"]
  C -- yes --> D["Expanding-window backtest"]
  D --> E["Compute real metrics\n(MAE, RMSE)"]
  E --> F["Fit final model on\ndata up to cutoff"]
  F --> G["SHAP attributions\n(association)"]
  G --> H["Persist ModelVersion,\nForecast, DriverAttribution"]
```

**Why this shape.** Validation always uses periods strictly after the training
window (expanding-window backtest), so reported accuracy reflects genuine
out-of-sample performance and never uses future information. Metrics are
computed, not asserted. SHAP explains association between features and
predictions; the UI and docs must not phrase these as causal.

---

## 6. Deployment diagram

```mermaid
flowchart TB
  subgraph Host["Docker Compose network"]
    PG[("postgres:16\ncpi-postgres")]
    BE["backend\n(node:20, :4000)"]
    FE["frontend\n(nginx, :5173)"]
    MLC["ml\n(python:3.11)"]
  end

  Dev["Developer / Browser"] -->|:5173| FE
  FE -->|/api → :4000| BE
  BE -->|:5432| PG
  MLC -->|:5432| PG
  BE -.->|reads default URLs| Ext1["StatCan WDS"]
  MLC -->|HTTPS| Ext1
  MLC -->|HTTPS| Ext2["MSC GeoMet"]
```

**Why this shape.** Compose gives a single-command local environment with a
health-gated startup order (backend and ML wait for a healthy Postgres). The
frontend is served as static files by nginx in production images, while `npm
run dev` provides HMR during development. Only the ML service needs outbound
internet access for data collection in normal operation.

---

## 7. Key architectural decisions

| Decision | Rationale | Trade-off accepted |
| --- | --- | --- |
| Monorepo with npm workspaces (frontend, backend) + standalone Python ML package | One clone, consistent tooling, atomic cross-cutting changes | Slightly more complex root config |
| Separate ML pipeline from API | Web requests never block on training; pipelines run on their own cadence | Requires a shared datastore contract |
| PostgreSQL + Prisma | Relational integrity for time series + typed DB access in TypeScript | ORM abstraction over raw SQL tuning |
| Prisma schema at repo root `/prisma` | Shared contract usable by backend and (conceptually) ML | Backend references a path outside its folder |
| Nullable observation values + status flags | Never present imputed data as observed | Consumers must handle nulls explicitly |
| `trainingCutoff` + `forecastOrigin` fields | Make look-ahead leakage auditable at the data layer | Extra bookkeeping per model run |
| Expanding-window backtesting | Honest out-of-sample metrics; no future leakage | Fewer eval points than k-fold on early data |
| SHAP for explainability, labelled "association" | Interpretable drivers without overclaiming causation | Attribution ≠ causal effect; must be communicated |
| Semantic design tokens via CSS variables | Theming without recompiling utilities; consistent UI | Indirection between color name and value |
| Domain API endpoints return `501` until wired | Discoverable contract without fabricating data | Frontend must render honest empty states |
| Config via validated env vars (Zod / pydantic) | Fail fast on misconfiguration; same code across envs | Requires an `.env` for non-defaults |

---

## 8. Non-negotiable guarantees reflected in the design

- No fabricated data, endpoints, metrics, or API responses.
- No future information in training (`trainingCutoff`, past-only features,
  expanding-window validation).
- No silent interpolation of target values (nullable values + status flags).
- No causal claims (SHAP attributions are labelled as association).
- Modularity, tests per feature, per-service documentation, and a project that
  stays runnable at every commit.
