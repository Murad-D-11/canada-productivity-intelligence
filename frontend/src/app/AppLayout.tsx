import { NavLink, Outlet } from 'react-router-dom';
import { navItems } from './navigation';
import { cn } from '../lib/cn';
import { Badge } from '../components/ui';

/**
 * Application shell: fixed sidebar navigation + top bar + routed content.
 * Layout only — no data fetching happens here in Milestone 3.
 */
export function AppLayout() {
  return (
    <div className="flex min-h-screen bg-surface text-content">
      <aside className="hidden w-64 shrink-0 border-r border-border bg-surface-raised lg:flex lg:flex-col">
        <div className="flex items-center gap-2 border-b border-border px-5 py-4">
          <span className="inline-block h-6 w-1.5 rounded-full bg-brand" aria-hidden />
          <div>
            <p className="text-sm font-semibold leading-tight">Canada Productivity</p>
            <p className="text-xs text-content-muted">Intelligence</p>
          </div>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                cn(
                  'block rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-brand/10 text-brand'
                    : 'text-content-muted hover:bg-surface-sunken hover:text-content',
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-border px-5 py-4">
          <Badge tone="caution">Prototype</Badge>
          <p className="mt-2 text-xs text-content-subtle">
            Design shell. Not yet connected to live data.
          </p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border bg-surface-raised px-6 py-3">
          <p className="text-sm font-medium text-content-muted">
            Canadian productivity decision support
          </p>
          <Badge tone="info">v0.1.0</Badge>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 space-y-6 px-6 py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
