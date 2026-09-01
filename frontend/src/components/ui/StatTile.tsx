import { Card } from './Card';
import { cn } from '../../lib/cn';

interface StatTileProps {
  label: string;
  /** Rendered value. Use an em dash when no data is available. */
  value: string;
  hint?: string;
  className?: string;
}

/**
 * Compact KPI tile. In Milestone 3 these render placeholder values ("—")
 * because the app is not yet wired to data.
 */
export function StatTile({ label, value, hint, className }: StatTileProps) {
  return (
    <Card className={cn('px-5 py-4', className)}>
      <p className="text-sm text-content-muted">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-content">{value}</p>
      {hint ? <p className="mt-1 text-xs text-content-subtle">{hint}</p> : null}
    </Card>
  );
}
