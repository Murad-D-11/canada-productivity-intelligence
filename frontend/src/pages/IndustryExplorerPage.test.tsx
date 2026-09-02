import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { IndustryExplorerPage } from './IndustryExplorerPage';
import * as api from '../lib/statcanApi';

vi.mock('../lib/statcanApi');

const mockedApi = vi.mocked(api);

afterEach(() => {
  vi.resetAllMocks();
});

describe('IndustryExplorerPage', () => {
  it('shows a loading state while dimensions load', () => {
    mockedApi.fetchIndustries.mockReturnValue(new Promise(() => {})); // never resolves
    mockedApi.fetchMeasures.mockReturnValue(new Promise(() => {}));
    render(<IndustryExplorerPage />);
    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it('shows an error state when the API fails', async () => {
    mockedApi.fetchIndustries.mockRejectedValue(new Error('backend down'));
    mockedApi.fetchMeasures.mockRejectedValue(new Error('backend down'));
    render(<IndustryExplorerPage />);
    await waitFor(() => expect(screen.getByText(/Couldn't load data/i)).toBeInTheDocument());
    expect(screen.getByText(/backend down/i)).toBeInTheDocument();
  });

  it('renders selectors and the chart once real data loads', async () => {
    mockedApi.fetchIndustries.mockResolvedValue([
      { memberId: 19, name: 'Total economy', classificationCode: null, parentMemberId: null },
    ]);
    mockedApi.fetchMeasures.mockResolvedValue([
      { memberId: 5, name: 'Labour productivity', unitOfMeasure: null },
    ]);
    mockedApi.fetchHistory.mockResolvedValue({
      data: [
        {
          period: '2020-01',
          periodStart: '2020-01-01',
          periodType: 'MONTHLY',
          value: 100,
          unit: 'Index, 2017=100',
          industry: 'Total economy',
          industryId: 19,
          measure: 'Labour productivity',
          measureId: 5,
          geography: 'Canada',
          coordinate: '1.5.19',
          vectorId: 1,
          statusCode: null,
        },
      ],
      pagination: { page: 1, pageSize: 500, total: 1, totalPages: 1 },
    });

    render(<IndustryExplorerPage />);
    await waitFor(() => expect(screen.getByLabelText('Industry')).toBeInTheDocument());
    expect(screen.getByLabelText('Measure')).toBeInTheDocument();
    await waitFor(() =>
      expect(
        document.querySelector('[aria-label="Historical productivity chart"]'),
      ).not.toBeNull(),
    );
  });

  it('shows an empty state when all values are suppressed', async () => {
    mockedApi.fetchIndustries.mockResolvedValue([
      { memberId: 2, name: 'Agriculture', classificationCode: '11', parentMemberId: 1 },
    ]);
    mockedApi.fetchMeasures.mockResolvedValue([
      { memberId: 5, name: 'Labour productivity', unitOfMeasure: null },
    ]);
    mockedApi.fetchHistory.mockResolvedValue({
      data: [
        {
          period: '2020-01',
          periodStart: '2020-01-01',
          periodType: 'MONTHLY',
          value: null,
          unit: 'Index, 2017=100',
          industry: 'Agriculture',
          industryId: 2,
          measure: 'Labour productivity',
          measureId: 5,
          geography: 'Canada',
          coordinate: '1.5.2',
          vectorId: 2,
          statusCode: '..',
        },
      ],
      pagination: { page: 1, pageSize: 500, total: 1, totalPages: 1 },
    });

    render(<IndustryExplorerPage />);
    await waitFor(() => expect(screen.getByText(/No values available/i)).toBeInTheDocument());
  });
});
