/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Client for the ParkSmart backend's POST /trip-alerts (docs/trip_alerts.md in
 * yraclimaco/parksmart): forecast weather and published UCSD construction notices for
 * one arrival and parking point. It is separate from /recommendations, so a failure here
 * never blocks a parking search, and it never changes availability or ranking.
 */

import { API_BASE_URL } from '../config.ts';
import { withTimeout } from './timeout.ts';

export type SourceStatus =
  | 'available'
  | 'no_relevant'
  | 'partial'
  | 'stale'
  | 'unavailable'
  | 'out_of_range'
  | 'missing_location';

const SOURCE_STATUSES: readonly string[] = [
  'available',
  'no_relevant',
  'partial',
  'stale',
  'unavailable',
  'out_of_range',
  'missing_location',
];

export interface TripAlert {
  alert_id: string;
  alert_type: 'weather' | 'construction';
  /** Plain text from the source. Render as text, never as HTML. */
  message: string;
  relevant_from: string | null;
  relevant_until: string | null;
  /** How a construction notice matched the trip: 'intersects_geometry' or 'within_200m'. */
  match_basis: string | null;
  source_name: string;
  source_url: string;
  limitations: string[];
}

export interface WeatherForecast {
  /** Whole-hour sample for temperature, wind and weather code. */
  forecast_time: string;
  temperature_c: number | null;
  apparent_temperature_c: number | null;
  precipitation_probability_percent: number | null;
  /** Describes the hour BEFORE forecast_time, not the hour after. */
  precipitation_mm: number | null;
  wind_speed_kmh: number | null;
}

export interface AlertSource {
  status: SourceStatus;
  source_name: string;
  source_url: string;
  /** Last successful retrieval of the data shown, or null. Not a publication time. */
  last_checked_at: string | null;
  alerts: TripAlert[];
  forecast: WeatherForecast | null;
  limitations: string[];
}

export interface TripAlertsResponse {
  weather: AlertSource;
  construction: AlertSource;
  limitations: string[];
}

export interface TripAlertsQuery {
  /** Local arrival, "YYYY-MM-DDTHH:mm:ss"; the backend reads it as UCSD time. */
  arrivalTime: string;
  /** Registry location_id of the chosen parking location. */
  parkingLocationId: string;
  destination: { name: string; latitude: number; longitude: number } | null;
}

export type TripAlertsOutcome =
  | { kind: 'ok'; alerts: TripAlertsResponse }
  /** This backend has no /trip-alerts yet (older version) or has alerts switched off. */
  | { kind: 'unavailable'; message: string }
  | { kind: 'error'; message: string };

/** Alerts are optional extras; give up sooner than a recommendation search. */
export const TRIP_ALERTS_TIMEOUT_MS = 10_000;

const FAILED = "Trip alerts couldn't load right now. Parking results are not affected.";
const UNAVAILABLE: TripAlertsOutcome = {
  kind: 'unavailable',
  message: 'Trip alerts are not set up on this server yet.',
};
/** FastAPI's body for a path that does not exist. */
const NO_SUCH_ENDPOINT = 'Not Found';

