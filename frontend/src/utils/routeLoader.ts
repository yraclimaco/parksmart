/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { fetchRoute, type ApiRoute, type RouteOutcome, type RouteTrip } from '../api/routes.ts';
import { tripKey, type PlannedLeg } from './routePlan.ts';

/** What one driving or walking row shows. */
export type LegState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ok'; route: ApiRoute }
  /** Not requested: missing start, destination or lot pin. */
  | { status: 'skipped'; message: string }
  /** Routing is turned off on the backend. */
  | { status: 'unavailable'; message: string }
  | { status: 'error'; message: string };

/** After the backend says routing is off, how long before the page asks it again. */
export const ROUTES_UNAVAILABLE_MEMORY_MS = 10 * 60 * 1000;

let unavailableSince: number | null = null;

/** True while the backend's "routing is off" answer is still remembered. */
export function routesKnownUnavailable(now: number = Date.now()): boolean {
  if (unavailableSince === null) return false;
  if (now - unavailableSince >= ROUTES_UNAVAILABLE_MEMORY_MS) {
    unavailableSince = null;
    return false;
  }
  return true;
}

/** Remembers that routing is off, so later searches don't ask again for a while. */
export function rememberRoutesUnavailable(now: number = Date.now()): void {
  unavailableSince = now;
}

/** Forgets what was learned about routing (tests, and a fresh start). */
export function resetRouteMemory(): void {
  unavailableSince = null;
  routeCache.clear();
}

/**
 * Successful routes for this visit, so switching between first choice and backup
 * (or re-running the same search) never asks the backend twice for the same trip.
 */
const routeCache = new Map<string, ApiRoute>();

const ROUTING_OFF_MESSAGE = 'Directions are not set up on this server yet.';

/** The row's starting state for a planned leg, with no request made yet. */
export function initialLegState(leg: PlannedLeg): LegState {
  if (!('trip' in leg)) return { status: 'skipped', message: leg.skipped };
  const cached = routeCache.get(tripKey(leg.trip));
  if (cached) return { status: 'ok', route: cached };
  // Known to be off: show that at once instead of a spinner for a request that is never sent
  if (routesKnownUnavailable()) return { status: 'unavailable', message: ROUTING_OFF_MESSAGE };
  return { status: 'loading' };
}

/** Whether this leg needs a request: it has a trip, no saved route, and routing is not known to be off. */
export function needsRequest(leg: PlannedLeg): leg is Extract<PlannedLeg, { trip: RouteTrip }> {
  return 'trip' in leg && !routeCache.has(tripKey(leg.trip)) && !routesKnownUnavailable();
}

/**
 * Asks the backend for one leg and turns the answer into what the row shows. A saved route is
 * kept, and a "routing is off" answer is remembered so the next searches skip `/routes` entirely.
 */
export async function loadLeg(
  trip: RouteTrip,
  options: { signal?: AbortSignal; fetchImpl?: typeof fetch } = {}
): Promise<LegState> {
  const outcome: RouteOutcome = await fetchRoute(trip, options);
  if (outcome.kind === 'ok') {
    routeCache.set(tripKey(trip), outcome.route);
    return { status: 'ok', route: outcome.route };
  }
  if (outcome.kind === 'unavailable') rememberRoutesUnavailable();
  return { status: outcome.kind, message: outcome.message };
}
