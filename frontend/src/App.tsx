/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Menu } from 'lucide-react';
import { AnimatePresence, MotionConfig, motion } from 'motion/react';
import { MapContainer } from './components/MapContainer.tsx';
import { PreferenceForm } from './components/PreferenceForm.tsx';
import { ResultsList } from './components/ResultsList.tsx';
import { DevStateControl } from './components/DevStateControl.tsx';
import { LotDetailCard } from './components/LotDetailCard.tsx';
import { UsualTripCard } from './components/UsualTripCard.tsx';
import { SCRUB_MAX, SCRUB_MIN, TimeScrubber } from './components/TimeScrubber.tsx';
import ucsdLogo from './assets/ucsd-logo.png';
import { ANIMATION_TIMINGS, isOnCampus } from './constants.ts';
import { findDestination, getDestination, makePinDestinationId } from './data/destinations.ts';
import { getArrivalError } from './utils/arrival.ts';
import { UsualTrip, forgetUsualTrip, loadUsualTrip, nextUsualDate, saveUsualTrip } from './utils/usualTrip.ts';
import { tightFrom } from './utils/availabilityModel.ts';
import { parseArrival } from './utils/permitRules.ts';
import { SAMPLE_LOTS, getSampleRecommendations } from './data/sampleRecommendations.ts';
import {
  ParkingPlannerRequest,
  ParkingRecommendation,
  DevSimulationState,
} from './types.ts';

/** How many earlier searches "Recent" keeps for this visit. */
const MAX_HISTORY = 5;

/** Same destination, date, time and permit. */
function sameRequest(a: ParkingPlannerRequest, b: ParkingPlannerRequest): boolean {
  return (
    a.destinationId === b.destinationId &&
    a.arrivalDate === b.arrivalDate &&
    a.arrivalTime === b.arrivalTime &&
    a.permitType === b.permitType
  );
}

/** Width the open planner panel covers on the left (380px panel + 24px gap). */
const PANEL_OFFSET_PX = 404;

/**
 * Returns today's date formatted as YYYY-MM-DD in local time.
 */
