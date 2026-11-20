import { describe, expect, it } from 'vitest';
import {
  DEFAULT_PREFERENCES,
  clearPreferences,
  isCustomized,
  loadPreferences,
  savePreferences,
} from './savedPreferences.ts';

function fakeStore(initial: Record<string, string> = {}) {
  const data = { ...initial };
  return {
    data,
    getItem: (key: string) => data[key] ?? null,
    setItem: (key: string, next: string) => {
      data[key] = next;
    },
    removeItem: (key: string) => {
      delete data[key];
    },
  };
}

describe('saved preferences', () => {
  it('returns null when nothing is saved or the data is unreadable', () => {
    expect(loadPreferences(fakeStore())).toBeNull();
    expect(loadPreferences(fakeStore({ 'parksmart.preferences.v2': 'not json' }))).toBeNull();
    expect(loadPreferences(fakeStore({ 'parksmart.preferences.v2': '[1,2]' }))).toBeNull();
    expect(loadPreferences(null)).toBeNull();
  });

  it('remembers the permit', () => {
    const store = fakeStore();
    savePreferences({ permitType: 'B' }, store);
    expect(loadPreferences(store)).toEqual({ permitType: 'B' });
  });

  it('ignores a permit it does not know', () => {
    const store = fakeStore({ 'parksmart.preferences.v2': JSON.stringify({ permitType: 'ZZ' }) });
    expect(loadPreferences(store)).toBeNull();
  });

  it('never reads or keeps an old saved walking limit or priority', () => {
    const store = fakeStore({
      'parksmart.preferences.v1': JSON.stringify({ permitType: 'B', priority: 'shorter_walk', maxWalkMinutes: 5 }),
    });
    expect(loadPreferences(store)).toBeNull();
    expect(store.data['parksmart.preferences.v1']).toBeUndefined();
  });

  it('stores only the permit', () => {
    const store = fakeStore();
    savePreferences({ permitType: 'D' }, store);
    expect(JSON.parse(store.data['parksmart.preferences.v2'])).toEqual({ permitType: 'D' });
  });

  it('forgets the saved permit when cleared', () => {
    const store = fakeStore();
    savePreferences({ permitType: 'D' }, store);
    clearPreferences(store);
    expect(loadPreferences(store)).toBeNull();
  });

  it('keeps working when storage throws', () => {
    const broken = {
      getItem: () => {
        throw new Error('blocked');
      },
      setItem: () => {
        throw new Error('blocked');
      },
      removeItem: () => {
        throw new Error('blocked');
      },
    };
    expect(loadPreferences(broken)).toBeNull();
    expect(() => savePreferences(DEFAULT_PREFERENCES, broken)).not.toThrow();
    expect(() => clearPreferences(broken)).not.toThrow();
  });

  it('tells the default permit from a customized one', () => {
    expect(isCustomized(DEFAULT_PREFERENCES)).toBe(false);
    expect(isCustomized({ permitType: 'B' })).toBe(true);
  });
});
