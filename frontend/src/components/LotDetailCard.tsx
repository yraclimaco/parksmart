/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { motion } from 'motion/react';
import { CalendarClock, CheckCircle2, Clock, Footprints, Info, X, XCircle } from 'lucide-react';
import { SpotActions } from './SpotActions.tsx';
import { AvailabilityMeter } from './AvailabilityMeter.tsx';
import { LotAerial } from './LotAerial.tsx';
import { BackendEstimate, CampusDestination, ParkingLot, PermitType } from '../types.ts';
import { estimateWalkingTime } from '../data/sampleRecommendations.ts';
import { availabilityAt, tightFrom } from '../utils/availabilityModel.ts';
import { accessLabel, formatAccessTime, lotAccess, relyOnUnverifiedDAccess, usableCategories } from '../utils/permitRules.ts';

interface LotDetailCardProps {
  lot: ParkingLot;
  /** Permit currently chosen in the planner form. */
  userPermit: PermitType;
  /** Arrival time from the form; null if the date/time is missing or invalid. */
  arrival: Date | null;
  /** Time the availability numbers describe (the time scrubber). */
  availabilityTime: Date;
  /** Null until the user picks a destination; the walk row is hidden then. */
  destination: CampusDestination | null;
  /** "First choice", "Backup" or "#3" when this lot is one of the current results. */
  rankLabel?: string | null;
  isConfirmed: boolean;
  onConfirm: () => void;
  /** Moves the arrival to a time when this permit can use the lot. */
  onPlanFor: (date: Date) => void;
  onClose: () => void;
  /**
   * Results come from the backend: sample availability and sample permit rules are not
   * shown. ``backendEstimate`` is set when this lot is one of the backend's results.
   */
  backendMode?: boolean;
  backendEstimate?: BackendEstimate | null;
}

/**
 * Apple Maps style place card for a single parking structure. Opens when any pin is
 * selected, so people can check a lot without running a full recommendation search.
 * Positioning and the enter/exit animation are handled by the parent.
 */
