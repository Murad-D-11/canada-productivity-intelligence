# Frontend image. Build context is the repo root to access the workspace lockfile.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
COPY frontend/package.json ./frontend/
COPY backend/package.json ./backend/
RUN npm install --workspace @cpi/frontend --include-workspace-root
COPY tsconfig.base.json ./
COPY frontend ./frontend
RUN npm run build --workspace @cpi/frontend

# --- Serve with nginx -----------------------------------------------------
FROM nginx:1.27-alpine AS runtime
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 5173
CMD ["nginx", "-g", "daemon off;"]
