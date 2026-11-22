/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useEffect, useState } from 'react';
import { isCompleteAlerts } from '../utils/alertFormat.ts';
import { fetchTripAlerts, type TripAlertsQuery, type TripAlertsResponse } from '../api/tripAlerts.ts';

export type AlertsState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ok'; alerts: TripAlertsResponse }
  | { status: 'unavailable'; message: string }
  | { status: 'error'; message: string };

const IDLE: AlertsState = { status: 'idle' };

/** Alerts for this visit; the backend caches them for minutes, so reuse beats asking again. */
const alertsCache = new Map<string, TripAlertsResponse>();

const keyOf = (query: TripAlertsQuery) =>
  [
    query.arrivalTime,
    query.parkingLocationId,
    query.destination ? `${query.destination.latitude},${query.destination.longitude}` : '-',
  ].join('|');

/**
 * Loads trip alerts for the chosen parking location and arrival. Choosing another lot
 * or arrival cancels the old request. Alerts only ever add information: an error here
 * leaves parking results untouched.
 *
 * @param enabled false keeps everything idle (sample mode has no backend).
 * @param query what to ask for, or null when nothing is chosen.
 */
export function useTripAlerts(enabled: boolean, query: TripAlertsQuery | null, retryToken = 0): AlertsState {
  const [state, setState] = useState<AlertsState>(IDLE);
  const key = query ? keyOf(query) : '';

  useEffect(() => {
    if (!enabled || !query) {
      setState(IDLE);
      return;
    }
    const cached = alertsCache.get(key);
    if (cached) {
      setState({ status: 'ok', alerts: cached });
      return;
    }
    const controller = new AbortController();
    setState({ status: 'loading' });
    fetchTripAlerts(query, { signal: controller.signal })
      .then((outcome) => {
        if (controller.signal.aborted) return;
        if (outcome.kind === 'ok') {
          // Only a full, fresh answer is kept; an incomplete one is asked for again on a recheck
          if (isCompleteAlerts(outcome.alerts)) alertsCache.set(key, outcome.alerts);
          setState({ status: 'ok', alerts: outcome.alerts });
        } else {
          setState({ status: outcome.kind, message: outcome.message });
        }
      })
      .catch(() => {
        // Cancelled by a newer choice; that choice owns the state.
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` covers the query
  }, [enabled, key, retryToken]);

  return state;
}
