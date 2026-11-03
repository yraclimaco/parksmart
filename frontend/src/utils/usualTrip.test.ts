import { describe, expect, it } from 'vitest';
import { forgetUsualTrip, loadUsualTrip, nextUsualDate, saveUsualTrip } from './usualTrip.ts';

function fakeStore() {
  const data = new Map<string, string>();
  return {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
}

describe('usual trip storage', () => {
  it('saves, loads and forgets a trip', () => {
    const store = fakeStore();
    expect(loadUsualTrip(store)).toBeNull();
    saveUsualTrip({ destinationId: 'geisel-library', permitType: 'S', arrivalTime: '09:40' }, store);
    expect(loadUsualTrip(store)).toEqual({ destinationId: 'geisel-library', permitType: 'S', arrivalTime: '09:40' });
    forgetUsualTrip(store);
    expect(loadUsualTrip(store)).toBeNull();
  });

  it('ignores malformed saved data', () => {
    const store = fakeStore();
    store.setItem('parksmart.usualTrip.v1', '{"destinationId":"x","permitType":"Z","arrivalTime":"9"}');
    expect(loadUsualTrip(store)).toBeNull();
    store.setItem('parksmart.usualTrip.v1', 'not json');
    expect(loadUsualTrip(store)).toBeNull();
  });

  it('works without storage at all', () => {
    expect(loadUsualTrip(null)).toBeNull();
    expect(() => saveUsualTrip({ destinationId: 'x', permitType: 'S', arrivalTime: '09:00' }, null)).not.toThrow();
  });
});

describe('nextUsualDate', () => {
  const evening = new Date(2026, 9, 21, 20, 45); // Wed 8:45 PM
  it('rolls a morning usual to tomorrow in the evening', () => {
    expect(nextUsualDate('09:40', evening)).toBe('2026-10-22');
  });
  it('keeps a later-today usual on today', () => {
    expect(nextUsualDate('21:30', evening)).toBe('2026-10-21');
  });
});
