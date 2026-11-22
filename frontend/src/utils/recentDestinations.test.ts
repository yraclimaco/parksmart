import { describe, expect, it } from 'vitest';
import { MAX_RECENT_DESTINATIONS, loadRecentDestinations, recordRecentDestination } from './recentDestinations.ts';

function fakeStore(initial?: string) {
  let value = initial ?? null;
  return {
    getItem: () => value,
    setItem: (_key: string, next: string) => {
      value = next;
    },
  };
}

describe('recent destinations', () => {
  it('starts empty and ignores malformed data', () => {
    expect(loadRecentDestinations(fakeStore())).toEqual([]);
    expect(loadRecentDestinations(fakeStore('nope'))).toEqual([]);
    expect(loadRecentDestinations(fakeStore('{"a":1}'))).toEqual([]);
    expect(loadRecentDestinations(null)).toEqual([]);
  });

  it('keeps the newest first and moves a repeat to the top without duplicating it', () => {
    const store = fakeStore();
    recordRecentDestination('geisel', store);
    recordRecentDestination('price-center', store);
    recordRecentDestination('geisel', store);
    expect(loadRecentDestinations(store)).toEqual(['geisel', 'price-center']);
  });

  it('keeps only the most recent few', () => {
    const store = fakeStore();
    ['a', 'b', 'c', 'd', 'e'].forEach((id) => recordRecentDestination(id, store));
    const recent = loadRecentDestinations(store);
    expect(recent).toHaveLength(MAX_RECENT_DESTINATIONS);
    expect(recent[0]).toBe('e');
  });

  it('keeps working when storage throws', () => {
    const broken = {
      getItem: () => {
        throw new Error('blocked');
      },
      setItem: () => {
        throw new Error('blocked');
      },
    };
    expect(loadRecentDestinations(broken)).toEqual([]);
    expect(recordRecentDestination('geisel', broken)).toEqual(['geisel']);
  });
});
