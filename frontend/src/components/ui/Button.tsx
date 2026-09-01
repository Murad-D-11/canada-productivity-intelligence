import type { ButtonHTMLAttributes } from 'react';
import { cn } from '../../lib/cn';

type Variant = 'primary' | 'secondary' | 'ghost';

const variantClasses: Record<Variant, string> = {
  primary: 'bg-brand text-white hover:bg-brand/90',
  secondary: 'border border-border bg-surface-raised text-content hover:bg-surface-sunken',
  ghost: 'text-content-muted hover:bg-surface-sunken',
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

/** Design-system button. Disabled state is dimmed and non-interactive. */
export function Button({ variant = 'primary', className, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-md px-3.5 py-2 text-sm font-medium',
        'transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand',
        'disabled:cursor-not-allowed disabled:opacity-50',
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  );
}
