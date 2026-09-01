import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Vite configuration. The dev server binds 0.0.0.0 so it is reachable from
// within Docker, and the port matches docker-compose (5173).
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
  },
  preview: {
    host: true,
    port: 5173,
  },
});