export const LotDetailCard: React.FC<LotDetailCardProps> = ({
  lot,
  userPermit,
  arrival,
  availabilityTime,
  destination,
  rankLabel = null,
  isConfirmed,
  onConfirm,
  onPlanFor,
  onClose,
  backendMode = false,
  backendEstimate = null,
}) => {
  const percent = availabilityAt(lot, availabilityTime);
  const tight = tightFrom(lot, availabilityTime);
  const isWeekend = availabilityTime.getDay() === 0 || availabilityTime.getDay() === 6;
  const timeLabel = availabilityTime.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  // Hours are checked at the arrival time in the form (falls back to now)
  const when = arrival ?? new Date();
  const access = lotAccess(userPermit, lot.spaceCategories, when);
  const permitWorks = access.status === 'always' || access.status === 'until';
  const usable = usableCategories(userPermit, lot.spaceCategories, when);
  const walkMinutes = destination ? estimateWalkingTime(lot, destination.id) : null;

  return (
    <motion.div
      // Fade lives on the glass element itself so the blur renders from the first frame
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.14, ease: 'easeOut' }}
      role="dialog"
      aria-label={`${lot.name} details`}
      className="w-[340px] max-w-[calc(100vw-2rem)] p-4 rounded-2xl bg-white border border-line shadow-[0_12px_32px_rgba(24,43,73,0.22)] text-navy"
    >
      {/* Aerial photo of the lot (USGS NAIP), keyed so switching lots restarts the fade */}
      <LotAerial key={lot.locationId} lot={lot} />

      {/* Header: glyph, name, close */}
      <div className="flex items-start gap-3">
        <div className="shrink-0 w-10 h-10 rounded-full bg-navy border-2 border-white text-white font-serif font-semibold text-xl flex items-center justify-center shadow-[0_2px_6px_rgba(24,43,73,0.3)]">
          P
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="font-serif text-[21px] font-semibold leading-tight tracking-[-0.005em] text-navy">{lot.name}</h2>
          <p className="text-xs text-muted mt-0.5 flex items-center gap-1.5">
            {rankLabel && (
              <span
                className={`px-2 py-0.5 rounded text-[12px] font-semibold ${
                  rankLabel === 'First choice' ? 'bg-sun text-navy' : 'bg-paper text-navy border border-line'
                }`}
              >
                {rankLabel}
              </span>
            )}
            <span>{lot.kind === 'lot' ? 'Surface lot' : 'Parking structure'}</span>
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close lot details"
          className="shrink-0 w-7 h-7 rounded-full bg-paper hover:bg-line text-muted flex items-center justify-center transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky/40 cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Availability: the same readout the result cards show. With the backend, only
          its own estimate for a recommended lot is shown, never the sample model. */}
      {backendMode ? (
        <div className="mt-4">
          {backendEstimate ? (
            <AvailabilityMeter
              percent={backendEstimate.availablePercent}
              timeLabel={(arrival ?? availabilityTime).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
              size="lg"
            />
          ) : (
            <p className="text-[13px] text-muted">
              No estimate here. Only lots recommended for your search show a historical estimate.
            </p>
          )}
        </div>
      ) : (
      <div className="mt-4">
        <AvailabilityMeter percent={percent} timeLabel={timeLabel} size="lg" />
        {/* Campus-specific insight from the (sample) daily pattern */}
        <p className="mt-2 text-[12px] text-muted">
          {tight
            ? `Usually gets tight from ${tight.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })} on ${isWeekend ? 'weekends' : 'weekdays'}.`
            : `Usually stays open all day on ${isWeekend ? 'weekends' : 'weekdays'}.`}
        </p>
      </div>
      )}

      {/* Facts */}
      <div className="mt-4 rounded-2xl bg-paper divide-y divide-line text-[13px]">
        {/* Permit hours and stall types use sample stall data, so they are hidden with the backend */}
        {!backendMode && <div className="flex items-center gap-2 px-3 py-2.5">
          {access.status === 'always' ? (
            <CheckCircle2 className="w-4 h-4 text-[#1E8E5A] shrink-0" aria-hidden="true" />
          ) : permitWorks ? (
            <Clock className="w-4 h-4 text-[#1E8E5A] shrink-0" aria-hidden="true" />
          ) : (
            <XCircle className="w-4 h-4 text-[#C0392B] shrink-0" aria-hidden="true" />
          )}
          <span className="font-medium">{accessLabel(access, userPermit, when, lot.spaceCategories)}</span>
          <div className="ml-auto flex gap-1" aria-label={`Space types: ${lot.spaceCategories.join(', ')}`}>
            {lot.spaceCategories.map((category) => (
              <span
                key={category}
                className={`px-1.5 rounded font-mono text-[10px] leading-4 ${
                  usable.includes(category)
                    ? 'bg-navy text-white font-bold'
                    : 'bg-white border border-line text-muted line-through'
                }`}
              >
                {category}
              </span>
            ))}
          </div>
        </div>}
        {!backendMode && relyOnUnverifiedDAccess(userPermit, lot.spaceCategories, when) && (
          <div className="flex items-start gap-2 px-3 py-2.5 text-[#835300]">
            <span>Needs verification: this relies on D stalls, and UCSD's Sept 18, 2026 D restriction may change who can use them.</span>
          </div>
        )}
        {lot.accessNote && (
          <div className="flex items-start gap-2 px-3 py-2.5 text-[#835300]">
            <Info className="w-4 h-4 shrink-0 mt-px" aria-hidden="true" />
            <span>{lot.accessNote}</span>
          </div>
        )}
        {destination && walkMinutes !== null && (
          <div className="flex items-center gap-2 px-3 py-2.5">
            <Footprints className="w-4 h-4 text-muted shrink-0" aria-hidden="true" />
            <span>
              <span className="font-medium">{walkMinutes} min walk</span>
              <span className="text-muted"> to {destination.name}</span>
            </span>
          </div>
        )}
      </div>

      <div className="mt-3">
        {backendMode ? (
          backendEstimate && (
            <SpotActions tone="primary" isConfirmed={isConfirmed} onConfirm={onConfirm} lot={lot} />
          )
        ) : permitWorks ? (
          <SpotActions
            tone="primary"
            isConfirmed={isConfirmed}
            onConfirm={onConfirm}
            lot={lot}
          />
        ) : access.status === 'from' ? (
          // Not usable at this time, but later today/this week: offer to plan for then
          <button
            type="button"
            onClick={() => onPlanFor(access.from)}
            className="w-full flex items-center justify-center gap-1.5 py-2.5 rounded-xl bg-navy hover:bg-navy-2 text-white text-[13px] font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky/40 cursor-pointer"
          >
            <CalendarClock className="w-4 h-4" aria-hidden="true" />
            Plan for {formatAccessTime(access.from, when)} instead
          </button>
        ) : (
          <p className="py-2.5 rounded-xl bg-paper text-center text-[13px] font-medium text-muted">
            Your {userPermit} permit can't park here. Try another permit or lot.
          </p>
        )}
      </div>

      <p className="mt-2 text-[11px] text-muted text-center">
        {backendMode
          ? 'Historical estimates from past surveys, not live availability'
          : 'Sample estimate, not live availability'}
      </p>
    </motion.div>
  );
};
