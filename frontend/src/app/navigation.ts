/** Central navigation definition consumed by the router and the sidebar. */
export interface NavItem {
  path: string;
  label: string;
  /** One-line summary shown as the page description. */
  summary: string;
}

export const navItems: NavItem[] = [
  { path: '/', label: 'Overview', summary: 'National productivity snapshot and recent movements.' },
  {
    path: '/industries',
    label: 'Industry Explorer',
    summary: 'Compare productivity across NAICS industries and geographies.',
  },
  {
    path: '/forecast',
    label: 'Forecast',
    summary: 'One-step-ahead labour productivity forecasts with real backtest context.',
  },
  {
    path: '/drivers',
    label: 'Drivers',
    summary: 'Model contributions behind each forecast (association, not causation).',
  },
  {
    path: '/scenario',
    label: 'Scenario Simulator',
    summary: 'Explore model-implied outcomes under what-if adjustments.',
  },
  {
    path: '/methodology',
    label: 'Methodology',
    summary: 'How data is sourced, modeled, and evaluated.',
  },
  {
    path: '/data-status',
    label: 'Data Status',
    summary: 'Freshness, coverage, and provenance of configured data sources.',
  },
];
