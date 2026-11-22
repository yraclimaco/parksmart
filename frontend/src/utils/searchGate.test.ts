import { describe, expect, it } from 'vitest';
import type { ParkingPlannerRequest } from '../types.ts';
import { createSearchGate } from './searchGate.ts';

const trip: ParkingPlannerRequest = {
  destinationId: 'geisel-library',
  arrivalDate: '2026-11-23',
  arrivalTime: '09:00',
  permitType: 'S',
};

describe('search gate', () => {
  it('lets the first search through', () => {
    expect(createSearchGate().isRunning(trip)).toBe(false);
  });

  it('blocks the same search while it is running (double tap, auto-refresh)', () => {
    const gate = createSearchGate();
    gate.begin(trip);
    expect(gate.isRunning({ ...trip })).toBe(true);
  });

  it('lets a different search replace the running one', () => {
    const gate = createSearchGate();
    gate.begin(trip);
    expect(gate.isRunning({ ...trip, arrivalTime: '09:05' })).toBe(false);
    gate.begin({ ...trip, arrivalTime: '09:05' });
    expect(gate.isRunning(trip)).toBe(false);
    expect(gate.isRunning({ ...trip, arrivalTime: '09:05' })).toBe(true);
  });

  it('lets the same search go again once it has ended (retry after an error, Clear all)', () => {
    const gate = createSearchGate();
    gate.begin(trip);
    gate.end();
    expect(gate.isRunning(trip)).toBe(false);
  });
});
