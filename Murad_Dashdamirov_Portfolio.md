# Portfolio — Murad Dashdamirov

dashdamirov.murad11@gmail.com | [LinkedIn](https://www.linkedin.com/in/murad-dashdamirov-90461934a) | [GitHub](https://github.com/Murad-D-11)

---

## Canada Productivity Intelligence

*An explainable, full-stack platform that turns public Statistics Canada data into a next-quarter labour-productivity forecast, per-forecast driver attributions, and a what-if scenario simulator.*

**Stack:** React + TypeScript (Vite, Tailwind, Recharts) · Node + Express + TypeScript (Prisma) · Python (scikit-learn, pandas) · PostgreSQL · Docker
**Links:** [Repository](https://github.com/Murad-D-11) &nbsp;|&nbsp; [Methodology write-up](https://github.com/Murad-D-11)

### 1. Forecast & Explainability

![Forecast screen: observed-vs-forecast chart with driver breakdown](assets/cpi-forecast.png)
<!--
  IMAGE: PNG. Capture the Forecast page for one industry with BOTH visible:
    - the Recharts observed-vs-forecast line chart, and
    - the "What is driving this forecast?" driver contribution breakdown.
  Caption idea below.
-->
*Next-quarter forecast for a selected industry, with the exact per-feature contributions that produced it.*

- Forecasts next-quarter labour productivity for a chosen industry and renders the observed history against the projected point, reporting both absolute and percentage change versus the latest observed value.
- Explains every prediction exactly rather than approximately: the linear model's output is decomposed into a base value plus each feature's contribution (`coefficient × scaled value`), so the ranked drivers of a forecast are deterministic and reproducible.
- Kept the machine-learning boundary strict — the React frontend consumes REST responses only and never assembles a feature vector, so all feature retrieval and model invocation stay server-side and cannot drift between client and model.
- Chose to fail honestly over filling gaps: when the model is untrained or a feature is missing, the API returns a typed error instead of a fabricated number, so the UI renders an explicit empty or error state.

### 2. System Architecture

![Three-tier architecture: React frontend, Express API, Python ML bridge, PostgreSQL](assets/cpi-architecture.png)

*Frontend calls REST only; the backend owns feature retrieval and invokes the Python model through a JSON stdin/stdout bridge.*

- Separated the system into three decoupled tiers so Python internals never reach the browser: a React SPA, a Node/Express REST API that reads the feature matrix from PostgreSQL through Prisma, and a Python `cpi_ml` package that runs the trained scikit-learn model.
- Integrated Node and Python through a JSON stdin/stdout bridge (`python -m cpi_ml.bridge`) rather than standing up a queue or separate microservice — the simplest mechanism that fit the existing architecture and added no runtime infrastructure to operate.
- Mapped bridge error codes onto meaningful HTTP statuses (untrained model → 503, bad input → 400, upstream failure → 502) so callers can distinguish a not-ready system from a bad request.

> This diagram is rendered from the system diagram in `docs/architecture.md` and reflects the shipped implementation: scikit-learn ridge/random-forest models with exact linear attribution, Statistics Canada as the active data source, and forecast/scenario endpoints served under `/api/v1`.

### 3. Scenario Simulator

![Adjusting an eligible input and comparing baseline vs scenario forecast](assets/cpi-scenario.gif)

*A what-if tool: adjust an eligible input and compare the model's baseline forecast against the scenario response.*

- Lets users perturb eligible inputs and compare a baseline forecast against the scenario result side by side, then reset to baseline.
- Validated every scenario against a single source of truth for feature metadata, rejecting unknown, out-of-range, or non-controllable inputs (forecast targets, lag features, and calendar fields) so a scenario can never silently corrupt the feature vector.
- Framed results honestly with a non-causal disclaimer: a scenario reports how the model responds to changed inputs, not a causal effect or a guarantee about the real economy.

### 4. National Overview — Industry Ranking

![Industries ranked by predicted next-quarter change](assets/cpi-overview.png)

*All industries forecast in a single model process and ranked by predicted next-quarter change.*

- Forecasts every industry's next quarter in one batched model call and ranks the results by predicted percentage change, keeping the whole national view to a single round-trip.
- Labelled the ranking explicitly as a model projection rather than an opportunity score or investment signal, and sorted industries with missing values pushed last so incomplete data never masquerades as a top result.

### 5. Data Pipeline & Provenance

![Data status / ingestion coverage view](assets/cpi-data-status.png)

*Real Statistics Canada ingestion with full provenance; no values are imputed at rest.*

- Ingested 29,443 Statistics Canada observations across 21 industries and 8 measures (coverage 1981–2026) into PostgreSQL, preserving each observation's source provenance and status flags and leaving suppressed values null rather than fabricating them.
- Engineered a 7-feature, past-only matrix (lagged productivity, four-quarter rolling mean, employment and labour-cost growth, and calendar fields) built with `shift(1)`, so a predictor for a given quarter uses only information available at or before that quarter — no look-ahead leakage.
- Wrote a quality report on each ingestion run (observations downloaded, updated, rejected, and missing) so data freshness and coverage are auditable rather than assumed.
