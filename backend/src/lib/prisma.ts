import { PrismaClient } from '@prisma/client';
import { env } from '../config/env.js';

/**
 * Singleton Prisma client. In development we cache it on `globalThis` to avoid
 * exhausting connections during hot reloads.
 */
const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({
    log: env.NODE_ENV === 'development' ? ['warn', 'error'] : ['error'],
  });

if (env.NODE_ENV !== 'production') {
  globalForPrisma.prisma = prisma;
}
