# UI Design — Canada Productivity Intelligence

Milestone 3 delivers a professional analytics **design system and page shells**.
No page is wired to data; every data region uses an honest empty/placeholder
state rather than fabricated values.

## Pages

| Route | Page | Purpose |
| --- | --- | --- |
| `/` | Overview | National snapshot: KPI tiles + trend chart placeholder. |
| `/industries` | Industry Explorer | Compare industries/geographies (filters + comparison chart). |
| `/forecast` | Forecast | Forecast vs. observed, with real-metric placeholders. |
| `/drivers` | Drivers | SHAP attribution ranking (labelled association, not causation). |
| `/scenario` | Scenario Simulator | What-if adjustments and model-implied outcomes. |
| `/methodology` | Methodology | Static summary of data and modeling guarantees. |
| `/data-status` | Data Status | Configured official sources and provenance. |

## Design tokens

Tokens live in `frontend/src/styles/tokens.css` as space-separated RGB channels
and are exposed to Tailwind as semantic color names in `tailwind.config.ts`.
Using channels enables Tailwind alpha syntax (e.g. `bg-brand/10`).

| Semantic token | Meaning |
| --- | --- |
| `brand`, `brand-muted` | Primary accent (maple red). |
| `surface`, `surface-raised`, `surface-sunken` | Background layers. |
| `content`, `content-muted`, `content-subtle` | Text hierarchy. |
| `border` | Hairlines and dividers. |
| `positive`, `negative`, `caution`, `info` | Semantic states. |

Additional tokens: `font-sans` (Inter), `font-mono` (JetBrains Mono),
`rounded-card`, `shadow-card`. A `.dark` class on `<html>` swaps the palette.

## Reusable components

Located in `frontend/src/components`:

- `ui/PageHeader` — page title + description + actions slot.
- `ui/Card`, `CardHeader`, `CardBody` — elevated content containers.
- `ui/StatTile` — KPI tile (renders `—` until data exists).
- `ui/Badge` — semantic status pill.
- `ui/Button` — primary/secondary/ghost variants with focus-visible ring.
- `ui/EmptyState` — honest "no data yet" region.
- `charts/ChartPlaceholder` — Recharts line chart bound to an empty dataset,
  demonstrating the charting layer without inventing values.

## Layout

`app/AppLayout` provides a fixed sidebar (from `app/navigation.ts`), a top bar,
and a routed content area via React Router's `Outlet`. `app/router.tsx` wires
all seven pages plus a not-found fallback under the layout.

## Accessibility notes

- Interactive elements use visible focus rings (`focus-visible:outline`).
- Color is paired with text labels (badges include words, not color alone).
- The chart placeholder carries an `aria-label` describing its empty state.
- Full WCAG conformance requires manual testing with assistive technologies and
  expert review; this shell follows the practices above as a starting point.
