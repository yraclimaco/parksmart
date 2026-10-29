/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Starred destinations, saved in this browser only (localStorage), like "your usual".
 * Only campus buildings can be starred; dropped pins are one-off spots.
 */
const STORAGE_KEY = 'parksmart.favorites.v1';
const MAX_FAVORITES = 20;

/** Minimal slice of the Storage API, so tests can pass a fake. */
type KeyValueStore = Pick<Storage, 'getItem' | 'setItem'>;

function defaultStore(): KeyValueStore | null {
  try {
    return window.localStorage;
  } catch {
    return null; // private mode, disabled storage, or no window (tests)
  }
}

/** Saved destination ids, oldest first; empty if none or unreadable. */
export function loadFavorites(store: KeyValueStore | null = defaultStore()): string[] {
  try {
    const raw = store?.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === 'string') : [];
  } catch {
    return [];
  }
}

/** Adds the id if missing, removes it if present. Returns the new list (also saved). */
export function toggleFavorite(id: string, store: KeyValueStore | null = defaultStore()): string[] {
  const current = loadFavorites(store);
  const next = current.includes(id)
    ? current.filter((existing) => existing !== id)
    : [...current, id].slice(-MAX_FAVORITES);
  try {
    store?.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Storage full or blocked: the star still works this visit, it just is not remembered
  }
  return next;
}
