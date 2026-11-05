/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useEffect, useState } from 'react';
import { fetchRoute, type ApiRoute, type LatLng, type TravelMode } from '../api/routes.ts';
import { planRoutes, tripKey, type PlannedLeg } from '../utils/routePlan.ts';

export type LegState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ok'; route: ApiRoute }
  /** Not requested: missing start, destination or lot pin. */
  | { status: 'skipped'; message: string }
  /** Routing is turned off on the backend. */
  | { status: 'unavailable'; message: string }
  | { status: 'error'; message: string };

export type RouteLegs = Record<TravelMode, LegState>;

const IDLE: RouteLegs = { driving: { status: 'idle' }, walking: { status: 'idle' } };

/**
 * Successful routes for this visit, so switching between first choice and backup
 * (or re-running the same search) never asks the backend twice for the same trip.
 */
const routeCache = new Map<string, ApiRoute>();

/**
 * Loads driving and walking routes for the chosen parking location. Changing the
 * lot, destination or start cancels requests for the old choice.
 *
 * @param enabled false keeps everything idle (sample mode has no backend).
 * @param lot chosen parking location's map point, or null when nothing is chosen.
 */
export function useRoutes(
  enabled: boolean,
  lot: LatLng | null,
  destination: LatLng | null,
  start: LatLng | null,
  retryToken = 0
): RouteLegs {
  const [legs, setLegs] = useState<RouteLegs>(IDLE);
  // Primitive deps so a new object with the same coordinates does not refetch
  const key = [lot, destination, start].map((p) => (p ? `${p.latitude},${p.longitude}` : '-')).join(';');

  useEffect(() => {
    if (!enabled || !lot) {
      setLegs(IDLE);
      return;
    }
    const plan = planRoutes(lot, destination, start);
    const controller = new AbortController();
    const next: RouteLegs = { driving: initial(plan.driving), walking: initial(plan.walking) };
    setLegs(next);

    for (const leg of [plan.driving, plan.walking]) {
      if (!('trip' in leg) || routeCache.has(tripKey(leg.trip))) continue;
      const cacheKey = tripKey(leg.trip);
      fetchRoute(leg.trip, { signal: controller.signal })
        .then((outcome) => {
          if (controller.signal.aborted) return;
          if (outcome.kind === 'ok') routeCache.set(cacheKey, outcome.route);
          const state: LegState =
            outcome.kind === 'ok'
              ? { status: 'ok', route: outcome.route }
              : { status: outcome.kind, message: outcome.message };
          setLegs((prev) => ({ ...prev, [leg.mode]: state }));
        })
        .catch(() => {
          // Cancelled by a newer choice; that choice owns the state.
        });
    }
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` covers the coordinates
  }, [enabled, key, retryToken]);

  return legs;
}

function initial(leg: PlannedLeg): LegState {
  if (!('trip' in leg)) return { status: 'skipped', message: leg.skipped };
  const cached = routeCache.get(tripKey(leg.trip));
  return cached ? { status: 'ok', route: cached } : { status: 'loading' };
}
