/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Client for the ParkSmart backend's POST /routes (src/api/main.py and
 * docs/routing.md in yraclimaco/parksmart). The backend holds the routing
 * provider's key; the website never calls a provider directly.
 */

import { API_BASE_URL } from '../config.ts';
import { withTimeout } from './timeout.ts';

export type TravelMode = 'driving' | 'walking';

export interface LatLng {
  latitude: number;
  longitude: number;
}

export interface RouteTrip {
  mode: TravelMode;
  origin: LatLng;
  destination: LatLng;
}

export interface ApiRoute {
  schema_version: string;
  mode: TravelMode;
  distance_meters: number;
  distance_miles: number;
  duration_minutes: number;
  /** GeoJSON order: [longitude, latitude] pairs from origin to destination. */
  geometry: number[][];
  /** Always false: providers give typical times, never live traffic. */
  traffic_aware: false;
  provider: string;
  attribution: string;
  limitations: string[];
}

export type RouteOutcome =
  | { kind: 'ok'; route: ApiRoute }
  /** Routing is turned off on this backend (503). Recommendations still work. */
  | { kind: 'unavailable'; message: string }
  | { kind: 'error'; message: string };

/**
 * Where people report wrong roads or paths in OpenStreetMap, the data behind
 * every route. Shown next to the route attribution, as OSM asks of map users.
 */
export const OSM_FIX_THE_MAP_URL = 'https://www.openstreetmap.org/fixthemap';

/** Routes are small requests; give up sooner than a recommendation search. */
export const ROUTE_TIMEOUT_MS = 12_000;

const FAILED = "Directions couldn't load right now. Try again in a moment.";
const UNAVAILABLE: RouteOutcome = { kind: 'unavailable', message: 'Directions are not set up on this server yet.' };
/** FastAPI's body for a path that does not exist. */
const NO_SUCH_ENDPOINT = 'Not Found';

/** Asks the backend for one driving or walking route. Rejects only when cancelled. */
export async function fetchRoute(
  trip: RouteTrip,
  options: { fetchImpl?: typeof fetch; signal?: AbortSignal; baseUrl?: string; timeoutMs?: number } = {}
): Promise<RouteOutcome> {
  const { signal, timeoutMs = ROUTE_TIMEOUT_MS, fetchImpl = fetch, baseUrl = API_BASE_URL } = options;
  return withTimeout<RouteOutcome>(
    async (combined) => {
      let response: Response;
      try {
        response = await fetchImpl(`${baseUrl}/routes`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(trip),
          signal: combined,
        });
      } catch (error) {
        if ((error as Error)?.name === 'AbortError') throw error;
        console.warn(`[ParkSmart] Could not reach ${baseUrl}/routes.`, error);
        return { kind: 'error', message: FAILED };
      }
      if (response.status === 503) return UNAVAILABLE;
      if (response.status === 404 || response.status === 400) {
        const message = await detail(response);
        // FastAPI's generic 404 means this backend has no /routes yet (older version)
        if (response.status === 404 && message === NO_SUCH_ENDPOINT) return UNAVAILABLE;
        // Otherwise the backend's own wording: no path found, or a trip too long
        return { kind: 'error', message: message ?? FAILED };
      }
      if (!response.ok) return { kind: 'error', message: FAILED };
      let data: unknown;
      try {
        data = await response.json();
      } catch (error) {
        if ((error as Error)?.name === 'AbortError') throw error;
        return { kind: 'error', message: FAILED };
      }
      const parsed = parseRoute(data);
      if (!parsed) {
        console.warn('[ParkSmart] /routes response did not match the agreed format:', data);
        return { kind: 'error', message: FAILED };
      }
      return { kind: 'ok', route: parsed };
    },
    () => ({ kind: 'error', message: FAILED }),
    { signal, timeoutMs }
  );
}

async function detail(response: Response): Promise<string | null> {
  try {
    const body = await response.json();
    return typeof body?.detail === 'string' ? body.detail : null;
  } catch {
    return null;
  }
}

const isNonNegative = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0;

/** Checks the response shape; null if it is not the agreed contract. */
export function parseRoute(data: unknown): ApiRoute | null {
  if (typeof data !== 'object' || data === null) return null;
  const route = data as Record<string, unknown>;
  if (route.mode !== 'driving' && route.mode !== 'walking') return null;
  if (route.traffic_aware !== false) return null;
  if (![route.distance_meters, route.distance_miles, route.duration_minutes].every(isNonNegative)) return null;
  const { geometry } = route;
  if (
    !Array.isArray(geometry) ||
    geometry.length < 2 ||
    !geometry.every(
      (pair) => Array.isArray(pair) && pair.length >= 2 && pair.every((n) => typeof n === 'number' && Number.isFinite(n))
    )
  ) {
    return null;
  }
  if (typeof route.provider !== 'string' || typeof route.attribution !== 'string') return null;
  if (!Array.isArray(route.limitations) || !route.limitations.every((note) => typeof note === 'string')) return null;
  return route as unknown as ApiRoute;
}
