/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Search, ChevronDown, Check, MapPin, Star, X } from 'lucide-react';
import { motion } from 'motion/react';
import { PERMIT_OPTIONS } from '../constants.ts';
import { POPULAR_DESTINATIONS, findDestination, searchDestinations } from '../data/destinations.ts';
import { maxArrivalDate } from '../utils/arrival.ts';
import { loadFavorites, toggleFavorite } from '../utils/favorites.ts';
import { ALL_PARKING } from '../data/parkingLots.ts';
import { ParkingPlannerRequest, CampusDestination, ParkingLot } from '../types.ts';

interface PreferenceFormProps {
  formData: ParkingPlannerRequest;
  onChange: (newData: Partial<ParkingPlannerRequest>) => void;
  onSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
  /** Problem with the arrival date/time, shown under the fields; blocks searching. */
  arrivalError: string | null;
  /** Resets the arrival date/time to right now. */
  onSetArrivalNow: () => void;
  /** "Find parking", or "Update results" when the shown results are stale. */
  submitLabel: string;
  /** A parking lot picked from the search box: show it on the map (not a destination). */
  onSelectParking: (locationId: string) => void;
}

/** One row in the destination dropdown: a place to go, or a lot to look at. */
type Option =
  | { kind: 'place'; destination: CampusDestination; matchedOn?: string }
  | { kind: 'parking'; lot: ParkingLot };

const MAX_PARKING_MATCHES = 6;

/** Parking lots whose name or P-number matches the query ("gilman", "p406", "406"). */
function searchParking(query: string): ParkingLot[] {
  const q = query.trim().toLowerCase();
  if (q.length < 2) return [];
  return ALL_PARKING.filter((lot) => {
    const name = lot.name.toLowerCase();
    return name.includes(q) || (/^\d+$/.test(q) && name.includes(`p${q.padStart(3, '0')}`));
  })
    .sort((a, b) => Number(b.name.toLowerCase().startsWith(q)) - Number(a.name.toLowerCase().startsWith(q)))
    .slice(0, MAX_PARKING_MATCHES);
}

/** Small section heading inside the dropdown. */
const SectionLabel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <li role="presentation" className="px-3 pt-2 pb-1 text-[12px] font-semibold text-muted">
    {children}
  </li>
);

/**
 * Clean floating preference form with searchable destination dropdown,
 * date/time inputs, permit pills, and primary submission action.
 */
