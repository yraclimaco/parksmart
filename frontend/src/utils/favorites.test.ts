import { describe, expect, it } from 'vitest';
import { loadFavorites, toggleFavorite } from './favorites.ts';

function fakeStore(initial?: string) {
  let value = initial ?? null;
  return {
    getItem: () => value,
    setItem: (_key: string, next: string) => {
      value = next;
    },
  };
}

describe('favorites', () => {
  it('starts empty and ignores malformed data', () => {
    expect(loadFavorites(fakeStore())).toEqual([]);
    expect(loadFavorites(fakeStore('not json'))).toEqual([]);
    expect(loadFavorites(fakeStore('{"a":1}'))).toEqual([]);
  });
  it('adds then removes an id, and remembers it', () => {
    const store = fakeStore();
    expect(toggleFavorite('geisel-library', store)).toEqual(['geisel-library']);
    expect(loadFavorites(store)).toEqual(['geisel-library']);
    expect(toggleFavorite('geisel-library', store)).toEqual([]);
  });
  it('works without storage', () => {
    expect(toggleFavorite('x', null)).toEqual(['x']);
  });
});
