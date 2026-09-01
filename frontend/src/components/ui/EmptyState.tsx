import type { ReactNode } from 'react';

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: ReactNode;
}

/**
 * Honest empty state. Used wherever a page would show data once pipelines are
 * wired up. It communicates that no data is present rather than faking values.
 */
export function EmptyState({ title, description, icon }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-card border border-dashed border-border bg-surface-sunken/40 px-6 py-12 text-center">
      {icon ? <div className="text-content-subtle">{icon}</div> : null}
      <p className="text-sm font-medium text-content">{title}</p>
      <p className="max-w-md text-sm text-content-muted">{description}</p>
    </div>
  );
}
