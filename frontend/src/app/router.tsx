import { createBrowserRouter } from 'react-router-dom';
import { AppLayout } from './AppLayout';
import { OverviewPage } from '../pages/OverviewPage';
import { IndustryExplorerPage } from '../pages/IndustryExplorerPage';
import { ForecastPage } from '../pages/ForecastPage';
import { DriversPage } from '../pages/DriversPage';
import { ScenarioSimulatorPage } from '../pages/ScenarioSimulatorPage';
import { MethodologyPage } from '../pages/MethodologyPage';
import { DataStatusPage } from '../pages/DataStatusPage';
import { NotFoundPage } from '../pages/NotFoundPage';

/** Application routes. Every route renders inside the shared AppLayout. */
export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: 'industries', element: <IndustryExplorerPage /> },
      { path: 'forecast', element: <ForecastPage /> },
      { path: 'drivers', element: <DriversPage /> },
      { path: 'scenario', element: <ScenarioSimulatorPage /> },
      { path: 'methodology', element: <MethodologyPage /> },
      { path: 'data-status', element: <DataStatusPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
