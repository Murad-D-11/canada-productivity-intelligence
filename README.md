# Canada Productivity Intelligence

AI-powered decision support for understanding where Canadian productivity is
changing, which factors are associated with those changes, and which
interventions may be worth exploring.

This is a production-quality startup prototype, not a dashboard. The workflow:

> Government Data → ETL → PostgreSQL → ML Forecasting → Explainability → Scenario Simulation → React Web App

## Status

Milestones 1–3 are complete: monorepo scaffolding, architecture documentation,
and the UI design system with page shells. The application intentionally serves
**no data yet** — domain API endpoints return `501 Not Implemented` and UI data
regions show honest empty states. This is by design: the platform never
fabricates data, endpoints, metrics, or responses.

## Monorepo layout

```
frontend/   React + TypeScript + Vite + Tailwind + Recharts (design shell)
backend/    Node + Express + TypeScript API (Prisma client)
ml/         Python package: ETL, features, forecasting, SHAP explainability
prisma/     Shared Prisma schema (PostgreSQL)
data/       Layered local data lake (raw/interim/processed/reference)
docs/       Architecture, methodology, and UI design documentation
scripts/    Cross-platform setup and check scripts
```

## Tech stack

- Frontend: React, TypeScript, Vite, Tailwind CSS, Recharts
- Backend: Node.js, Express, TypeScript
- Database: PostgreSQL with Prisma
- ML: Python, pandas, NumPy, scikit-learn, XGBoost, SHAP
- Infrastructure: Docker, Docker Compose

## Prerequisites

- Node.js >= 20 and npm >= 10
- Python >= 3.11
- Docker + Docker Compose (optional, for containerized runs)

## Getting started

Copy the environment template and fill in local values (no secrets are stored
in the template):

```bash
cp .env.example .env
```

### Install

```bash
# Windows
./scripts/setup.ps1

# macOS / Linux
./scripts/setup.sh
```

Or manually:

```bash
npm install                       # frontend + backend workspaces
cd ml && python -m venv .venv && pip install -e ".[dev]"
```

### Run (development)

```bash
npm run dev:backend               # API on http://localhost:4000
npm run dev:frontend              # Web app on http://localhost:5173
```

### Run with Docker

```bash
docker compose build
docker compose up
```

This starts PostgreSQL, the backend, the frontend (served by nginx), and the ML
container.

## Quality checks

```bash
npm run typecheck                 # TypeScript across workspaces
npm run lint                      # ESLint
npm run format:check              # Prettier
npm test --workspace @cpi/backend # Backend tests (Vitest)
cd ml && pytest                   # ML tests
```

## Data sources

Official Government of Canada sources only:

- [Statistics Canada Web Data Service](https://www.statcan.gc.ca/en/developers/wds/user-guide)
- [MSC GeoMet OGC API](https://eccc-msc.github.io/open-data/msc-geomet/ogc_api_en/)
- Canadian Survey on Business Conditions (via StatCan)

## Documentation

- [Architecture](docs/architecture.md) — diagrams and decision rationale
- [Methodology](docs/methodology.md) — data and modeling guarantees
- [UI design](docs/ui-design.md) — pages, tokens, components

## Engineering principles

No fabricated data, endpoints, or metrics. No future information in training.
No silent interpolation of target values. No causal claims. Everything modular,
tested, documented, and runnable at every commit.

## License

MIT
