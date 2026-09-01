import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

type BadgeTone = 'neutral' | 'positive' | 'negative' | 'caution' | 'info';

const toneClasses: Record<BadgeTone, string> = {
  neutral: 'bg-surface-sunken text-content-muted',
  positive: 'bg-positive/10 text-positive',
  negative: 'bg-negative/10 text-negative',
  caution: 'bg-caution/10 text-caution',
  info: 'bg-info/10 text-info',
};

interface BadgeProps {
  children: ReactNode;
  tone?: BadgeTone;
  className?: string;
}

/** Small status pill. Tone maps to a semantic design token. */
export function Badge({ children, tone = 'neutral', className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        toneClasses[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
