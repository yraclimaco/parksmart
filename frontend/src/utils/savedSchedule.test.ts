import { describe, expect, it } from 'vitest';
import type { ScheduleEvent } from './icsSchedule.ts';
import { clearSchedule, loadSchedule, saveSchedule } from './savedSchedule.ts';

function fakeStore(initial?: string) {
  let value = initial ?? null;
  return {
    getItem: () => value,
    setItem: (_key: string, next: string) => {
      value = next;
    },
    removeItem: () => {
      value = null;
    },
  };
}

const EVENT: ScheduleEvent = {
  id: 'cse100',
  title: 'CSE 100',
  location: 'CENTR 115',
  date: '2026-11-16',
  startMinutes: 570,
  durationMinutes: 70,
  rule: { interval: 1, byDay: [1, 3, 5], untilTotal: null, count: null },
  exdates: ['2026-11-25'],
};

describe('saved schedule: zones', () => {
  it('keeps the zone of a repeating class, so it stays right across daylight saving after a reload', () => {
    const utc: ScheduleEvent = { ...EVENT, source: { zone: 'UTC', date: '2026-09-28', minutes: 960 } };
    const store = fakeStore();
    saveSchedule([utc], store);
    expect(loadSchedule(store)[0].source).toEqual({ zone: 'UTC', date: '2026-09-28', minutes: 960 });
  });

  it('ignores a malformed zone instead of dropping the class', () => {
    const bad = { ...EVENT, source: { zone: 5, date: 'x' } };
    const loaded = loadSchedule(fakeStore(JSON.stringify([bad])));
    expect(loaded).toHaveLength(1);
    expect(loaded[0].source).toBeUndefined();
  });
});

describe('saved schedule', () => {
  it('starts empty and ignores unreadable data', () => {
    expect(loadSchedule(fakeStore())).toEqual([]);
    expect(loadSchedule(fakeStore('nope'))).toEqual([]);
    expect(loadSchedule(fakeStore('{"a":1}'))).toEqual([]);
    expect(loadSchedule(null)).toEqual([]);
  });

  it('remembers a schedule, including how it repeats', () => {
    const store = fakeStore();
    expect(saveSchedule([EVENT, { ...EVENT, id: 'single', rule: null, exdates: [] }], store)).toBe(true);
    const loaded = loadSchedule(store);
    expect(loaded).toHaveLength(2);
    expect(loaded[0]).toEqual(EVENT);
    expect(loaded[1].rule).toBeNull();
  });

  it('drops events with the wrong shape and keeps the good ones', () => {
    const store = fakeStore(JSON.stringify([EVENT, { id: 'bad' }, { ...EVENT, date: 'tomorrow' }, null, 7]));
    expect(loadSchedule(store)).toEqual([EVENT]);
  });

  it('forgets the schedule when cleared', () => {
    const store = fakeStore();
    saveSchedule([EVENT], store);
    clearSchedule(store);
    expect(loadSchedule(store)).toEqual([]);
  });

  it('keeps working, and says so, when storage throws', () => {
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
    expect(loadSchedule(broken)).toEqual([]);
    expect(saveSchedule([EVENT], broken)).toBe(false);
    expect(() => clearSchedule(broken)).not.toThrow();
  });
});
