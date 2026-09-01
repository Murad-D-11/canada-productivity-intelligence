import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

interface CardProps {
  children: ReactNode;
  className?: string;
}

/** Elevated surface container used throughout the analytics pages. */
export function Card({ children, className }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-card border border-border bg-surface-raised shadow-card',
        className,
      )}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
}

/** Standard card header with a title, optional description, and actions slot. */
export function CardHeader({ title, description, actions }: CardHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
      <div>
        <h3 className="text-sm font-semibold text-content">{title}</h3>
        {description ? <p className="mt-1 text-sm text-content-muted">{description}</p> : null}
      </div>
      {actions ? <div className="shrink-0">{actions}</div> : null}
    </div>
  );
}

/** Padded body region for card content. */
export function CardBody({ children, className }: CardProps) {
  return <div className={cn('px-5 py-4', className)}>{children}</div>;
}