export const PreferenceForm: React.FC<PreferenceFormProps> = ({
  formData,
  onChange,
  onSubmit,
  isLoading,
  arrivalError,
  onSetArrivalNow,
  submitLabel,
  onSelectParking,
}) => {
  const [isDestinationOpen, setIsDestinationOpen] = useState(false);
  const [destinationSearch, setDestinationSearch] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  // Starred places (this browser only), shown first in the dropdown
  const [favorites, setFavorites] = useState<string[]>(() => loadFavorites());
  const dropdownRef = useRef<HTMLDivElement | null>(null);
  const listRef = useRef<HTMLUListElement | null>(null);

  // No destination until the user picks one (or drops a pin on the map)
  const selectedDestination = findDestination(formData.destinationId) ?? null;
  const query = destinationSearch.trim();

  // Before typing: popular places. While typing: matching places and parking, with
  // parking first when the query is clearly a lot ("Gilman", "P406")
  const favoritePlaces = useMemo(
    () =>
      favorites
        .map((id) => findDestination(id))
        .filter((d): d is CampusDestination => d !== undefined && !d.isPin)
        .map((d): Option => ({ kind: 'place', destination: d })),
    [favorites]
  );
  const { places, parking } = useMemo(() => {
    if (!query) {
      return {
        places: POPULAR_DESTINATIONS.filter((d) => !favorites.includes(d.id)).map((d): Option => ({ kind: 'place', destination: d })),
        parking: [] as Option[],
      };
    }
    return {
      places: searchDestinations(query).map((m): Option => ({ kind: 'place', destination: m.destination, matchedOn: m.matchedOn })),
      parking: searchParking(query).map((lot): Option => ({ kind: 'parking', lot })),
    };
  }, [query, favorites]);
  const parkingFirst =
    parking.length > 0 &&
    (places.length === 0 || (parking[0].kind === 'parking' && parking[0].lot.name.toLowerCase().startsWith(query.toLowerCase())));
  const sections: Array<{ label: string; options: Option[] }> = (
    parkingFirst
      ? [{ label: 'Parking', options: parking }, { label: 'Places', options: places }]
      : [
          ...(query ? [] : [{ label: 'Favorites', options: favoritePlaces }]),
          { label: query ? 'Places' : 'Popular', options: places },
          { label: 'Parking', options: parking },
        ]
  ).filter((section) => section.options.length > 0);
  const flatOptions = sections.flatMap((section) => section.options);

  // Highlight the best match whenever the results change
  useEffect(() => setActiveIndex(0), [query]);

  // Keep the highlighted row in view while arrowing through the list
  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${activeIndex}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDestinationOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const closeDropdown = () => {
    setDestinationSearch('');
    setIsDestinationOpen(false);
  };

  const chooseOption = (option: Option) => {
    if (option.kind === 'place') onChange({ destinationId: option.destination.id });
    else onSelectParking(option.lot.locationId);
    closeDropdown();
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(flatOptions.length - 1, i + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(0, i - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const option = flatOptions[activeIndex];
      if (option) chooseOption(option);
    } else if (e.key === 'Escape') {
      e.stopPropagation();
      closeDropdown();
    }
  };

  let rowIndex = -1;

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      {/* Campus Destination Field */}
      <div className="relative" ref={dropdownRef}>
        <label
          id="destination-label"
          className="block text-[13px] font-semibold text-ink mb-1.5"
        >
          Destination
        </label>
        <button
          type="button"
          aria-labelledby="destination-label"
          aria-haspopup="listbox"
          aria-expanded={isDestinationOpen}
          onClick={() => setIsDestinationOpen(!isDestinationOpen)}
          className="w-full text-left px-3.5 py-2.5 rounded-[10px] bg-white border border-line hover:border-navy/40 focus:outline-none focus:ring-2 focus:ring-sky/30 focus:border-sky transition-all duration-150 flex items-center justify-between shadow-xs group"
        >
          <div className="flex items-center gap-2.5 min-w-0">
            {selectedDestination?.isPin ? (
              <MapPin className="w-4 h-4 text-ink shrink-0" />
            ) : (
              <Search className="w-4 h-4 text-muted group-hover:text-muted shrink-0 transition-colors" />
            )}
            <div className="truncate">
              {selectedDestination ? (
                <span className="text-sm font-medium text-navy">{selectedDestination.name}</span>
              ) : (
                <span className="text-sm text-muted">Where are you headed?</span>
              )}
            </div>
          </div>
          <ChevronDown
            className={`w-4 h-4 text-muted transition-transform duration-200 shrink-0 ${
              isDestinationOpen ? 'rotate-180 text-ink' : ''
            }`}
          />
        </button>

        {/* Searchable Dropdown Popup */}
        {isDestinationOpen && (
          <div className="absolute top-full left-0 right-0 mt-1.5 p-2 bg-white rounded-xl border border-line shadow-[0_12px_32px_rgba(24,43,73,0.18)] z-50 animate-in fade-in zoom-in-95 duration-150">
            <div className="relative mb-1">
              <Search className="w-3.5 h-3.5 text-muted absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={destinationSearch}
                onChange={(e) => setDestinationSearch(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                placeholder="Building, code (WLH) or parking lot"
                aria-label="Search buildings, class codes or parking"
                aria-controls="destination-options"
                aria-activedescendant={flatOptions.length ? `destination-option-${activeIndex}` : undefined}
                autoFocus
                className="w-full pl-8 pr-7 py-1.5 text-xs rounded-lg bg-paper border border-transparent focus:outline-none focus:ring-1 focus:ring-sky/30 text-navy"
              />
              {destinationSearch && (
                <button
                  type="button"
                  onClick={() => setDestinationSearch('')}
                  aria-label="Clear search"
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 w-5 h-5 rounded-full flex items-center justify-center text-muted hover:text-ink hover:bg-paper cursor-pointer"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
            <ul ref={listRef} id="destination-options" className="max-h-72 overflow-y-auto py-0.5 text-sm" role="listbox">
              {sections.map((section) => (
                <React.Fragment key={section.label}>
                  <SectionLabel>{section.label}</SectionLabel>
                  {section.options.map((option) => {
                    rowIndex += 1;
                    const index = rowIndex;
                    const isActive = index === activeIndex;
                    if (option.kind === 'parking') {
                      const { lot } = option;
                      return (
                        <li
                          key={`lot-${lot.locationId}`}
                          id={`destination-option-${index}`}
                          data-index={index}
                          role="option"
                          aria-selected={isActive}
                          onClick={() => chooseOption(option)}
                          onMouseMove={() => setActiveIndex(index)}
                          className={`px-3 py-2 rounded-lg cursor-pointer flex items-center gap-2.5 text-xs text-ink ${isActive ? 'bg-paper' : ''}`}
                        >
                          <span className="w-5 h-5 shrink-0 rounded-md bg-navy text-white text-[10px] font-extrabold flex items-center justify-center">P</span>
                          <div className="min-w-0 flex-1">
                            <div className="font-semibold truncate">{lot.name}</div>
                            <div className="text-[11px] text-muted">
                              {lot.kind === 'structure' ? 'Parking structure' : 'Surface lot'} · show on map
                            </div>
                          </div>
                        </li>
                      );
                    }
                    const { destination, matchedOn } = option;
                    const isCurrent = destination.id === formData.destinationId;
                    return (
                      <li
                        key={destination.id}
                        id={`destination-option-${index}`}
                        data-index={index}
                        role="option"
                        aria-selected={isActive}
                        onClick={() => chooseOption(option)}
                        onMouseMove={() => setActiveIndex(index)}
                        className={`px-3 py-2 rounded-lg cursor-pointer flex items-center gap-2.5 text-xs ${
                          isCurrent ? 'text-navy' : 'text-ink'
                        } ${isActive ? 'bg-paper' : ''}`}
                      >
                        <button
                          type="button"
                          aria-pressed={favorites.includes(destination.id)}
                          aria-label={
                            favorites.includes(destination.id)
                              ? `Remove ${destination.name} from favorites`
                              : `Add ${destination.name} to favorites`
                          }
                          title={favorites.includes(destination.id) ? 'Remove from favorites' : 'Add to favorites'}
                          // Keep focus in the search box and do not pick the place
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={(e) => {
                            e.stopPropagation();
                            setFavorites(toggleFavorite(destination.id));
                          }}
                          className="shrink-0 -ml-1 p-1 rounded-md hover:bg-line cursor-pointer"
                        >
                          <Star
                            className={`w-3.5 h-3.5 ${
                              favorites.includes(destination.id) ? 'fill-amber-400 text-amber-500' : 'text-muted'
                            }`}
                            aria-hidden="true"
                          />
                        </button>
                        <div className="min-w-0 flex-1">
                          <div className="font-semibold truncate">{destination.name}</div>
                          {matchedOn && !destination.codes?.includes(matchedOn) && (
                            <div className="text-[11px] text-muted truncate">Also called {matchedOn}</div>
                          )}
                        </div>
                        {destination.codes?.[0] && (
                          <span
                            className={`shrink-0 px-1.5 py-0.5 rounded-md text-[10px] font-bold tracking-wide ${
                              matchedOn && destination.codes.includes(matchedOn)
                                ? 'bg-navy text-white'
                                : 'bg-paper text-muted'
                            }`}
                          >
                            {matchedOn && destination.codes.includes(matchedOn) ? matchedOn : destination.codes[0]}
                          </span>
                        )}
                        {isCurrent && <Check className="w-3.5 h-3.5 shrink-0 text-navy" />}
                      </li>
                    );
                  })}
                </React.Fragment>
              ))}
              {flatOptions.length === 0 && (
                <li className="px-3 py-3 text-xs text-muted text-center">
                  No matches. Tip: use Drop pin on the map to pick any spot.
                </li>
              )}
            </ul>
            {!query && (
              <p className="px-3 pt-1.5 pb-0.5 text-[11px] text-muted border-t border-line mt-1">
                Tap the star to save a place. Not listed? Use Drop pin on the map.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Arrival Date and Time Grid */}
      <div className="grid grid-cols-2 gap-2.5">
        <div>
          <label
            htmlFor="arrival-date"
            className="block text-[13px] font-semibold text-ink mb-1.5"
          >
            Arrival date
          </label>
          <div className="relative">
            <input
              id="arrival-date"
              type="date"
              max={maxArrivalDate()}
              value={formData.arrivalDate}
              onChange={(e) => onChange({ arrivalDate: e.target.value })}
              aria-invalid={arrivalError !== null}
              aria-describedby={arrivalError ? 'arrival-error' : undefined}
              className="w-full px-2.5 py-2 rounded-[10px] bg-white border border-line text-[13px] font-medium text-navy focus:outline-none focus:ring-2 focus:ring-sky/30 focus:border-sky "
            />
          </div>
        </div>

        <div>
          <label
            htmlFor="arrival-time"
            className="block text-[13px] font-semibold text-ink mb-1.5"
          >
            Arrival time
          </label>
          <div className="relative">
            <input
              id="arrival-time"
              type="time"
              value={formData.arrivalTime}
              onChange={(e) => onChange({ arrivalTime: e.target.value })}
              aria-invalid={arrivalError !== null}
              aria-describedby={arrivalError ? 'arrival-error' : undefined}
              className="w-full px-2.5 py-2 rounded-[10px] bg-white border border-line text-[13px] font-medium text-navy focus:outline-none focus:ring-2 focus:ring-sky/30 focus:border-sky "
            />
          </div>
        </div>
      </div>

      {/* Arrival validation: empty or past date/time */}
      {arrivalError && (
        <div
          id="arrival-error"
          role="alert"
          className="-mt-2 flex items-center justify-between gap-2 px-3 py-2 rounded-xl bg-[#C0392B]/10 text-[12px] text-[#A12116] font-medium"
        >
          <span>{arrivalError}</span>
          <button
            type="button"
            onClick={onSetArrivalNow}
            className="shrink-0 px-2 py-0.5 rounded-md bg-white text-navy font-semibold hover:bg-white cursor-pointer"
          >
            Use now
          </button>
        </div>
      )}

      {/* Permit Type Pill Selector */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label className="block text-[13px] font-semibold text-ink">
            Permit type
          </label>
          <span className="text-[11px] text-muted">
            {PERMIT_OPTIONS.find((p) => p.type === formData.permitType)?.description}
          </span>
        </div>
        <div
          role="radiogroup"
          aria-label="Permit type"
          className="grid grid-cols-6 gap-0.5 p-0.5 bg-paper border border-line rounded-[10px]"
        >
          {PERMIT_OPTIONS.map((permit) => {
            const isSelected = formData.permitType === permit.type;
            return (
              <button
                key={permit.type}
                type="button"
                role="radio"
                aria-checked={isSelected}
                title={`${permit.type}: ${permit.description}`}
                onClick={() => onChange({ permitType: permit.type })}
                className={`relative py-1.5 text-xs font-semibold rounded-[10px] transition-colors duration-200 text-center focus:outline-none focus-visible:ring-2 focus-visible:ring-sky/40 cursor-pointer ${
                  isSelected ? 'text-white' : 'text-muted hover:text-navy'
                }`}
              >
                {/* Shared layoutId makes the white thumb slide between options */}
                {isSelected && (
                  <motion.span
                    layoutId="permit-thumb"
                    className="absolute inset-0 rounded-[8px] bg-navy"
                    transition={{ type: 'spring', stiffness: 500, damping: 35 }}
                  />
                )}
                <span className="relative">{permit.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Primary Action Button */}
      <button
        type="submit"
        disabled={isLoading || arrivalError !== null || !selectedDestination}
        className="w-full py-2.5 px-4 rounded-[10px] font-semibold text-[15px] text-white bg-navy hover:bg-navy-2 border-b-[3px] border-gold active:translate-y-px focus:outline-none focus-visible:ring-2 focus-visible:ring-sky/40 focus-visible:ring-offset-2 transition-all duration-150 shadow-[0_2px_6px_rgba(24,43,73,0.3)] disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:translate-y-0 flex items-center justify-center gap-2 cursor-pointer"
      >
        {isLoading ? (
          <>
            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            <span>Finding parking options...</span>
          </>
        ) : (
          <span>{selectedDestination ? submitLabel : 'Choose a destination'}</span>
        )}
      </button>
    </form>
  );
};
