import { describe, expect, it, vi } from 'vitest';
import { fetchTripAlerts, parseTripAlerts, type TripAlertsQuery } from './tripAlerts.ts';

const QUERY: TripAlertsQuery = {
  arrivalTime: '2026-11-18T10:00:00',
  parkingLocationId: 'gilman-ps',
  destination: { name: 'Geisel Library', latitude: 32.8811, longitude: -117.2376 },
};

const source = (overrides: Record<string, unknown> = {}) => ({
  status: 'available',
  source_name: 'Open-Meteo',
  source_url: 'https://open-meteo.com/',
  last_checked_at: '2026-11-17T18:00:00-08:00',
  alerts: [],
  forecast: null,
  limitations: [],
  ...overrides,
});

const response = (overrides: Record<string, unknown> = {}) => ({
  schema_version: '0.1',
  is_example: false,
  weather: source(),
  construction: source({ status: 'no_relevant', source_name: 'UCSD construction' }),
  limitations: [],
  ...overrides,
});

const fakeFetch = (status: number, body: unknown) =>
  vi.fn(async () => new Response(typeof body === 'string' ? body : JSON.stringify(body), { status }));

describe('fetchTripAlerts', () => {
  it('posts the arrival, parking id and destination coordinates to /trip-alerts', async () => {
    const fetchImpl = fakeFetch(200, response());
    const outcome = await fetchTripAlerts(QUERY, { fetchImpl, baseUrl: 'http://api.test' });
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('http://api.test/trip-alerts');
    expect(JSON.parse(init.body as string)).toEqual({
      arrival_time: '2026-11-18T10:00:00',
      parking_location_id: 'gilman-ps',
      destination: { name: 'Geisel Library', coordinates: { latitude: 32.8811, longitude: -117.2376 } },
    });
    expect(outcome.kind).toBe('ok');
  });

  it('omits the destination when there is none', async () => {
    const fetchImpl = fakeFetch(200, response());
    await fetchTripAlerts({ ...QUERY, destination: null }, { fetchImpl, baseUrl: 'http://api.test' });
    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string)).not.toHaveProperty('destination');
  });

  it('treats 503 and the generic 404 as "not set up", not as an error', async () => {
    expect((await fetchTripAlerts(QUERY, { fetchImpl: fakeFetch(503, {}) })).kind).toBe('unavailable');
    expect((await fetchTripAlerts(QUERY, { fetchImpl: fakeFetch(404, { detail: 'Not Found' }) })).kind).toBe('unavailable');
  });

  it('reports other failures as an error that says parking results are fine', async () => {
    const outcome = await fetchTripAlerts(QUERY, { fetchImpl: fakeFetch(500, {}) });
    expect(outcome).toMatchObject({ kind: 'error' });
    expect((outcome as { message: string }).message).toMatch(/Parking results are not affected/);
  });

  it('reports a network failure as an error', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError('network down');
    });
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect((await fetchTripAlerts(QUERY, { fetchImpl })).kind).toBe('error');
  });

  it('rejects a response that does not match the contract', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect((await fetchTripAlerts(QUERY, { fetchImpl: fakeFetch(200, { weather: {} }) })).kind).toBe('error');
  });

  it('rethrows a cancellation so a newer choice can replace it', async () => {
    const controller = new AbortController();
    const fetchImpl = vi.fn(async () => {
      controller.abort();
      throw Object.assign(new Error('aborted'), { name: 'AbortError' });
    });
    await expect(fetchTripAlerts(QUERY, { fetchImpl, signal: controller.signal })).rejects.toThrow();
  });
});

describe('parseTripAlerts', () => {
  it('accepts every documented source status', () => {
    for (const status of ['available', 'no_relevant', 'partial', 'stale', 'unavailable', 'out_of_range', 'missing_location']) {
      expect(parseTripAlerts(response({ weather: source({ status }) }))).not.toBeNull();
    }
  });

  it('rejects an unknown status rather than guessing what it means', () => {
    expect(parseTripAlerts(response({ weather: source({ status: 'all_clear' }) }))).toBeNull();
  });

  it('keeps unknown forecast values as null, never zero', () => {
    const forecast = {
      forecast_time: '2026-11-18T10:00:00-08:00',
      temperature_c: 16,
      apparent_temperature_c: null,
      precipitation_probability_percent: null,
      precipitation_mm: null,
      wind_speed_kmh: null,
    };
    const parsed = parseTripAlerts(response({ weather: source({ forecast }) }));
    expect(parsed?.weather.forecast?.wind_speed_kmh).toBeNull();
  });

  it('rejects a malformed alert or forecast', () => {
    expect(parseTripAlerts(response({ weather: source({ alerts: [{ message: 5 }] }) }))).toBeNull();
    expect(parseTripAlerts(response({ weather: source({ forecast: { forecast_time: 3 } }) }))).toBeNull();
  });
});

describe('parseTripAlerts match basis', () => {
  const alert = (extra: Record<string, unknown>) => ({
    alert_id: 'a1',
    alert_type: 'construction',
    message: 'Published construction notice: Road work.',
    relevant_from: null,
    relevant_until: null,
    source_name: 'UCSD',
    source_url: 'https://example.org',
    limitations: [],
    ...extra,
  });

  it('keeps how a notice matched the trip, and tolerates a missing value', () => {
    const withBasis = parseTripAlerts(response({ construction: source({ alerts: [alert({ match_basis: 'within_200m' })] }) }));
    expect(withBasis?.construction.alerts[0].match_basis).toBe('within_200m');
    const without = parseTripAlerts(response({ construction: source({ alerts: [alert({})] }) }));
    expect(without?.construction.alerts[0].match_basis).toBeNull();
  });
});
