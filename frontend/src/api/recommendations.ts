/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Client for the ParkSmart FastAPI backend's POST /recommendations.
 *
 * Field names follow the backend contract (docs/backend.md and
 * src/api/schemas.py in yraclimaco/parksmart): snake_case JSON, availability
 * as a 0-1 fraction, walking time in minutes, and null for anything unknown.
 * Null is never shown as 0.
 */

import { API_BASE_URL } from '../config.ts';
import { ALL_PARKING } from '../data/parkingLots.ts';
import { findDestination } from '../data/destinations.ts';
import type { ParkingLot, ParkingPlannerRequest, ParkingRecommendation } from '../types.ts';

export interface ApiCoordinates {
  latitude: number;
  longitude: number;
}

export interface ApiLocation {
  location_id: string;
  name: string;
  coordinates: ApiCoordinates | null;
}

export interface ApiChoice {
  location: ApiLocation;
  estimated_available_fraction: number | null;
  estimated_walking_minutes: number | null;
  explanation: string;
}

/** Backend result states. predictions_unavailable is the proposed addition from #20. */
export type ApiStatus = 'ready' | 'no_suitable_location' | 'not_implemented' | 'predictions_unavailable';

export interface ApiRecommendationResponse {
  status: ApiStatus;
  is_example: boolean;
  arrival_time: string;
  first_choice: ApiChoice | null;
  backup_choice: ApiChoice | null;
  explanation: string;
  limitations: string[];
}

export interface ApiRecommendationRequest {
  destination: { name: string; coordinates: ApiCoordinates | null };
  /** Local UCSD time without an offset, e.g. "2026-10-29T10:00:00". */
  arrival_time: string;
  permit_type: string;
}

/** What the website does with a request: show results, or explain why it can't. */
export type RecommendationOutcome =
  | { kind: 'ok'; response: ApiRecommendationResponse; recommendations: ParkingRecommendation[] }
  | { kind: 'error'; message: string };

const STATUSES: ReadonlySet<string> = new Set([
  'ready',
  'no_suitable_location',
  'not_implemented',
  'predictions_unavailable',
]);

/** Builds the JSON body; null if the destination is unknown. */
export function toApiRequest(request: ParkingPlannerRequest): ApiRecommendationRequest | null {
  const destination = findDestination(request.destinationId);
  if (!destination) return null;
  return {
    destination: {
      name: destination.name,
      coordinates: { latitude: destination.latitude, longitude: destination.longitude },
    },
    arrival_time: `${request.arrivalDate}T${request.arrivalTime}:00`,
    permit_type: request.permitType,
  };
}

/**
 * Sends the trip to the backend and returns results or a message to show.
 * Never throws for HTTP or network problems, and never falls back to sample data.
 */
