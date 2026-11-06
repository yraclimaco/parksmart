import { describe, expect, it, vi } from 'vitest';
import { OSM_FIX_THE_MAP_URL, fetchRoute, parseRoute, type ApiRoute } from './routes.ts';

const TRIP = {
  mode: 'walking' as const,
  origin: { latitude: 32.8776, longitude: -117.2337 },
  destination: { latitude: 32.8811, longitude: -117.2376 },
};

function route(overrides: Partial<ApiRoute> = {}): ApiRoute {
  return {
    schema_version: '0.1',
    mode: 'walking',
    distance_meters: 812.4,
    distance_miles: 0.5,
    duration_minutes: 9.7,
    geometry: [
      [-117.2337, 32.8776],
      [-117.2376, 32.8811],
    ],
    traffic_aware: false,
    provider: 'OSRM (OpenStreetMap data)',
    attribution: 'Route data © OpenStreetMap contributors',
    limitations: ['Starts at the map point.'],
    ...overrides,
  };
}

function fakeFetch(status: number, body: unknown) {
  return vi.fn(async () => new Response(typeof body === 'string' ? body : JSON.stringify(body), { status }));
}

describe('fetchRoute', () => {
  it('posts the trip to /routes and returns the route', async () => {
    const fetchImpl = fakeFetch(200, route());
    const outcome = await fetchRoute(TRIP, { fetchImpl, baseUrl: 'http://api.test' });
    expect(fetchImpl).toHaveBeenCalledWith(
      'http://api.test/routes',
      expect.objectContaining({ method: 'POST', body: JSON.stringify(TRIP) })
    );
    expect(outcome).toEqual({ kind: 'ok', route: route() });
  });

  it('treats an older backend without /routes as directions being off', async () => {
    // FastAPI answers unknown paths with 404 {"detail": "Not Found"}
    const outcome = await fetchRoute(TRIP, { fetchImpl: fakeFetch(404, { detail: 'Not Found' }) });
    expect(outcome.kind).toBe('unavailable');
  });

  it('treats 503 as routes being turned off, not as a failure', async () => {
    const outcome = await fetchRoute(TRIP, { fetchImpl: fakeFetch(503, { detail: 'off' }) });
    expect(outcome.kind).toBe('unavailable');
  });

  it.each([
    [404, { detail: 'No road or path was found near one of the points.' }, 'No road or path'],
    [400, { detail: 'Walking routes are limited to 5 km in a straight line.' }, 'limited to 5 km'],
    [502, { detail: 'down' }, "couldn't load"],
    [500, {}, "couldn't load"],
    [200, 'not json', "couldn't load"],
    [200, route({ geometry: [[-117.2, 32.8]] }), "couldn't load"],
    [200, route({ duration_minutes: -1 }), "couldn't load"],
  ])('explains HTTP %i problems', async (status, body, message) => {
    const outcome = await fetchRoute(TRIP, { fetchImpl: fakeFetch(status, body) });
    expect(outcome.kind).toBe('error');
    if (outcome.kind === 'error') expect(outcome.message).toContain(message);
  });

  it('explains network failures', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const fetchImpl = vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    });
    const outcome = await fetchRoute(TRIP, { fetchImpl });
    expect(outcome.kind).toBe('error');
    warn.mockRestore();
  });

  it('times out instead of loading forever', async () => {
    vi.useFakeTimers();
    const fetchImpl = vi.fn(
      (_url: string, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
        })
    );
    const pending = fetchRoute(TRIP, { fetchImpl: fetchImpl as typeof fetch, timeoutMs: 1000 });
    await vi.advanceTimersByTimeAsync(1000);
    const outcome = await pending;
    vi.useRealTimers();
    expect(outcome.kind).toBe('error');
  });

  it('lets a newer selection cancel the request', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new DOMException('Aborted', 'AbortError');
    });
    await expect(fetchRoute(TRIP, { fetchImpl })).rejects.toThrow('Aborted');
  });
});

describe('parseRoute', () => {
  it('never accepts a traffic-aware claim the website cannot explain', () => {
    expect(parseRoute({ ...route(), traffic_aware: true })).toBeNull();
  });
});

describe('OpenStreetMap attribution', () => {
  it('links to the OSM page for reporting map errors', () => {
    expect(OSM_FIX_THE_MAP_URL).toBe('https://www.openstreetmap.org/fixthemap');
  });
});
