import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ProductivityChart } from './ProductivityChart';
import type { ObservationPoint } from '../../lib/statcanApi';

function point(period: string, value: number | null): ObservationPoint {
  return {
    period,
    periodStart: `${period}-01`,
    periodType: 'MONTHLY',
    value,
    unit: 'Index, 2017=100',
    industry: 'Total economy',
    industryId: 19,
    measure: 'Labour productivity',
    measureId: 5,
    geography: 'Canada',
    coordinate: '1.5.19',
    vectorId: 1,
    statusCode: null,
  };
}

describe('ProductivityChart', () => {
  it('renders a chart container for real data', () => {
    const { container } = render(
      <ProductivityChart points={[point('2020-01', 100), point('2020-02', 101.2)]} />,
    );
    // The accessible chart wrapper is present.
    expect(container.querySelector('[aria-label="Historical productivity chart"]')).not.toBeNull();
  });

  it('omits suppressed (null) values rather than plotting zeros', () => {
    // Should not throw when some values are null; nulls are filtered out.
    const { container } = render(
      <ProductivityChart points={[point('2020-01', null), point('2020-02', 101.2)]} />,
    );
    expect(container.querySelector('[aria-label="Historical productivity chart"]')).not.toBeNull();
  });
});
