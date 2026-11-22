/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Check, FileText, MousePointerClick, RotateCcw } from 'lucide-react';
import { ARRIVE_BEFORE_CLASS_MINUTES, formatClock } from '../utils/classTime';
import { prefersReducedMotion, useInView } from './LotParts';

/**
 * Example classes for the demo. The classes, times and lots are made up; the 20-minute rule is the
 * real one, and each building is what the planner's real room-code matcher (`matchBuilding`)
 * finds for that room (classPlanDemo.test.ts checks this).
 */
export const DEMO_CLASSES = [
  { code: 'MATH 20C', room: 'WLH 2001', building: 'Warren Lecture Hall', start: 9 * 60, first: 'Lot P503', firstWalk: 5, backup: 'Lot P510', backupWalk: 7 },
  { code: 'CSE 100', room: 'CENTR 115', building: 'Center Hall', start: 11 * 60, first: 'Hopkins Parking Structure', firstWalk: 6, backup: 'Gilman Parking Structure', backupWalk: 8 },
  { code: 'PHYS 2A', room: 'YORK 2722', building: 'York Hall', start: 14 * 60, first: 'Pangea Parking Structure', firstWalk: 5, backup: 'Scholars Parking Structure', backupWalk: 8 },
] as const;

/** The demo's beats: the file arrives, the classes appear with their buildings, then one is tapped. */
type Stage = 'file' | 'list' | 'result';

/** Milliseconds after the demo scrolls into view: classes appear, then the demo taps a class. */
const LIST_AT_MS = 1100;
const AUTO_PICK_AT_MS = 2600;
/** The class the demo taps on its own. */
const AUTO_PICK = 1;

/**
 * Screen 3's picture, in three beats: a schedule file is imported, its classes appear with each
 * room code read as a building, and tapping a class sets the arrival 20 minutes before it and shows
 * a first choice and a backup near that building. It plays once when scrolled into view; any class
 * can be tapped, and Replay plays it again. Example data only.
 */
export const ClassPlanDemo: React.FC = () => {
  const [ref, seen] = useInView<HTMLDivElement>();
  const reduced = React.useMemo(prefersReducedMotion, []);
  const [stage, setStage] = React.useState<Stage>(reduced ? 'result' : 'file');
  const [picked, setPicked] = React.useState<number | null>(reduced ? AUTO_PICK : null);
  const [run, setRun] = React.useState(0);
  const touched = React.useRef(false);
  const timers = React.useRef<number[]>([]);

  const clearTimers = React.useCallback(() => {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
  }, []);
  const later = React.useCallback((fn: () => void, ms: number) => {
    timers.current.push(window.setTimeout(fn, ms));
  }, []);

  const pick = React.useCallback(
    (index: number) => {
      // A tap shows its result at once, with no waiting
      clearTimers();
      setPicked(index);
      setStage('result');
    },
    [clearTimers]
  );

  React.useEffect(() => {
    if (!seen || reduced) return;
    clearTimers();
    setStage('file');
    setPicked(null);
    later(() => setStage('list'), LIST_AT_MS);
    later(() => {
      if (!touched.current) pick(AUTO_PICK);
    }, AUTO_PICK_AT_MS);
    return clearTimers;
  }, [seen, reduced, run, pick, clearTimers, later]);

  const replay = () => {
    touched.current = false;
    setRun((r) => r + 1);
  };

  const chosen = picked === null ? null : DEMO_CLASSES[picked];
  const showList = stage !== 'file';

  return (
    <div className="cp" ref={ref}>
      <div className="cp-card" role="group" aria-label="Example: importing a class schedule and getting parking for a class">
        <p className="cp-head">
          <strong>Your classes</strong>
          {!reduced && (
            <button type="button" className="cp-replay" onClick={replay}>
              <RotateCcw aria-hidden="true" /> Replay
            </button>
          )}
        </p>

        <div className={`cp-file${showList ? ' cp-file--done' : ''}`}>
          <FileText aria-hidden="true" />
          <span>
            <strong>schedule.ics</strong> {showList ? `${DEMO_CLASSES.length} classes found` : 'Reading your classes…'}
          </span>
          {showList && <Check className="cp-file-ok" aria-hidden="true" />}
        </div>

        <ul className={`cp-list${showList ? ' cp-list--in' : ''}`} aria-hidden={!showList}>
          {DEMO_CLASSES.map((c, i) => (
            <li key={c.code} style={{ '--cp-i': i } as React.CSSProperties}>
              <button
                type="button"
                className={`cp-class${picked === i ? ' cp-class--picked' : ''}`}
                aria-pressed={picked === i}
                tabIndex={showList ? 0 : -1}
                onClick={() => {
                  touched.current = true;
                  pick(i);
                }}
              >
                <span className="cp-time">{formatClock(c.start)}</span>
                <span className="cp-title">
                  <strong>{c.code}</strong>
                  <span>
                    {c.room} <span className="cp-arrow" aria-hidden="true">&rarr;</span>
                    <span className="cp-sr"> is in </span>
                    <span className="cp-building">{c.building}</span>
                  </span>
                </span>
                {picked === i ? (
                  <Check className="cp-icon" aria-hidden="true" />
                ) : (
                  <MousePointerClick className="cp-icon cp-icon--hint" aria-hidden="true" />
                )}
              </button>
            </li>
          ))}
        </ul>

        <div className="cp-out" aria-live="polite">
          {chosen === null || stage === 'file' || stage === 'list' ? (
            <p className="cp-cue">{showList ? 'Tap a class' : ' '}</p>
          ) : (
            <>
              <p className="cp-arrive">
                Arrive <strong>{formatClock(chosen.start - ARRIVE_BEFORE_CLASS_MINUTES)}</strong>, {ARRIVE_BEFORE_CLASS_MINUTES} min before class
              </p>
              <div className="cp-result">
                <p className="cp-first">
                  <span className="cp-tag">First choice</span>
                  <strong>{chosen.first}</strong>
                  <span>
                    {chosen.firstWalk} min walk to {chosen.building}
                  </span>
                </p>
                <p className="cp-backup">
                  <span className="cp-tag cp-tag--quiet">Backup</span>
                  <strong>{chosen.backup}</strong>
                  <span>{chosen.backupWalk} min walk</span>
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
