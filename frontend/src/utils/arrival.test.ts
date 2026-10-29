import { describe, expect, it } from 'vitest';
import { getArrivalError, maxArrivalDate } from './arrival.ts';

const now = new Date('2026-10-21T14:00:00');

describe('getArrivalError', () => {
  it('flags a missing date or time', () => {
    expect(getArrivalError({ arrivalDate: '', arrivalTime: '14:00' }, now)).toMatch(/date/);
    expect(getArrivalError({ arrivalDate: '2026-10-21', arrivalTime: '' }, now)).toMatch(/time/);
  });
  it('flags a past date', () => {
    expect(getArrivalError({ arrivalDate: '2026-10-20', arrivalTime: '14:00' }, now)).toMatch(/passed/);
  });
  it('allows a few minutes of slack and any future time', () => {
    expect(getArrivalError({ arrivalDate: '2026-10-21', arrivalTime: '13:50' }, now)).toBeNull();
    expect(getArrivalError({ arrivalDate: '2026-10-22', arrivalTime: '09:00' }, now)).toBeNull();
  });
});

describe('getArrivalError, far future', () => {
  it('rejects dates more than a year ahead', () => {
    expect(getArrivalError({ arrivalDate: '2099-01-01', arrivalTime: '09:00' }, now)).toMatch(/next year/);
  });
  it('maxArrivalDate is one year after today', () => {
    expect(maxArrivalDate(now)).toBe('2027-10-21');
  });
});
