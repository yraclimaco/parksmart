import { describe, expect, it, vi } from 'vitest';
import { DEFAULT_DESTINATION_ID, getDestination } from '../data/destinations.ts';
import { resolveRecommendationSource } from '../config.ts';
import type { ParkingPlannerRequest } from '../types.ts';
import {
  fetchRecommendations,
  parseResponse,
  toApiRequest,
  type ApiRecommendationResponse,
} from './recommendations.ts';

const REQUEST: ParkingPlannerRequest = {
  destinationId: DEFAULT_DESTINATION_ID,
  arrivalDate: '2026-10-29',
  arrivalTime: '10:00',
  permitType: 'S',
};

function choice(locationId: string, fraction: number | null, walk: number | null) {
  return {
    location: { location_id: locationId, name: `Name ${locationId}`, coordinates: null },
    estimated_available_fraction: fraction,
    estimated_walking_minutes: walk,
    explanation: `Why ${locationId}`,
  };
}

function ready(overrides: Partial<ApiRecommendationResponse> = {}): ApiRecommendationResponse {
  return {
    status: 'ready',
    is_example: false,
    arrival_time: '2026-10-29T10:00:00-07:00',
    first_choice: choice('gilman-ps', 0.62, 8),
    backup_choice: choice('p406', null, null),
    explanation: 'Gilman scored highest.',
    limitations: ['Historical estimate, not live.'],
    ...overrides,
  };
}

