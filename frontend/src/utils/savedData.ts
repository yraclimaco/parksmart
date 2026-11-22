/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { clearFavorites } from './favorites.ts';
import { clearRecentDestinations } from './recentDestinations.ts';
import { clearPreferences } from './savedPreferences.ts';
import { clearSchedule } from './savedSchedule.ts';

type SavedDataStore = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

/**
 * Everything the planner keeps on this device for the person: the imported class schedule, starred
 * places, recent places and the saved permit. What "Clear all" forgets.
 */
export function clearAllSavedData(store: SavedDataStore | null = defaultStore()): void {
  clearSchedule(store);
  clearFavorites(store);
  clearRecentDestinations(store);
  clearPreferences(store);
}

function defaultStore(): SavedDataStore | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}
