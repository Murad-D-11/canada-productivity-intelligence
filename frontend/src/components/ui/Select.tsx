import type { SelectHTMLAttributes } from 'react';
import { cn } from '../../lib/cn';

interface Option {
  value: string | number;
  label: string;
}

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  label: string;
  options: Option[];
}

/** Design-system labelled select control. */
export function Select({ label, options, className, id, ...props }: SelectProps) {
  const selectId = id ?? `select-${label.toLowerCase().replace(/\s+/g, '-')}`;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={selectId} className="text-sm font-medium text-content-muted">
        {label}
      </label>
      <select
        id={selectId}
        className={cn(
          'rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-content',
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand',
          'disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
        {...props}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
