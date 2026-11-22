import { describe, expect, it } from 'vitest';
import type { ParkingPlannerRequest } from '../types.ts';
import {
  blankRequest,
  classTripChanges,
  formatLocalDate,
  formatLocalTime,
  isDuplicateSearch,
  isResultStale,
  sameRequest,
  shouldAutoRefresh,
} from './plannerState.ts';

const base: ParkingPlannerRequest = {
  destinationId: 'geisel-library',
  arrivalDate: '2026-11-20',
  arrivalTime: '09:00',
  permitType: 'S',
};

describe('blankRequest (first visit and Clear all)', () => {
  const now = new Date(2026, 10, 19, 23, 9);

  it('has no destination, arrives now, and uses the default permit and mix', () => {
    expect(blankRequest(now)).toEqual({
      destinationId: '',
      arrivalDate: '2026-11-19',
      arrivalTime: '23:09',
      permitType: 'S',
      priority: 'balanced',
      maxWalkMinutes: null,
    });
  });

  it('formats single-digit months, days, hours and minutes with a leading zero', () => {
    const early = new Date(2027, 0, 5, 7, 4);
    expect(formatLocalDate(early)).toBe('2027-01-05');
    expect(formatLocalTime(early)).toBe('07:04');
  });
});

describe('sameRequest and isResultStale', () => {
  it('treats a missing priority and walk limit as the defaults', () => {
    expect(sameRequest(base, { ...base, priority: 'balanced', maxWalkMinutes: null })).toBe(true);
  });

  it('is not stale before any search, or when nothing changed', () => {
    expect(isResultStale(null, base)).toBe(false);
    expect(isResultStale(base, { ...base })).toBe(false);
  });

  it('is stale when destination, date, time, permit, priority or walk limit changes', () => {
    expect(isResultStale(base, { ...base, destinationId: 'price-center-west' })).toBe(true);
    expect(isResultStale(base, { ...base, arrivalDate: '2026-11-21' })).toBe(true);
    expect(isResultStale(base, { ...base, arrivalTime: '09:30' })).toBe(true);
    expect(isResultStale(base, { ...base, permitType: 'B' })).toBe(true);
    expect(isResultStale(base, { ...base, priority: 'shorter_walk' })).toBe(true);
    expect(isResultStale(base, { ...base, maxWalkMinutes: 10 })).toBe(true);
  });
});

describe('shouldAutoRefresh', () => {
  it('refreshes after the permit or time changes for the same destination', () => {
    expect(shouldAutoRefresh(base, { ...base, permitType: 'B' }, null)).toBe(true);
    expect(shouldAutoRefresh(base, { ...base, arrivalTime: '10:00' }, null)).toBe(true);
  });

  it('does nothing before the first search or when nothing changed', () => {
    expect(shouldAutoRefresh(null, base, null)).toBe(false);
    expect(shouldAutoRefresh(base, { ...base }, null)).toBe(false);
  });

  it('leaves a new destination to the immediate search, so there is never a second request', () => {
    expect(shouldAutoRefresh(base, { ...base, destinationId: 'price-center-west' }, null)).toBe(false);
    expect(shouldAutoRefresh(base, { ...base, destinationId: 'price-center-west', permitType: 'B' }, null)).toBe(false);
  });

  it('waits while the arrival time is invalid', () => {
    expect(shouldAutoRefresh(base, { ...base, arrivalTime: '' }, 'Pick an arrival time.')).toBe(false);
  });

  it('does not fire again for the same inputs after a search finished', () => {
    const changed = { ...base, permitType: 'B' as const };
    expect(shouldAutoRefresh(changed, changed, null)).toBe(false); // the finished search became "searched"
  });
});

describe('isDuplicateSearch (no identical search while one is running)', () => {
  it('is false when nothing is running', () => {
    expect(isDuplicateSearch(null, base)).toBe(false);
  });

  it('is true for the same trip, so a second tap or an auto-refresh is not sent again', () => {
    expect(isDuplicateSearch(base, { ...base })).toBe(true);
  });

  it('is false when anything about the trip differs, so a newer search still replaces the old one', () => {
    expect(isDuplicateSearch(base, { ...base, arrivalTime: '09:05' })).toBe(false);
    expect(isDuplicateSearch(base, { ...base, permitType: 'B' })).toBe(false);
    expect(isDuplicateSearch(base, { ...base, destinationId: 'price-center-west' })).toBe(false);
  });
});

describe('classTripChanges (planning a class)', () => {
  const when = { arrivalDate: '2026-11-23', arrivalTime: '08:40' };

  it('sets the building and time for a class whose building is known', () => {
    expect(classTripChanges({ destinationId: 'center-hall', ...when })).toEqual({ destinationId: 'center-hall', ...when });
  });

  it('clears the destination for a class whose building is not known', () => {
    expect(classTripChanges(when)).toEqual({ destinationId: '', ...when });
    expect(classTripChanges({ destinationId: undefined, ...when }).destinationId).toBe('');
  });

  it('never leaves the previous building to be searched or auto-refreshed for an unmatched class', () => {
    // Searched Geisel, then tapped a class in an unknown room
    const next = { ...base, ...classTripChanges(when) };
    expect(next.destinationId).toBe('');
    expect(shouldAutoRefresh(base, next, null)).toBe(false);
  });
});