export async function fetchRecommendations(
  request: ParkingPlannerRequest,
  options: { fetchImpl?: typeof fetch; signal?: AbortSignal; baseUrl?: string } = {}
): Promise<RecommendationOutcome> {
  const body = toApiRequest(request);
  if (!body) return { kind: 'error', message: 'Pick a destination from the list first.' };
  const baseUrl = options.baseUrl ?? API_BASE_URL;
  const fetchImpl = options.fetchImpl ?? fetch;

  let response: Response;
  try {
    response = await fetchImpl(`${baseUrl}/recommendations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: options.signal,
    });
  } catch (error) {
    if ((error as Error)?.name === 'AbortError') throw error;
    return { kind: 'error', message: `Could not reach the ParkSmart backend at ${baseUrl}. Check that it is running and allows requests from this site (CORS).` };
  }

  if (response.status === 404) {
    return { kind: 'error', message: 'The backend has no recommendation service yet (POST /recommendations returned 404).' };
  }
  if (response.status === 422) {
    return { kind: 'error', message: `The backend rejected these trip details: ${await validationDetail(response)}` };
  }
  if (!response.ok) {
    return { kind: 'error', message: `The backend could not compute recommendations (HTTP ${response.status}).` };
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    return { kind: 'error', message: 'The backend sent a response the website could not read.' };
  }
  const parsed = parseResponse(data);
  if (!parsed) {
    return { kind: 'error', message: 'The backend response did not match the agreed format.' };
  }
  return { kind: 'ok', response: parsed, recommendations: toRecommendations(parsed) };
}

/** Checks the response shape; returns null if it is not the agreed contract. */
export function parseResponse(data: unknown): ApiRecommendationResponse | null {
  if (!isObject(data)) return null;
  const { status, is_example, arrival_time, first_choice, backup_choice, explanation, limitations } = data;
  if (typeof status !== 'string' || !STATUSES.has(status)) return null;
  if (typeof is_example !== 'boolean' || typeof arrival_time !== 'string') return null;
  if (typeof explanation !== 'string') return null;
  if (!Array.isArray(limitations) || !limitations.every((note) => typeof note === 'string')) return null;
  if (!isChoiceOrNull(first_choice) || !isChoiceOrNull(backup_choice)) return null;
  if (status === 'ready' && first_choice === null) return null;
  if (status !== 'ready' && (first_choice !== null || backup_choice !== null)) return null;
  return data as unknown as ApiRecommendationResponse;
}

/** Turns API choices into the cards the results list already renders. */
export function toRecommendations(response: ApiRecommendationResponse): ParkingRecommendation[] {
  const choices: [ApiChoice | null, string][] = [
    [response.first_choice, 'First choice'],
    [response.backup_choice, 'Backup'],
  ];
  return choices.flatMap(([choice, badgeLabel], index) =>
    choice
      ? [{
          badgeLabel,
          rank: index + 1,
          lot: lotFor(choice.location),
          score: 0,
          reason: choice.explanation,
          access: { status: 'never' as const },
          estimate: {
            availablePercent:
              choice.estimated_available_fraction === null
                ? null
                : Math.round(choice.estimated_available_fraction * 100),
            walkingMinutes:
              choice.estimated_walking_minutes === null ? null : Math.round(choice.estimated_walking_minutes),
            isExample: response.is_example,
          },
        }]
      : []
  );
}

/**
 * The website's own lot (pin, kind, access note) when the ID matches; otherwise a lot
 * built from the API. Its sample fields are never displayed for API results.
 */
function lotFor(location: ApiLocation): ParkingLot {
  const known = ALL_PARKING.find((lot) => lot.locationId === location.location_id);
  if (known) return { ...known, name: location.name };
  return {
    locationId: location.location_id,
    name: location.name,
    latitude: location.coordinates?.latitude ?? Number.NaN,
    longitude: location.coordinates?.longitude ?? Number.NaN,
    estimatedAvailabilityPercent: 0,
    walkingMinutes: 0,
    spaceCategories: [],
    kind: 'lot',
  };
}

async function validationDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = isObject(body) ? body.detail : undefined;
    if (Array.isArray(detail) && detail.length > 0 && isObject(detail[0]) && typeof detail[0].msg === 'string') {
      return detail[0].msg;
    }
    if (typeof detail === 'string') return detail;
  } catch {
    // Fall through to the generic message.
  }
  return 'check the destination, arrival time and permit.';
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNullableNumber(value: unknown, min: number, max: number): boolean {
  return value === null || (typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max);
}

function isChoiceOrNull(value: unknown): boolean {
  if (value === null) return true;
  if (!isObject(value) || !isObject(value.location)) return false;
  const { location } = value;
  if (typeof location.location_id !== 'string' || typeof location.name !== 'string') return false;
  if (location.coordinates !== null && !isObject(location.coordinates)) return false;
  return (
    isNullableNumber(value.estimated_available_fraction, 0, 1) &&
    isNullableNumber(value.estimated_walking_minutes, 0, Number.POSITIVE_INFINITY) &&
    typeof value.explanation === 'string'
  );
}
