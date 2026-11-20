/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { PERMIT_OPTIONS } from '../constants.ts';
import type { PermitType } from '../types.ts';

/**
 * The one setting a returning user should not have to enter again: their permit. Saved in
 * this browser only (localStorage). Destination, date and time are per trip and never saved.
 *
 * Priority and walking limit used to be saved here too. They are no longer user controls
 * (every search is balanced with the default limit), and a saved short walking limit left
 * searches with no results, so the old key is ignored and removed.
 */
export interface SavedPreferences {
  permitType: PermitType;
}

/** What a first-time visitor sees; also what "Reset" returns to. */
export const DEFAULT_PREFERENCES: SavedPreferences = { permitType: 'S' };

const STORAGE_KEY = 'parksmart.preferences.v2';
/** Earlier format that also held priority and walking limit; never read, removed on load. */
const LEGACY_STORAGE_KEY = 'parksmart.preferences.v1';

/** Minimal slice of the Storage API, so tests can pass a fake. */
type KeyValueStore = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

function defaultStore(): KeyValueStore | null {
  try {
    return window.localStorage;
  } catch {
    return null; // private mode, disabled storage, or no window (tests)
  }
}

/** The saved permit, or null if none is saved or it is not a permit we know. */
export function loadPreferences(store: KeyValueStore | null = defaultStore()): SavedPreferences | null {
  try {
    store?.removeItem(LEGACY_STORAGE_KEY);
  } catch {
    // Nothing to clean up if storage is blocked
  }
  try {
    const raw = store?.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null) return null;
    const permit = PERMIT_OPTIONS.find((p) => p.type === (parsed as Record<string, unknown>).permitType)?.type;
    return permit ? { permitType: permit } : null;
  } catch {
    return null;
  }
}

/** Remembers the permit; a full or blocked store only means it is not restored next visit. */
export function savePreferences(prefs: SavedPreferences, store: KeyValueStore | null = defaultStore()): void {
  try {
    store?.setItem(STORAGE_KEY, JSON.stringify({ permitType: prefs.permitType }));
  } catch {
    // Storage full or blocked: this visit still works
  }
}

/** Forgets the saved permit so the next visit starts from the default. */
export function clearPreferences(store: KeyValueStore | null = defaultStore()): void {
  try {
    store?.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to do if storage is blocked
  }
}

/** True when the permit differs from what a first-time visitor sees. */
export function isCustomized(prefs: SavedPreferences): boolean {
  return prefs.permitType !== DEFAULT_PREFERENCES.permitType;
}
