/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { PermitType } from '../types.ts';

/**
 * "Your usual": the last trip someone searched, saved in this browser only
 * (localStorage). No account, no server; clearing site data removes it, and the
 * app offers "Forget my usual".
 */
export interface UsualTrip {
  destinationId: string;
  permitType: PermitType;
  /** Time of day they usually arrive, "HH:MM". */
  arrivalTime: string;
}

// v2: v1 could hold the old Geisel Library default from before destinations were required
const STORAGE_KEY = 'parksmart.usualTrip.v2';
const PERMITS: readonly PermitType[] = ['A', 'B', 'S', 'SR', 'D', 'V'];

/** Minimal slice of the Storage API, so tests can pass a fake. */
type KeyValueStore = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

function defaultStore(): KeyValueStore | null {
  try {
    return window.localStorage;
  } catch {
    return null; // private mode, disabled storage, or no window (tests)
  }
}

/** Reads the saved trip, or null if none / unreadable / malformed. */
export function loadUsualTrip(store: KeyValueStore | null = defaultStore()): UsualTrip | null {
  try {
    const raw = store?.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<UsualTrip>;
    const valid =
      typeof parsed.destinationId === 'string' &&
      typeof parsed.arrivalTime === 'string' &&
      /^\d{2}:\d{2}$/.test(parsed.arrivalTime) &&
      PERMITS.includes(parsed.permitType as PermitType);
    return valid ? (parsed as UsualTrip) : null;
  } catch {
    return null;
  }
}

export function saveUsualTrip(trip: UsualTrip, store: KeyValueStore | null = defaultStore()): void {
  try {
    store?.setItem(STORAGE_KEY, JSON.stringify(trip));
  } catch {
    // Storage full or blocked: the app works the same, just without remembering
  }
}

export function forgetUsualTrip(store: KeyValueStore | null = defaultStore()): void {
  try {
    store?.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to do
  }
}

/** Grace period: a usual time up to this many minutes ago still counts as "today". */
const USUAL_GRACE_MINUTES = 15;

/**
 * The next date the usual trip happens: today if its time is still ahead
 * (within a short grace), otherwise tomorrow. Returns "YYYY-MM-DD".
 */
export function nextUsualDate(arrivalTime: string, now: Date = new Date()): string {
  const [h, m] = arrivalTime.split(':').map(Number);
  const candidate = new Date(now);
  candidate.setHours(h, m, 0, 0);
  if (candidate.getTime() < now.getTime() - USUAL_GRACE_MINUTES * 60_000) {
    candidate.setDate(candidate.getDate() + 1);
  }
  const y = candidate.getFullYear();
  const mo = String(candidate.getMonth() + 1).padStart(2, '0');
  const d = String(candidate.getDate()).padStart(2, '0');
  return `${y}-${mo}-${d}`;
}