/** Asks the backend for alerts. Rejects only when cancelled through `signal`. */
export async function fetchTripAlerts(
  query: TripAlertsQuery,
  options: { fetchImpl?: typeof fetch; signal?: AbortSignal; baseUrl?: string; timeoutMs?: number } = {}
): Promise<TripAlertsOutcome> {
  const { signal, timeoutMs = TRIP_ALERTS_TIMEOUT_MS, fetchImpl = fetch, baseUrl = API_BASE_URL } = options;
  const body = {
    arrival_time: query.arrivalTime,
    parking_location_id: query.parkingLocationId,
    ...(query.destination
      ? {
          destination: {
            name: query.destination.name,
            coordinates: { latitude: query.destination.latitude, longitude: query.destination.longitude },
          },
        }
      : {}),
  };
  return withTimeout<TripAlertsOutcome>(
    async (combined) => {
      let response: Response;
      try {
        response = await fetchImpl(`${baseUrl}/trip-alerts`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: combined,
        });
      } catch (error) {
        if ((error as Error)?.name === 'AbortError') throw error;
        console.warn(`[ParkSmart] Could not reach ${baseUrl}/trip-alerts.`, error);
        return { kind: 'error', message: FAILED };
      }
      if (response.status === 503) return UNAVAILABLE;
      if (response.status === 404 && (await detail(response)) === NO_SUCH_ENDPOINT) return UNAVAILABLE;
      if (!response.ok) return { kind: 'error', message: FAILED };
      let data: unknown;
      try {
        data = await response.json();
      } catch (error) {
        if ((error as Error)?.name === 'AbortError') throw error;
        return { kind: 'error', message: FAILED };
      }
      const parsed = parseTripAlerts(data);
      if (!parsed) {
        console.warn('[ParkSmart] /trip-alerts response did not match the agreed format:', data);
        return { kind: 'error', message: FAILED };
      }
      return { kind: 'ok', alerts: parsed };
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

const isString = (value: unknown): value is string => typeof value === 'string';
const isNumberOrNull = (value: unknown): value is number | null =>
  value === null || (typeof value === 'number' && Number.isFinite(value));
const isStringList = (value: unknown): value is string[] => Array.isArray(value) && value.every(isString);

function parseAlert(data: unknown): TripAlert | null {
  if (typeof data !== 'object' || data === null) return null;
  const a = data as Record<string, unknown>;
  if (a.alert_type !== 'weather' && a.alert_type !== 'construction') return null;
  if (![a.alert_id, a.message, a.source_name, a.source_url].every(isString)) return null;
  if (!(a.relevant_from === null || isString(a.relevant_from))) return null;
  if (!(a.relevant_until === null || isString(a.relevant_until))) return null;
  if (!isStringList(a.limitations)) return null;
  return { ...(a as unknown as TripAlert), match_basis: isString(a.match_basis) ? a.match_basis : null };
}

function parseForecast(data: unknown): WeatherForecast | null | undefined {
  if (data === null || data === undefined) return null;
  if (typeof data !== 'object') return undefined;
  const f = data as Record<string, unknown>;
  if (!isString(f.forecast_time)) return undefined;
  const numbers = [
    f.temperature_c,
    f.apparent_temperature_c,
    f.precipitation_probability_percent,
    f.precipitation_mm,
    f.wind_speed_kmh,
  ];
  if (!numbers.every(isNumberOrNull)) return undefined;
  return f as unknown as WeatherForecast;
}

function parseSource(data: unknown): AlertSource | null {
  if (typeof data !== 'object' || data === null) return null;
  const s = data as Record<string, unknown>;
  if (!isString(s.status) || !SOURCE_STATUSES.includes(s.status)) return null;
  if (!isString(s.source_name) || !isString(s.source_url)) return null;
  if (!(s.last_checked_at === null || isString(s.last_checked_at))) return null;
  if (!Array.isArray(s.alerts) || !isStringList(s.limitations)) return null;
  const alerts = s.alerts.map(parseAlert);
  if (alerts.some((alert) => alert === null)) return null;
  const forecast = parseForecast(s.forecast);
  if (forecast === undefined) return null;
  return {
    status: s.status as SourceStatus,
    source_name: s.source_name,
    source_url: s.source_url,
    last_checked_at: (s.last_checked_at as string | null) ?? null,
    alerts: alerts as TripAlert[],
    forecast,
    limitations: s.limitations,
  };
}

/** Checks the response shape; null if it is not the agreed contract. */
export function parseTripAlerts(data: unknown): TripAlertsResponse | null {
  if (typeof data !== 'object' || data === null) return null;
  const d = data as Record<string, unknown>;
  const weather = parseSource(d.weather);
  const construction = parseSource(d.construction);
  if (!weather || !construction || !isStringList(d.limitations)) return null;
  return { weather, construction, limitations: d.limitations };
}
