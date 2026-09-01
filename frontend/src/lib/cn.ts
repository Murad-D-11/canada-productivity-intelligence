/**
 * Minimal className combiner. Joins truthy class fragments with a space.
 * Kept dependency-free to avoid pulling in clsx for a trivial need.
 */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ');
}
