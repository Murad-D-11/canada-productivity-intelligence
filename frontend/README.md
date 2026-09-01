# Frontend — Canada Productivity Intelligence

React + TypeScript single-page app built with Vite, styled with Tailwind, and
charted with Recharts.

## Stack

- React 18 + TypeScript
- Vite 5 (dev server + build)
- Tailwind CSS 3 with semantic design tokens (`src/styles/tokens.css`)
- React Router 6
- Recharts for data visualization

## Structure

```
frontend/
  src/
    app/          router + layout shell
    components/   reusable design-system primitives (ui) + charts
    pages/        one module per route (Overview, Forecast, ...)
    lib/          config + helpers
    styles/       design tokens + Tailwind entry
```

## Design tokens

Colors are defined as RGB channel triples in `src/styles/tokens.css` and mapped
to semantic Tailwind color names in `tailwind.config.ts` (surface, content,
brand, positive, negative, caution, info). Light is the default theme; adding a
`dark` class to `<html>` swaps to the dark palette. This keeps component code
free of hard-coded hex values.

## Scripts

| Command             | Description                     |
| ------------------- | ------------------------------- |
| `npm run dev`       | Start the Vite dev server.      |
| `npm run build`     | Type-check + production build.  |
| `npm run preview`   | Preview the production build.   |
| `npm run typecheck` | Type-check only.                |
| `npm run lint`      | Lint the source.                |

## Note on functionality

Milestone 3 delivers the design system and page shells only. Pages render
layout, structure, and placeholder states — they are intentionally not wired to
live data or the backend yet.