function toDateString(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function getTodayDateString(): string {
  return toDateString(new Date());
}

/**
 * Returns the current local time formatted as HH:MM (24-hour, as <input type="time"> expects).
 */
function getCurrentTimeString(): string {
  const now = new Date();
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
}

/** True on phone-width screens, where the planner becomes a bottom sheet instead of a left panel. */
function useIsMobile(): boolean {
  const query = '(max-width: 639px)';
  const [isMobile, setIsMobile] = useState<boolean>(() => window.matchMedia(query).matches);
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setIsMobile(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  return isMobile;
}

/** The state simulator is for developers: shown in dev builds, or in production with ?dev in the URL. */
const showDevTools = import.meta.env.DEV || new URLSearchParams(window.location.search).has('dev');

/** "HH:MM" to minutes after midnight, clamped to the scrubber's range. */
function minutesOf(time: string): number {
  const [h, m] = time.split(':').map(Number);
  const minutes = Number.isFinite(h) && Number.isFinite(m) ? h * 60 + m : 9 * 60;
  return Math.min(SCRUB_MAX, Math.max(SCRUB_MIN, minutes));
}

/** Minutes after midnight to "HH:MM". */
function timeOf(minutes: number): string {
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

/**
 * Main application component.
 * Owns state for formInputs, recommendations, selectedLocationId, and simulated UI states.
 */
export default function App() {
  // 1. Form inputs. No destination until the user picks one (no Geisel default);
  // date and time start at right now.
  // "Your usual" only exists after a real search (saved in this browser only); it is
  // offered as a card, never prefilled into the form.
  const [usualTrip, setUsualTrip] = useState<UsualTrip | null>(() => loadUsualTrip());

  const [formInputs, setFormInputs] = useState<ParkingPlannerRequest>(() => ({
    destinationId: '',
    arrivalDate: getTodayDateString(),
    arrivalTime: getCurrentTimeString(),
    permitType: 'S',
  }));

  // Earlier searches this visit, most recent first (the current one is not included).
  // Picking one swaps it with the current search, so X then Y, then "Recent", returns to X.
  const [searchHistory, setSearchHistory] = useState<ParkingPlannerRequest[]>([]);

  // 2. Recommendations State
  const [recommendations, setRecommendations] = useState<ParkingRecommendation[]>([]);

  // 3. Selection State (synchronizes selected card with map marker)
  const [selectedLocationId, setSelectedLocationId] = useState<string | null>(null);

  // 4. Loading & Animation State
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // The exact request the current results were computed for. null until the first
  // search, which is how the panel knows to show its "enter your trip" prompt.
  const [searchedRequest, setSearchedRequest] = useState<ParkingPlannerRequest | null>(null);
  const searchedRequestRef = useRef<ParkingPlannerRequest | null>(null);

  // Lot the user confirmed with "Select this spot" (routing will hook in here later)
  const [confirmedLotId, setConfirmedLotId] = useState<string | null>(null);

  // Lot detail card (opened by clicking a pin on the map)
  const [isDetailOpen, setIsDetailOpen] = useState<boolean>(false);

  // Time scrubber: previewed time of day (minutes after midnight) and play state.
  // Follows the arrival time until the user scrubs.
  const [previewMinutes, setPreviewMinutes] = useState<number>(() => minutesOf(formInputs.arrivalTime));
  const [isTimelinePlaying, setIsTimelinePlaying] = useState<boolean>(false);
  // The Time tool is a toggle in the map's controls; closing it snaps the map and every
  // number back to the arrival time, so nothing keeps showing a time you can no longer see.
  const [isTimeOpen, setIsTimeOpen] = useState<boolean>(false);
  useEffect(() => {
    setPreviewMinutes(minutesOf(formInputs.arrivalTime));
  }, [formInputs.arrivalTime]);
  const handleTimeToggle = useCallback(() => {
    setIsTimeOpen((open) => {
      if (open) setIsTimelinePlaying(false);
      return !open;
    });
  }, []);
  useEffect(() => {
    if (!isTimeOpen) setPreviewMinutes(minutesOf(formInputs.arrivalTime));
  }, [isTimeOpen, formInputs.arrivalTime]);
  const previewTime = useMemo(() => {
    const day = parseArrival(formInputs.arrivalDate, '00:00') ?? new Date();
    day.setHours(Math.floor(previewMinutes / 60), previewMinutes % 60, 0, 0);
    return day;
  }, [formInputs.arrivalDate, previewMinutes]);

  // Side panel open/closed (hamburger toggle)
  const [isPanelOpen, setIsPanelOpen] = useState<boolean>(true);
  const isMobile = useIsMobile();

  // 5. Dev State Simulator
  const [devState, setDevState] = useState<DevSimulationState>('normal');

  // Phone: the lot card needs the space, so tuck the planner away while they are open
  useEffect(() => {
    if (isMobile && isDetailOpen) setIsPanelOpen(false);
  }, [isMobile, isDetailOpen]);

  // Phone: the sheet is short, so bring the results into view after each search
  useEffect(() => {
    if (!isMobile || searchedRequest === null || isLoading) return;
    // Scroll only the sheet's own list (scrollIntoView can also shift the page behind it)
    const results = document.getElementById('planner-results');
    const box = document.getElementById('planner-scroll');
    if (results && box) {
      box.scrollTo({
        top: box.scrollTop + results.getBoundingClientRect().top - box.getBoundingClientRect().top - 8,
        behavior: 'smooth',
      });
    }
  }, [isMobile, searchedRequest, isLoading]);

  // Compute recommendations from current formInputs
  const runPlanner = useCallback(
    (customInputs?: ParkingPlannerRequest) => {
      const inputs = customInputs || formInputs;
      if (getArrivalError(inputs)) return; // the form shows the message; nothing to search
      if (!findDestination(inputs.destinationId)) return; // no destination picked yet
      setIsLoading(true);
      setIsDetailOpen(false); // a new search shows results in the panel, not the pin card
      setConfirmedLotId(null);

      const finish = () => {
        const response = getSampleRecommendations(inputs);
        setRecommendations(response.recommendations);
        // Move the search being replaced into history (unless it is the same trip)
        const previous = searchedRequestRef.current;
        if (previous && !sameRequest(previous, inputs)) {
          setSearchHistory((history) =>
            [previous, ...history.filter((r) => !sameRequest(r, previous) && !sameRequest(r, inputs))].slice(0, MAX_HISTORY)
          );
        }
        searchedRequestRef.current = inputs;
        setSearchedRequest(inputs);
        setIsLoading(false);

        // Pre-select the First Choice recommendation lot by default
        setSelectedLocationId(response.recommendations[0]?.lot.locationId ?? null);

        // Remember this trip as "your usual" (this browser only). A dropped pin is a
        // one-off spot, not a place to offer again, so it is not saved.
        if (findDestination(inputs.destinationId)?.isPin) return;
        const usual: UsualTrip = {
          destinationId: inputs.destinationId,
          permitType: inputs.permitType,
          arrivalTime: inputs.arrivalTime,
        };
        saveUsualTrip(usual);
        setUsualTrip(usual);
      };

      // Sample data answers instantly; a real API call would keep the loading state up
      if (ANIMATION_TIMINGS.SHIMMER_DURATION_MS === 0) {
        finish();
        return;
      }
      const timer = setTimeout(finish, ANIMATION_TIMINGS.SHIMMER_DURATION_MS);
      return () => clearTimeout(timer);
    },
    [formInputs]
  );

  // Handle preference form changes
  const handleFormChange = (changes: Partial<ParkingPlannerRequest>) => {
    if (changes.destinationId !== undefined) setPinNotice(null);
    setFormInputs((prev) => ({
      ...prev,
      ...changes,
    }));
  };

  // Handle Form Submission
  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (devState !== 'normal') {
      setDevState('normal');
    }
    runPlanner();
  };

  // Handle lot selection (from card click or marker click)
  const handleSelectLot = useCallback((locationId: string) => {
    setSelectedLocationId((prev) => (prev === locationId ? null : locationId));
  }, []);

  // Handle clearing selection on map background click
  // Pin clicks on the map also open the lot detail card (panel card clicks do not,
  // since those cards already show the same details)
  const selectedIdRef = useRef<string | null>(null);
  selectedIdRef.current = selectedLocationId;
  const handleSelectLotFromMap = useCallback((locationId: string) => {
    const next = selectedIdRef.current === locationId ? null : locationId;
    setSelectedLocationId(next);
    setIsDetailOpen(next !== null);
  }, []);

  // Whenever nothing is selected (from any source), the card is closed too
  useEffect(() => {
    if (!selectedLocationId) setIsDetailOpen(false);
  }, [selectedLocationId]);

  const handleClearSelection = useCallback(() => {
    setIsDetailOpen(false);
    setSelectedLocationId(null);
  }, []);

  // Lot whose detail card is open (any selected pin or card)
  const selectedLot = useMemo(
    () => SAMPLE_LOTS.find((lot) => lot.locationId === selectedLocationId) ?? null,
    [selectedLocationId]
  );

  // Esc closes the lot card
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsDetailOpen(false);
        setSelectedLocationId(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Handle retry from error state
  const handleRetry = () => {
    setDevState('normal');
    runPlanner();
  };

  // Handle resetting filters from empty state
  const handleResetFilters = () => {
    const updated: ParkingPlannerRequest = { ...formInputs, permitType: 'S' };
    setFormInputs(updated);
    setDevState('normal');
    runPlanner(updated);
  };

  // Selected campus destination (or dropped pin); null until the user picks one
  const currentDestination = useMemo(
    () => findDestination(formInputs.destinationId) ?? null,
    [formInputs.destinationId]
  );

  // A parking lot picked in the search box: select its pin and open its card.
  // It does not become the destination.
  const handleSelectParking = useCallback((locationId: string) => {
    setSelectedLocationId(locationId);
    setIsDetailOpen(true);
  }, []);

  // "Drop pin" on the map: use the clicked spot as the destination
  const [pinNotice, setPinNotice] = useState<string | null>(null);
  const handleDropPin = useCallback((latitude: number, longitude: number): boolean => {
    if (!isOnCampus(latitude, longitude)) {
      setPinNotice('That spot is off campus. Drop the pin on the UCSD campus, or pick a building.');
      return false;
    }
    setPinNotice(null);
    setFormInputs((prev) => ({ ...prev, destinationId: makePinDestinationId(latitude, longitude) }));
    return true;
  }, []);

  // Turning Drop pin off removes the dropped pin
  const handleClearPin = useCallback(() => {
    setPinNotice(null);
    setFormInputs((prev) => (findDestination(prev.destinationId)?.isPin ? { ...prev, destinationId: '' } : prev));
  }, []);

  // Re-run an earlier search from "Recent"
  const handleRestoreSearch = (request: ParkingPlannerRequest) => {
    setFormInputs(request);
    setDevState('normal');
    runPlanner(request);
  };

  // Instant answer for the usual trip, shown before the first search
  const usualPreview = useMemo(() => {
    if (!usualTrip) return null;
    const request: ParkingPlannerRequest = {
      destinationId: usualTrip.destinationId,
      permitType: usualTrip.permitType,
      arrivalTime: usualTrip.arrivalTime,
      arrivalDate: nextUsualDate(usualTrip.arrivalTime),
    };
    const arrival = parseArrival(request.arrivalDate, request.arrivalTime);
    if (!arrival) return null;
    if (!findDestination(request.destinationId)) return null;
    const topPick = getSampleRecommendations(request).recommendations[0] ?? null;
    const tight = topPick ? tightFrom(topPick.lot, arrival) : null;
    const fmt = (d: Date) => d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
    const isToday = request.arrivalDate === getTodayDateString();
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const isTomorrow = request.arrivalDate === toDateString(tomorrow);
    return {
      request,
      destinationName: getDestination(request.destinationId).name,
      whenLabel: `${isToday ? 'today' : isTomorrow ? 'tomorrow' : arrival.toLocaleDateString('en-US', { weekday: 'long' })} at ${fmt(arrival)}`,
      topPick,
      tightAt: tight ? fmt(tight) : null,
    };
  }, [usualTrip]);

  const handleShowUsual = () => {
    if (!usualPreview) return;
    setFormInputs(usualPreview.request);
    runPlanner(usualPreview.request);
  };
  const handleForgetUsual = () => {
    forgetUsualTrip();
    setUsualTrip(null);
  };

  // Results go stale when any trip detail changes after the search that produced them
  const isStale =
    searchedRequest !== null &&
    (searchedRequest.destinationId !== formInputs.destinationId ||
      searchedRequest.permitType !== formInputs.permitType ||
      searchedRequest.arrivalDate !== formInputs.arrivalDate ||
      searchedRequest.arrivalTime !== formInputs.arrivalTime);

  // Inline validation for the arrival date/time (empty or already passed)
  const arrivalError = getArrivalError(formInputs);

  // First choice / backup IDs for labeling pins (hidden while results are stale)
  const rankedLotIds = useMemo(() => {
    if (isStale || devState !== 'normal') return { first: null, backup: null, third: null };
    return {
      first: recommendations[0]?.lot.locationId ?? null,
      backup: recommendations[1]?.lot.locationId ?? null,
      third: recommendations[2]?.lot.locationId ?? null,
    };
  }, [recommendations, isStale, devState]);

  const handleConfirmLot = useCallback((locationId: string) => {
    setConfirmedLotId((prev) => (prev === locationId ? null : locationId));
  }, []);

  // Derive active rendering state based on normal computation or dev simulator
  const activeIsLoading = devState === 'loading' || isLoading;
  const activeIsError = devState === 'error';
  const activeRecommendations = useMemo(() => {
    if (devState === 'empty') return [];
    if (devState === 'error' || devState === 'loading') return [];
    return recommendations;
  }, [devState, recommendations]);

  return (
    // reducedMotion="user" turns off Motion animations for people who ask their OS for less motion
    <MotionConfig reducedMotion="user">
    <div className="relative w-screen h-screen overflow-hidden bg-slate-100 font-sans text-navy select-none">
      {/* Full-Screen MapLibre GL Map */}
      <MapContainer
        lots={SAMPLE_LOTS}
        selectedLocationId={selectedLocationId}
        selectedDestination={currentDestination}
        onSelectLot={handleSelectLotFromMap}
        onClearSelection={handleClearSelection}
        onDropPin={handleDropPin}
        hasDroppedPin={currentDestination?.isPin === true}
        onClearPin={handleClearPin}
        isTimeOpen={isTimeOpen}
        onTimeToggle={handleTimeToggle}
        timePanel={
          <TimeScrubber
            day={previewTime}
            minutes={previewMinutes}
            onMinutesChange={setPreviewMinutes}
            isPlaying={isTimelinePlaying}
            onPlayingChange={setIsTimelinePlaying}
            differsFromArrival={previewMinutes !== minutesOf(formInputs.arrivalTime)}
            onUseTime={() => handleFormChange({ arrivalTime: timeOf(previewMinutes) })}
          />
        }
        isPanelOpen={isPanelOpen}
        isDetailOpen={isDetailOpen}
        rankedLotIds={rankedLotIds}
        availabilityTime={previewTime}
      />

      {/* Hamburger toggle: stays in the top-left whether the panel is open or closed */}
      <button
        type="button"
        onClick={() => setIsPanelOpen((open) => !open)}
        aria-label={isPanelOpen ? 'Hide planner panel' : 'Show planner panel'}
        aria-expanded={isPanelOpen}
        aria-controls="planner-panel"
        className={`absolute top-[22px] left-4 max-sm:left-[29px] ${
          isPanelOpen ? 'max-sm:top-[calc(50%+23px)]' : 'top-4 max-sm:left-4'
        } z-30 w-9 h-9 rounded-[10px] flex items-center justify-center text-navy transition-colors duration-200 hover:bg-paper active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky/50 cursor-pointer ${
          isPanelOpen
            ? ''
            : 'bg-white border border-line shadow-[0_1px_2px_rgba(24,43,73,0.08),0_4px_12px_rgba(24,43,73,0.1)]'
        }`}
      >
        <Menu className="w-5 h-5" aria-hidden="true" />
      </button>

      {/* Planner: a solid sheet on the left edge (a bottom sheet on phones), slides out when hidden */}
      <aside
        id="planner-panel"
        aria-label="Parking planner controls and recommendations"
        aria-hidden={!isPanelOpen}
        inert={!isPanelOpen}
        className={`absolute top-0 left-0 bottom-0 w-[388px] max-w-full max-sm:top-1/2 max-sm:bottom-9 max-sm:left-3 max-sm:right-3 max-sm:w-auto max-sm:max-w-none z-20 flex flex-col transition-transform duration-300 ease-out motion-reduce:transition-none ${
          isPanelOpen
            ? 'translate-x-0 pointer-events-auto'
            : '-translate-x-full max-sm:translate-x-0 max-sm:translate-y-[calc(100%+3rem)] pointer-events-none'
        }`}
      >
        <div className="flex-1 flex flex-col bg-white border-r border-line max-sm:border max-sm:rounded-2xl shadow-[4px_0_24px_rgba(24,43,73,0.12)] max-sm:shadow-[0_4px_24px_rgba(24,43,73,0.2)] overflow-hidden">
          {/* Panel header. Left padding leaves room for the hamburger button that sits on top. */}
          <header className="pl-[60px] pr-4 pt-[22px] pb-3.5 border-b-2 border-gold shrink-0">
            {/* One 36px row, centered on the hamburger button that sits on top of its left end */}
            <div className="flex items-center justify-between gap-3 h-9">
              <div className="flex items-center gap-2 min-w-0">
                <div
                  aria-hidden="true"
                  className="w-9 h-9 rounded-lg bg-navy flex items-center justify-center text-sun font-serif font-semibold text-[20px] leading-none"
                >
                  <span className="-translate-y-px">P</span>
                </div>
                <h1 className="font-serif text-[26px] font-semibold text-navy tracking-[-0.01em] leading-none -translate-y-px">
                  ParkSmart
                </h1>
              </div>

              {/* UC San Diego wordmark (transparent PNG, sits directly on the panel) */}
              <img src={ucsdLogo} alt="UC San Diego" className="h-[20px] w-auto block shrink-0" />
            </div>
            <p className="mt-2 text-[13px] text-muted leading-snug">
              Find where to park before you arrive.
            </p>
          </header>

          {/* Internally Scrollable Body */}
          <div id="planner-scroll" className="flex-1 overflow-y-auto px-5 py-4 space-y-4 overscroll-contain focus:outline-none">
            {/* Preference Form Section */}
            <section aria-labelledby="planner-preferences-title">
              <h2 id="planner-preferences-title" className="sr-only">
                Trip Preferences
              </h2>
              <PreferenceForm
                formData={formInputs}
                onChange={handleFormChange}
                onSubmit={handleFormSubmit}
                isLoading={activeIsLoading}
                arrivalError={arrivalError}
                onSetArrivalNow={() =>
                  handleFormChange({ arrivalDate: getTodayDateString(), arrivalTime: getCurrentTimeString() })
                }
                submitLabel={isStale ? 'Update results' : 'Find parking'}
                onSelectParking={handleSelectParking}
              />
              {pinNotice && (
                <p role="status" className="mt-3 px-3 py-2 rounded-lg bg-[#D98A00]/12 border border-[#D98A00]/30 text-[12px] font-medium text-[#835300]">
                  {pinNotice}
                </p>
              )}
            </section>

            {/* Subtle Divider */}
            <div className="flex items-center gap-3 py-0.5 text-[13px] font-semibold text-navy">
              <span>Results</span>
              <div className="flex-1 border-t border-line" />
            </div>

            {/* Results Section */}
            <section id="planner-results" aria-labelledby="planner-results-title">
              <h2 id="planner-results-title" className="sr-only">
                Recommended Parking
              </h2>
              <ResultsList
                isLoading={activeIsLoading}
                isError={activeIsError}
                recommendations={activeRecommendations}
                searchedRequest={searchedRequest}
                searchHistory={searchHistory}
                onRestoreSearch={handleRestoreSearch}
                showIntroPrompt={searchedRequest === null && devState === 'normal'}
                usualTripCard={
                  usualPreview && (
                    <UsualTripCard
                      destinationName={usualPreview.destinationName}
                      whenLabel={usualPreview.whenLabel}
                      topPick={usualPreview.topPick}
                      tightAt={usualPreview.tightAt}
                      onShowOptions={handleShowUsual}
                      onForget={handleForgetUsual}
                    />
                  )
                }
                isStale={isStale}
                availabilityTime={previewTime}
                confirmedLotId={confirmedLotId}
                onConfirmLot={handleConfirmLot}
                selectedLocationId={selectedLocationId}
                onSelectLot={handleSelectLot}
                onRetry={handleRetry}
                onResetFilters={handleResetFilters}
              />
            </section>
          </div>

          {/* Panel Footer Note */}
          <footer className="px-5 py-2.5 bg-paper border-t border-line text-[11px] text-muted leading-snug shrink-0">
            <span>Sample data. Estimates only. Unofficial student project, not affiliated with UC San Diego.</span>
          </footer>
        </div>
      </aside>

      {/* Dev Simulator Toggle (Tucked into bottom right corner) */}
      {/* Lot detail card: centered in the visible map area (beside the panel when it is open) */}
      <div
        className="absolute bottom-6 max-sm:bottom-10 z-20 -translate-x-1/2 transition-[left] duration-300 ease-out pointer-events-none"
        style={{ left: isPanelOpen && !isMobile ? `calc(${PANEL_OFFSET_PX}px + (100% - ${PANEL_OFFSET_PX}px) / 2)` : '50%' }}
      >
        <AnimatePresence mode="wait">
          {isDetailOpen && selectedLot && (
            // Only transforms here. Fading a *parent* of a backdrop-filter element makes
            // Chrome skip the blur until the fade ends (the frost "pops in"), so the
            // opacity fade lives on the glass card itself (see LotDetailCard).
            <motion.div
              key={selectedLot.locationId}
              className="pointer-events-auto"
              initial={{ y: 20, scale: 0.97 }}
              animate={{ y: 0, scale: 1 }}
              exit={{ y: 12, scale: 0.98 }}
              transition={{ type: 'spring', stiffness: 600, damping: 38 }}
            >
              <LotDetailCard
                lot={selectedLot}
                userPermit={formInputs.permitType}
                arrival={parseArrival(formInputs.arrivalDate, formInputs.arrivalTime)}
                availabilityTime={previewTime}
                destination={currentDestination}
                rankLabel={
                  isStale
                    ? null
                    : activeRecommendations.find((r) => r.lot.locationId === selectedLot.locationId)?.badgeLabel ?? null
                }
                isConfirmed={confirmedLotId === selectedLot.locationId}
                onConfirm={() => handleConfirmLot(selectedLot.locationId)}
                onPlanFor={(date) =>
                  handleFormChange({
                    arrivalDate: `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`,
                    arrivalTime: `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`,
                  })
                }
                onClose={handleClearSelection}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {showDevTools && (
        <DevStateControl
          currentState={devState}
          onStateChange={(state) => setDevState(state)}
        />
      )}
    </div>
    </MotionConfig>
  );
}
