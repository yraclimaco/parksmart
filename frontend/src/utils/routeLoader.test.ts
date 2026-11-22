import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ApiRoute, RouteTrip } from '../api/routes.ts';
import type { PlannedLeg } from './routePlan.ts';
import {
  ROUTES_UNAVAILABLE_MEMORY_MS,
  initialLegState,
  loadLeg,
  needsRequest,
  rememberRoutesUnavailable,
  resetRouteMemory,
  routesKnownUnavailable,
} from './routeLoader.ts';

const WALK: RouteTrip = {
  mode: 'walking',
  origin: { latitude: 32.8776, longitude: -117.2337 },
  destination: { latitude: 32.8811, longitude: -117.2376 },
};
const DRIVE: RouteTrip = {
  mode: 'driving',
  origin: { latitude: 32.85, longitude: -117.21 },
  destination: { latitude: 32.8776, longitude: -117.2337 },
};
const walkLeg: PlannedLeg = { mode: 'walking', trip: WALK };
const driveLeg: PlannedLeg = { mode: 'driving', trip: DRIVE };

const route: ApiRoute = {
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
  limitations: [],
};

const reply = (status: number, body: unknown) => vi.fn(async () => new Response(JSON.stringify(body), { status }));

beforeEach(() => resetRouteMemory());

describe('routing turned off on the backend', () => {
  it('asks once, then stops sending /routes requests for later searches', async () => {
    const fetchImpl = reply(503, { detail: 'Routes are not available on this server.' });

    expect(needsRequest(walkLeg)).toBe(true);
    const first = await loadLeg(WALK, { fetchImpl });
    expect(first.status).toBe('unavailable');
    expect(fetchImpl).toHaveBeenCalledTimes(1);

    // Every later search (another lot, another start) skips the request
    expect(needsRequest(walkLeg)).toBe(false);
    expect(needsRequest(driveLeg)).toBe(false);
    expect(needsRequest({ mode: 'walking', trip: { ...WALK, origin: { latitude: 32.9, longitude: -117.2 } } })).toBe(false);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it('shows "not available" straight away instead of a spinner for a request that is never sent', () => {
    expect(initialLegState(walkLeg)).toEqual({ status: 'loading' });
    rememberRoutesUnavailable();
    expect(initialLegState(walkLeg).status).toBe('unavailable');
  });

  it('treats an older backend with no /routes the same way', async () => {
    await loadLeg(WALK, { fetchImpl: reply(404, { detail: 'Not Found' }) });
    expect(needsRequest(driveLeg)).toBe(false);
  });

  it('asks again after the memory runs out, in case routing was turned on', () => {
    rememberRoutesUnavailable(1_000);
    expect(routesKnownUnavailable(1_000 + ROUTES_UNAVAILABLE_MEMORY_MS - 1)).toBe(true);
    expect(routesKnownUnavailable(1_000 + ROUTES_UNAVAILABLE_MEMORY_MS)).toBe(false);
  });

  it('does not remember an ordinary failure as "routing is off"', async () => {
    const outcome = await loadLeg(WALK, { fetchImpl: reply(500, { detail: 'boom' }) });
    expect(outcome.status).toBe('error');
    expect(needsRequest(walkLeg)).toBe(true);
  });

  it('does not remember a gateway or cold-start 503 either, so the next search can still get routes', async () => {
    const outcome = await loadLeg(WALK, { fetchImpl: reply(503, { message: 'Service Unavailable' }) });
    expect(outcome.status).toBe('error');
    expect(needsRequest(walkLeg)).toBe(true);
    expect(needsRequest(driveLeg)).toBe(true);
  });
});

describe('driving and walking legs sent together', () => {
  it('sends one request when routing is off, not one per leg', async () => {
    const fetchImpl = reply(503, { detail: 'Routes are not available on this server.' });
    const [driving, walking] = await Promise.all([loadLeg(DRIVE, { fetchImpl }), loadLeg(WALK, { fetchImpl })]);
    expect(driving.status).toBe('unavailable');
    expect(walking.status).toBe('unavailable');
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it('sends both once routing is known to be on', async () => {
    const fetchImpl = reply(200, route);
    const [driving, walking] = await Promise.all([loadLeg(DRIVE, { fetchImpl }), loadLeg(WALK, { fetchImpl })]);
    expect(driving.status).toBe('ok');
    expect(walking.status).toBe('ok');
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    // From now on legs no longer wait in line
    const again = await loadLeg({ ...WALK, destination: { latitude: 32.9, longitude: -117.2 } }, { fetchImpl });
    expect(again.status).toBe('ok');
    expect(fetchImpl).toHaveBeenCalledTimes(3);
  });

  it('when the first request is cancelled, only one waiting leg goes next (not both)', async () => {
    let calls = 0;
    const fetchImpl = vi.fn(async (_url: unknown, init?: RequestInit) => {
      calls += 1;
      if (calls === 1) {
        // The first request hangs until it is cancelled, like a search superseded by a newer one
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => reject(Object.assign(new Error('aborted'), { name: 'AbortError' })));
        });
      }
      return new Response(JSON.stringify({ detail: 'Routes are not available on this server.' }), { status: 503 });
    }) as unknown as typeof fetch;

    const controller = new AbortController();
    const first = loadLeg(WALK, { fetchImpl, signal: controller.signal });
    const waiters = Promise.all([loadLeg(DRIVE, { fetchImpl }), loadLeg({ ...WALK, origin: DRIVE.origin }, { fetchImpl })]);
    controller.abort();
    await expect(first).rejects.toThrow();
    const [a, b] = await waiters;
    expect(a.status).toBe('unavailable');
    expect(b.status).toBe('unavailable');
    expect(fetchImpl).toHaveBeenCalledTimes(2); // the cancelled one, then exactly one more
  });

  it('lets the second leg try when the first request was cancelled', async () => {
    const aborted = vi.fn(async () => {
      throw Object.assign(new Error('aborted'), { name: 'AbortError' });
    });
    await expect(loadLeg(DRIVE, { fetchImpl: aborted as unknown as typeof fetch })).rejects.toThrow();
    const fetchImpl = reply(200, route);
    expect((await loadLeg(WALK, { fetchImpl })).status).toBe('ok');
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});

describe('saved routes', () => {
  it('never asks twice for the same trip', async () => {
    const fetchImpl = reply(200, route);
    const first = await loadLeg(WALK, { fetchImpl });
    expect(first.status).toBe('ok');
    expect(needsRequest(walkLeg)).toBe(false);
    expect(initialLegState(walkLeg)).toEqual({ status: 'ok', route });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it('has nothing to ask for when a leg was skipped', () => {
    const skipped: PlannedLeg = { mode: 'driving', skipped: 'Add a starting point to see driving directions.' };
    expect(needsRequest(skipped)).toBe(false);
    expect(initialLegState(skipped).status).toBe('skipped');
  });
});
