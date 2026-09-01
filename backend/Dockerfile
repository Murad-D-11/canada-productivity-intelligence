# Backend API image. Build context is the repo root so we can access the shared
# prisma/ schema and workspace lockfile.
FROM node:20-alpine AS base
WORKDIR /app
RUN apk add --no-cache openssl

# --- Dependencies ---------------------------------------------------------
FROM base AS deps
COPY package.json package-lock.json* ./
COPY backend/package.json ./backend/
COPY frontend/package.json ./frontend/
RUN npm install --workspace @cpi/backend --include-workspace-root

# --- Build ----------------------------------------------------------------
FROM deps AS build
COPY tsconfig.base.json ./
COPY prisma ./prisma
COPY backend ./backend
RUN npm run prisma:generate --workspace @cpi/backend \
  && npm run build --workspace @cpi/backend

# --- Runtime --------------------------------------------------------------
FROM base AS runtime
ENV NODE_ENV=production
# npm workspaces hoist all dependencies (including the generated Prisma client)
# to the root node_modules, so only the root tree needs to be copied.
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/backend/dist ./backend/dist
COPY --from=build /app/prisma ./prisma
COPY backend/package.json ./backend/
EXPOSE 4000
CMD ["node", "backend/dist/server.js"]
