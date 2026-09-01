import { Link } from 'react-router-dom';
import { PageHeader, Button } from '../components/ui';

/** Fallback route. */
export function NotFoundPage() {
  return (
    <>
      <PageHeader title="Page not found" description="The page you requested does not exist." />
      <Link to="/">
        <Button variant="secondary">Back to Overview</Button>
      </Link>
    </>
  );
}
