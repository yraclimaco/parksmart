import { describe, expect, it } from 'vitest';
import { DEMO_CLASSES } from './ClassPlanDemo.tsx';
import { matchBuilding } from '../utils/scheduleTrips.ts';

describe('landing class demo', () => {
  it('shows the building the real room-code matcher finds for each room', () => {
    for (const c of DEMO_CLASSES) {
      expect(matchBuilding(c.room)?.name).toBe(c.building);
    }
  });
});