/** A fetch stand-in that records the call and returns one response. */
function fakeFetch(status: number, body: unknown) {
  return vi.fn(async () =>
    new Response(typeof body === 'string' ? body : JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  );
}

describe('toApiRequest', () => {
  it('sends snake_case fields with local UCSD time and destination coordinates', () => {
    const destination = getDestination(DEFAULT_DESTINATION_ID);
    expect(toApiRequest(REQUEST)).toEqual({
      destination: {
        name: destination.name,
        coordinates: { latitude: destination.latitude, longitude: destination.longitude },
      },
      arrival_time: '2026-10-29T10:00:00',
      permit_type: 'S',
    });
  });

  it('returns null for an unknown destination', () => {
    expect(toApiRequest({ ...REQUEST, destinationId: 'nowhere' })).toBeNull();
  });
});

describe('fetchRecommendations', () => {
  it('posts to /recommendations and maps both choices', async () => {
    const fetchImpl = fakeFetch(200, ready());
    const outcome = await fetchRecommendations(REQUEST, { fetchImpl, baseUrl: 'http://api.test' });
    expect(fetchImpl).toHaveBeenCalledWith(
      'http://api.test/recommendations',
      expect.objectContaining({ method: 'POST' })
    );
    expect(outcome.kind).toBe('ok');
    if (outcome.kind !== 'ok') return;
    const [first, backup] = outcome.recommendations;
    expect(first.badgeLabel).toBe('First choice');
    expect(first.estimate).toEqual({ availablePercent: 62, walkingMinutes: 8, isExample: false });
    expect(first.reason).toBe('Why gilman-ps');
    // Known IDs reuse the website's verified pin
    expect(Number.isFinite(first.lot.latitude)).toBe(true);
    expect(backup.badgeLabel).toBe('Backup');
    // Unknown stays unknown: null, never 0
    expect(backup.estimate).toEqual({ availablePercent: null, walkingMinutes: null, isExample: false });
  });

  it('keeps a ready result without a backup', async () => {
    const outcome = await fetchRecommendations(REQUEST, {
      fetchImpl: fakeFetch(200, ready({ backup_choice: null })),
    });
    expect(outcome.kind === 'ok' && outcome.recommendations).toHaveLength(1);
  });

  it('returns no cards for evaluated empty results', async () => {
    const outcome = await fetchRecommendations(REQUEST, {
      fetchImpl: fakeFetch(200, ready({ status: 'no_suitable_location', first_choice: null, backup_choice: null })),
    });
    expect(outcome.kind).toBe('ok');
    if (outcome.kind === 'ok') {
      expect(outcome.recommendations).toEqual([]);
      expect(outcome.response.status).toBe('no_suitable_location');
    }
  });

  it('builds a pinless lot for IDs the website does not know', async () => {
    const outcome = await fetchRecommendations(REQUEST, {
      fetchImpl: fakeFetch(200, ready({ first_choice: choice('tdlln', 0.5, null), backup_choice: null })),
    });
    if (outcome.kind !== 'ok') throw new Error('expected ok');
    expect(outcome.recommendations[0].lot.name).toBe('Name tdlln');
    expect(Number.isNaN(outcome.recommendations[0].lot.latitude)).toBe(true);
  });

  it.each([
    [404, {}, 'not available right now'],
    [422, { detail: [{ msg: 'Arrival time does not exist in UCSD local time' }] }, 'does not exist in UCSD'],
    [500, {}, 'error 500'],
    [503, {}, 'error 503'],
    [200, 'not json', 'could not read'],
    [200, { status: 'ready' }, 'agreed format'],
    [200, ready({ first_choice: choice('x', 1.4, 3) }), 'agreed format'],
    [200, ready({ status: 'no_suitable_location' }), 'agreed format'],
  ])('explains HTTP %i problems', async (status, body, message) => {
    const outcome = await fetchRecommendations(REQUEST, { fetchImpl: fakeFetch(status, body) });
    expect(outcome.kind).toBe('error');
    if (outcome.kind === 'error') expect(outcome.message).toContain(message);
  });

  it('explains network failures without falling back to sample data', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const fetchImpl = vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    });
    const outcome = await fetchRecommendations(REQUEST, { fetchImpl, baseUrl: 'http://api.test' });
    expect(outcome).toEqual({
      kind: 'error',
      message: "Couldn't reach ParkSmart right now. Check your connection and try again.",
    });
    // Visitors get plain wording; the URL and CORS hint go to the console for developers
    expect(warn).toHaveBeenCalledWith(expect.stringContaining('http://api.test'));
    expect(warn).toHaveBeenCalledWith(expect.stringContaining('CORS'));
    warn.mockRestore();
  });

  it('gives up after the timeout instead of loading forever', async () => {
    vi.useFakeTimers();
    // A backend that never answers, but stops when its request is aborted
    const fetchImpl = vi.fn(
      (_url: string, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
        })
    );
    const pending = fetchRecommendations(REQUEST, { fetchImpl: fetchImpl as typeof fetch, timeoutMs: 5000 });
    await vi.advanceTimersByTimeAsync(5000);
    const outcome = await pending;
    vi.useRealTimers();
    expect(outcome.kind).toBe('error');
    if (outcome.kind === 'error') expect(outcome.message).toContain('taking too long');
  });

  it('still lets a newer search cancel a request that has a timeout', async () => {
    const controller = new AbortController();
    const fetchImpl = vi.fn(
      (_url: string, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
        })
    );
    const pending = fetchRecommendations(REQUEST, { fetchImpl: fetchImpl as typeof fetch, signal: controller.signal });
    controller.abort();
    await expect(pending).rejects.toThrow('Aborted');
  });

  it('lets aborts from a newer search propagate', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new DOMException('Aborted', 'AbortError');
    });
    await expect(fetchRecommendations(REQUEST, { fetchImpl })).rejects.toThrow('Aborted');
  });
});

describe('parseResponse', () => {
  it('accepts the proposed predictions_unavailable status', () => {
    expect(
      parseResponse(ready({ status: 'predictions_unavailable', first_choice: null, backup_choice: null }))
    ).not.toBeNull();
  });
});

describe('resolveRecommendationSource', () => {
  it('uses the backend only when explicitly set to api', () => {
    expect(resolveRecommendationSource('api')).toBe('api');
    expect(resolveRecommendationSource(' API ')).toBe('api');
    expect(resolveRecommendationSource(undefined)).toBe('sample');
    expect(resolveRecommendationSource('anything')).toBe('sample');
  });
});
