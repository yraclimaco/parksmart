/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { DEFAULT_PRIORITY } from '../constants.ts';
import type { ParkingPlannerRequest } from '../types.ts';
import { getArrivalError } from './arrival.ts';
import { campusNow } from './campusClock.ts';
import { DEFAULT_PREFERENCES } from './savedPreferences.ts';

/** "2026-11-19" in local time. */
export function formatLocalDate(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

/** "23:09" in local time (24-hour, the format the planner stores). */
export function formatLocalTime(date: Date): string {
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

/**
 * A fresh planner: no destination, arrival right now, the default permit, balanced with the
 * default walking limit. This is both the first-visit state and what Clear all returns to.
 */
export function blankRequest(now: Date = campusNow()): ParkingPlannerRequest {
  return {
    destinationId: '',
    arrivalDate: formatLocalDate(now),
    arrivalTime: formatLocalTime(now),
    ...DEFAULT_PREFERENCES,
    priority: DEFAULT_PRIORITY,
    maxWalkMinutes: null,
  };
}

/** Same destination, date, time, permit, priority and walking limit. */
export function sameRequest(a: ParkingPlannerRequest, b: ParkingPlannerRequest): boolean {
  return (
    a.destinationId === b.destinationId &&
    a.arrivalDate === b.arrivalDate &&
    a.arrivalTime === b.arrivalTime &&
    a.permitType === b.permitType &&
    (a.priority ?? DEFAULT_PRIORITY) === (b.priority ?? DEFAULT_PRIORITY) &&
    (a.maxWalkMinutes ?? null) === (b.maxWalkMinutes ?? null)
  );
}

/** Results go stale when any trip detail changes after the search that produced them. */
export function isResultStale(searched: ParkingPlannerRequest | null, current: ParkingPlannerRequest): boolean {
  return searched !== null && !sameRequest(searched, current);
}

/**
 * Whether the results should refresh on their own: a search has been made, the trip changed, the
 * destination is the one that was searched (a new destination searches at once instead) and the
 * arrival is valid. A failed search leaves the old request in place, but nothing in the inputs
 * changes afterwards, so this never turns into a retry loop.
 */
export function shouldAutoRefresh(
  searched: ParkingPlannerRequest | null,
  current: ParkingPlannerRequest,
  arrivalError: string | null
): boolean {
  return (
    searched !== null &&
    searched.destinationId === current.destinationId &&
    !sameRequest(searched, current) &&
    arrivalError === null
  );
}

/**
 * True when a search for these inputs is already on its way, so sending it again would only
 * double the requests (a quick second tap, or an auto-refresh landing on a running search).
 */
export function isDuplicateSearch(inFlight: ParkingPlannerRequest | null, next: ParkingPlannerRequest): boolean {
  return inFlight !== null && sameRequest(inFlight, next);
}

/**
 * The form changes for planning a class. A class whose building is not known sets the time but
 * clears the destination: the old building must never be searched for a different class.
 */
export function classTripChanges(trip: {
  destinationId?: string;
  arrivalDate: string;
  arrivalTime: string;
}): Pick<ParkingPlannerRequest, 'destinationId' | 'arrivalDate' | 'arrivalTime'> {
  return {
    destinationId: trip.destinationId ?? '',
    arrivalDate: trip.arrivalDate,
    arrivalTime: trip.arrivalTime,
  };
}

/**
 * What tapping a class does. A class with a known building searches for it. A class with no known
 * building only sets the time, and empties the old destination and results: nothing may search
 * (or auto-refresh) the previous building for a different class.
 */
export function planClassTrip(trip: { destinationId?: string; arrivalDate: string; arrivalTime: string }): {
  changes: ReturnType<typeof classTripChanges>;
  search: boolean;
  clearResults: boolean;
} {
  const changes = classTripChanges(trip);
  const known = changes.destinationId !== '';
  return { changes, search: known, clearResults: !known };
}

/**
 * An earlier search to run again from "Recent". If its arrival has passed (it defaults to "now", so
 * after a few minutes it has), the trip is moved to now instead of refusing to search.
 */
export function restoreRequest(request: ParkingPlannerRequest, now: Date = campusNow()): ParkingPlannerRequest {
  if (getArrivalError(request, now) === null) return request;
  return { ...request, arrivalDate: formatLocalDate(now), arrivalTime: formatLocalTime(now) };
}
