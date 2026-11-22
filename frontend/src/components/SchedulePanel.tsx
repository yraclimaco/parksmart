/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useMemo, useRef, useState } from 'react';
import { CalendarDays, MapPin, Upload, X } from 'lucide-react';
import { classesOn, parseIcs, type ClassSession, type ScheduleEvent } from '../utils/icsSchedule.ts';
import { clearSchedule, loadSchedule, saveSchedule } from '../utils/savedSchedule.ts';
import { arrivalForClass, formatClock, matchBuilding } from '../utils/scheduleTrips.ts';

/** Calendar files are small; anything much bigger is not a class schedule. */
const MAX_FILE_BYTES = 2 * 1024 * 1024;

export interface ClassTrip {
  /** Campus building for the class, or undefined when it could not be matched for sure. */
  destinationId?: string;
  arrivalDate: string;
  arrivalTime: string;
}

interface SchedulePanelProps {
  /** The planner's arrival date ("YYYY-MM-DD"); the panel lists that day's classes. */
  date: string;
  /** Fill the trip for a class (and search, when its building is known). */
  onPlanClass: (trip: ClassTrip) => void;
}

/** "Wed, Nov 18" for a "YYYY-MM-DD" date. */
function dayLabel(date: string): string {
  const [y, m, d] = date.split('-').map(Number);
  const day = new Date(y, m - 1, d);
  if (Number.isNaN(day.getTime())) return ''; // the date field was cleared
  return day.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

/**
 * Import a class schedule (.ics) and park for any class in one tap. The file is read in the
 * browser and never uploaded; the classes are remembered on this device so it only has to
 * be imported once. Tapping a class sets the arrival time to just before it starts and,
 * when its building is recognized, searches for parking near it.
 */
export const SchedulePanel: React.FC<SchedulePanelProps> = ({ date, onPlanClass }) => {
  const [events, setEvents] = useState<ScheduleEvent[]>(() => loadSchedule());
  const [message, setMessage] = useState<{ tone: 'ok' | 'problem'; text: string } | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const sessions = useMemo(() => classesOn(events, date), [events, date]);
  const hasSchedule = events.length > 0;

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) {
      setMessage({ tone: 'problem', text: 'That file is too large to be a class schedule.' });
      return;
    }
    try {
      const parsed = parseIcs(await file.text());
      if (parsed.length === 0) {
        setMessage({
          tone: 'problem',
          text: 'No classes found in that file. Export your calendar as .ics and try again.',
        });
        return;
      }
      const stored = saveSchedule(parsed);
      setEvents(parsed);
      setMessage({
        tone: 'ok',
        text: `Imported ${parsed.length} ${parsed.length === 1 ? 'class' : 'classes'}${
          stored ? '. Saved on this device.' : '. Your browser would not save it, so it will be gone next visit.'
        }`,
      });
    } catch {
      setMessage({ tone: 'problem', text: "Couldn't read that file. Export your calendar as .ics and try again." });
    } finally {
      if (inputRef.current) inputRef.current.value = ''; // allow choosing the same file again
    }
  };

  const handleRemove = () => {
    clearSchedule();
    setEvents([]);
    setMessage(null);
  };

  const plan = (session: ClassSession) => {
    const { arrivalDate, arrivalTime } = arrivalForClass(session);
    onPlanClass({ destinationId: matchBuilding(session.location)?.id, arrivalDate, arrivalTime });
  };

  const fileInput = (
    <input
      ref={inputRef}
      type="file"
      accept=".ics,text/calendar"
      className="sr-only"
      aria-label="Choose a class schedule .ics file"
      onChange={(e) => void handleFile(e.target.files?.[0])}
    />
  );

  return (
    <section aria-labelledby="schedule-title" className="rounded-[12px] border border-line bg-white p-3">
      <div className="flex items-center justify-between gap-2">
        <h2 id="schedule-title" className="flex items-center gap-1.5 text-[13px] font-semibold text-ink">
          <CalendarDays className="w-4 h-4 text-navy" aria-hidden="true" />
          {hasSchedule ? `Your classes${dayLabel(date) ? `, ${dayLabel(date)}` : ''}` : 'Class schedule'}
        </h2>
        {hasSchedule && (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="min-h-[44px] sm:min-h-[28px] px-2 text-xs font-semibold text-navy underline underline-offset-2 hover:text-navy-2 rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-sky cursor-pointer"
            >
              Replace
            </button>
            <button
              type="button"
              onClick={handleRemove}
              aria-label="Remove class schedule"
              className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] sm:min-w-[28px] sm:min-h-[28px] rounded-md text-muted hover:text-navy focus:outline-none focus-visible:ring-2 focus-visible:ring-sky cursor-pointer"
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
        )}
      </div>

      {!hasSchedule && (
        <div className="mt-2 space-y-2">
          <p className="text-xs text-muted">
            Import your classes and park for any of them in one tap. The file is read on this device and never uploaded.
          </p>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="w-full inline-flex items-center justify-center gap-1.5 min-h-[44px] sm:min-h-[36px] rounded-lg border border-navy/30 bg-white text-[13px] font-semibold text-navy hover:bg-paper focus:outline-none focus-visible:ring-2 focus-visible:ring-sky cursor-pointer"
          >
            <Upload className="w-4 h-4" aria-hidden="true" /> Import schedule (.ics)
          </button>
          <p className="text-xs text-muted">
            Google Calendar: Settings, Import &amp; export, Export. Apple Calendar: File, Export.
          </p>
        </div>
      )}

      {hasSchedule && (
        <ul className="mt-2 space-y-1.5">
          {sessions.length === 0 && <li className="text-xs text-muted">No classes on this day.</li>}
          {sessions.map((session) => {
            const building = matchBuilding(session.location);
            return (
              <li key={`${session.id}-${session.startMinutes}`}>
                <button
                  type="button"
                  onClick={() => plan(session)}
                  className="w-full text-left rounded-lg border border-line bg-paper px-3 py-2 min-h-[44px] hover:border-navy focus:outline-none focus-visible:ring-2 focus-visible:ring-sky cursor-pointer"
                >
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="text-[13px] font-semibold text-ink">{session.title}</span>
                    <span className="shrink-0 text-xs font-semibold text-navy">
                      {formatClock(session.startMinutes)}
                    </span>
                  </span>
                  <span className="mt-0.5 flex items-center gap-1 text-xs text-muted">
                    <MapPin className="w-3 h-3 shrink-0" aria-hidden="true" />
                    {building
                      ? building.name
                      : session.location
                      ? `${session.location}: choose a destination above`
                      : 'No location: choose a destination above'}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {message && (
        <p
          role="status"
          className={`mt-2 text-xs ${message.tone === 'ok' ? 'text-[#136B42]' : 'text-[#B3261E]'}`}
        >
          {message.text}
        </p>
      )}
      {fileInput}
    </section>
  );
};
