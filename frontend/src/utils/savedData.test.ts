import { describe, expect, it } from 'vitest';
import { toggleFavorite, loadFavorites } from './favorites.ts';
import { loadRecentDestinations, recordRecentDestination } from './recentDestinations.ts';
import { clearAllSavedData } from './savedData.ts';
import { loadPreferences, savePreferences } from './savedPreferences.ts';
import { loadSchedule, saveSchedule } from './savedSchedule.ts';

/** A small in-memory localStorage. */
function memoryStore() {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
}

describe('clearAllSavedData (what Clear all forgets)', () => {
  it('forgets the imported classes, starred places, recent places and the saved permit', () => {
    const store = memoryStore();
    saveSchedule(
      [{ id: 'a', title: 'CSE 100', location: 'CENTR 115', date: '2026-11-23', startMinutes: 600, durationMinutes: 60, rule: null, exdates: [] }],
      store
    );
    toggleFavorite('geisel-library', store);
    recordRecentDestination('york-hall', store);
    savePreferences({ permitType: 'B' }, store);
    expect(loadSchedule(store)).toHaveLength(1);
    expect(loadFavorites(store)).toEqual(['geisel-library']);

    clearAllSavedData(store);

    expect(loadSchedule(store)).toEqual([]);
    expect(loadFavorites(store)).toEqual([]);
    expect(loadRecentDestinations(store)).toEqual([]);
    expect(loadPreferences(store)).toBeNull();
  });

  it('does nothing without storage (private mode)', () => {
    expect(() => clearAllSavedData(null)).not.toThrow();
  });
});
