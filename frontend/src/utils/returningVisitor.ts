/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Whether this browser has opened the planner before. Returning visitors skip the intro and
 * landing page and open straight to the planner (the Home button still goes back).
 * Adding `?home` to the address always shows the landing page, for demos.
 */
const STORAGE_KEY = 'parksmart.visited.v1';

/** Minimal slice of the Storage API, so tests can pass a fake. */
type KeyValueStore = Pick<Storage, 'getItem' | 'setItem'>;

function defaultStore(): KeyValueStore | null {
  try {
    return window.localStorage;
  } catch {
    return null; // private mode, disabled storage, or no window (tests)
  }
}

/** True if the planner was opened here before and the address does not ask for the landing page. */
export function shouldOpenPlannerDirectly(
  search: string = typeof window === 'undefined' ? '' : window.location.search,
  store: KeyValueStore | null = defaultStore()
): boolean {
  if (new URLSearchParams(search).has('home')) return false;
  try {
    return store?.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

/** Remembers that the planner was opened. */
export function markPlannerVisited(store: KeyValueStore | null = defaultStore()): void {
  try {
    store?.setItem(STORAGE_KEY, '1');
  } catch {
    // Blocked storage just means the intro shows again next visit
  }
}
