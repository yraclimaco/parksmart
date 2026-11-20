/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * The last few places a person searched, saved in this browser only (localStorage), so a
 * repeat trip is one tap. Only campus buildings are kept; dropped pins are one-off spots.
 */
const STORAGE_KEY = 'parksmart.recent-destinations.v1';
export const MAX_RECENT_DESTINATIONS = 3;

/** Minimal slice of the Storage API, so tests can pass a fake. */
type KeyValueStore = Pick<Storage, 'getItem' | 'setItem'>;

function defaultStore(): KeyValueStore | null {
  try {
    return window.localStorage;
  } catch {
    return null; // private mode, disabled storage, or no window (tests)
  }
}

/** Recent destination ids, newest first; empty if none or unreadable. */
export function loadRecentDestinations(store: KeyValueStore | null = defaultStore()): string[] {
  try {
    const raw = store?.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((id): id is string => typeof id === 'string').slice(0, MAX_RECENT_DESTINATIONS)
      : [];
  } catch {
    return [];
  }
}

/** Puts the id first (moving it up if it was already there). Returns the new list (also saved). */
export function recordRecentDestination(id: string, store: KeyValueStore | null = defaultStore()): string[] {
  const next = [id, ...loadRecentDestinations(store).filter((existing) => existing !== id)].slice(
    0,
    MAX_RECENT_DESTINATIONS
  );
  try {
    store?.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Storage full or blocked: the list just is not remembered next visit
  }
  return next;
}
