/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import type { ParkingPlannerRequest } from '../types.ts';
import { isDuplicateSearch } from './plannerState.ts';

/**
 * Remembers the one search that is on its way, so the same search is never sent a second time
 * while it runs (a double tap, or an auto-refresh landing on a running search). A different
 * search is always allowed: it replaces the running one.
 */
export interface SearchGate {
  /** True when this search is already running. */
  isRunning(next: ParkingPlannerRequest): boolean;
  /** A search was sent. */
  begin(request: ParkingPlannerRequest): void;
  /** The running search ended (answer, error, or cancelled). */
  end(): void;
}

export function createSearchGate(): SearchGate {
  let inFlight: ParkingPlannerRequest | null = null;
  return {
    isRunning: (next) => isDuplicateSearch(inFlight, next),
    begin: (request) => {
      inFlight = request;
    },
    end: () => {
      inFlight = null;
    },
  };
}
