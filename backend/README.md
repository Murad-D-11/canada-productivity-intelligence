# Backend — Canada Productivity Intelligence API

Express + TypeScript service that exposes the analytics API and mediates access
to PostgreSQL (via Prisma) and, in later milestones, to ML outputs.

## Stack

- Node.js 20 + Express 4
- TypeScript (ESM)
- Prisma ORM (schema lives in `../prisma/schema.prisma`)
- Zod for environment/request validation
- Pino for structured logging
- Vitest for tests

## Structure

```
backend/
  src/
    config/      env validation + logger
    lib/         prisma client singleton
    middleware/  error handling
    routes/      health, meta, aggregated API router
    app.ts       express app factory (testable)
    server.ts    process bootstrap
```

## Scripts

| Command                 | Description                                   |
| ----------------------- | --------------------------------------------- |
| `npm run dev`           | Start with hot reload (tsx watch).            |
| `npm run build`         | Compile TypeScript to `dist/`.                |
| `npm start`             | Run the compiled server.                      |
| `npm run typecheck`     | Type-check without emitting.                  |
| `npm run lint`          | Lint the source.                              |
| `npm test`              | Run the Vitest suite.                         |
| `npm run prisma:generate` | Generate the Prisma client.                 |

## API surface (current)

| Endpoint            | Status          | Notes                                          |
| ------------------- | --------------- | ---------------------------------------------- |
| `GET /healthz`      | Implemented     | Liveness.                                      |
| `GET /readyz`       | Implemented     | Readiness.                                     |
| `GET /api/meta`     | Implemented     | Service + configured data source metadata.     |
| `GET /api/endpoints`| Implemented     | Lists planned domain endpoints.                |
| `GET /api/industries` etc. | `501`    | Contract defined; wired to data in later work. |

Domain endpoints intentionally return `501 Not Implemented` until the ETL and
ML pipelines exist. The service never returns fabricated data.
