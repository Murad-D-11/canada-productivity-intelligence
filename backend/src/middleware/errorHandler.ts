import type { ErrorRequestHandler, RequestHandler } from 'express';
import { logger } from '../config/logger.js';

/** Typed application error with an HTTP status code. */
export class HttpError extends Error {
  constructor(
    public statusCode: number,
    message: string,
  ) {
    super(message);
    this.name = 'HttpError';
  }
}

/** 404 handler for unmatched routes. */
export const notFoundHandler: RequestHandler = (req, res) => {
  res.status(404).json({ error: 'Not Found', path: req.originalUrl });
};

/**
 * Wraps an async route handler so that rejected promises are forwarded to the
 * Express error handler via `next`. Express 4 does not catch async errors
 * automatically, so without this an async handler that throws leaves the
 * request hanging until the client (or test) times out.
 */
export const asyncHandler =
  (handler: RequestHandler): RequestHandler =>
  (req, res, next) => {
    Promise.resolve(handler(req, res, next)).catch(next);
  };

/** Centralized error handler. Keeps responses consistent and logs details. */
export const errorHandler: ErrorRequestHandler = (err, _req, res, _next) => {
  const status = err instanceof HttpError ? err.statusCode : 500;
  if (status >= 500) {
    logger.error({ err }, 'Unhandled error');
  }
  res.status(status).json({
    error: status >= 500 ? 'Internal Server Error' : err.message,
  });
};
