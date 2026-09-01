import { createApp } from './app.js';
import { env } from './config/env.js';
import { logger } from './config/logger.js';

/** Boots the HTTP server and wires graceful shutdown. */
function main(): void {
  const app = createApp();

  const server = app.listen(env.BACKEND_PORT, () => {
    logger.info(`API listening on http://localhost:${env.BACKEND_PORT}`);
  });

  const shutdown = (signal: string) => {
    logger.info(`Received ${signal}, shutting down`);
    server.close(() => process.exit(0));
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
}

main();
