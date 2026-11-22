/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Check, X } from 'lucide-react';
import parkSmartLogoHd from '../assets/parksmart-logo-hd.png';
import { AlertsDemo } from './AlertsDemo';
import { EvidenceTest } from './EvidenceTest';
import { NextUp } from './NextUp';
import { ClassPlanDemo } from './ClassPlanDemo';
import { HeroDemo } from './HeroDemo';
import { PermitMap } from './PermitMap';
import { WhyFunnel } from './WhyFunnel';
import { Pipeline } from './Pipeline';
import { ScoreMix } from './ScoreMix';
import { LandingIntro } from './LandingIntro';
import { CarCursor } from './CarCursor';

interface LandingPageProps {
  isExiting: boolean;
  onPlanClick: () => void;
}

/**
 * The coverage screen: what ParkSmart does and what it does not do yet, without repeating other
 * sections. Sources: docs/recommendations.md (permits, special stalls, arrival-only checks),
 * docs/issue27_additional_data.md (visitor near-full overestimate), docs/routing.md (walk times).
 */
const COVERS = [
  { lead: 'Every main permit:', text: 'A, B, S, SR, D, and V (visitor)' },
  { lead: 'Your class schedule,', text: 'imported from a calendar (.ics) file' },
  { lead: '46 campus lots and structures', text: 'with UCSD survey history' },
  { lead: 'Weather and construction', text: 'notes for your trip' },
  { lead: 'A first choice and a backup', text: 'for every search' },
  { lead: 'Free.', text: 'No account, no sign-up' },
] as const;

const NOT_COVERED = [
  { lead: 'Live counts.', text: 'Forecasts come from past surveys' },
  { lead: 'Events and posted closures', text: '' },
  { lead: 'Special permits and stalls:', text: 'SuperSaver, carpool, accessible, EV, reserved' },
  { lead: 'Visitor prices and pay stations.', text: 'Visitor forecasts run optimistic when lots are nearly full' },
  { lead: 'Real walking routes.', text: 'Walk times are straight-line estimates' },
  { lead: 'Missing survey years.', text: 'Some years and quarters are missing from UCSD\'s archive' },
  { lead: 'How long you stay.', text: 'Only your arrival time is checked' },
] as const;

/**
 * The intro plays on every page load, so every visit starts there. It does not replay when someone
 * comes back to the landing page from the planner (Home), or when they prefer reduced motion.
 */
let introPlayedThisLoad = false;

const shouldPlayIntro = (): boolean => {
  if (introPlayedThisLoad) return false;
  introPlayedThisLoad = true;
  try {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
  } catch {
    /* no matchMedia: play it */
  }
  return true;
};

/** Public links for judges and teammates. All verified targets in this repo's docs. */
const LINKS = [
  { label: 'GitHub', href: 'https://github.com/yraclimaco/parksmart' },
  { label: 'Design doc', href: 'https://lucid.app/lucidchart/326e969e-634e-4050-8e27-3d232a43aae4/view' },
  { label: 'UCSD QPASS surveys', href: 'https://rmp-wapps.ucsd.edu/TS/Survey/QPASS/Contents.html' },
  { label: 'Imagery: USGS NAIP', href: 'https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer' },
  { label: 'Map: OpenFreeMap, OpenStreetMap', href: 'https://openfreemap.org/' },
] as const;



/** Header links. `screens` are the data-screen numbers that highlight each link. */
const NAV = [
  { id: 'classes', label: 'Classes', screens: [3] },
  { id: 'permit', label: 'Permit', screens: [4] },
  { id: 'alerts', label: 'Alerts', screens: [5] },
  { id: 'how', label: 'How it works', screens: [6, 7] },
  { id: 'evidence', label: 'Accuracy', screens: [8] },
  { id: 'limits', label: 'Coverage', screens: [9] },
  { id: 'next', label: 'What\'s next', screens: [10] },
] as const;

/**
 * How a pick is chosen, in the order the backend does it (docs/recommendations.md and
 * src/ranking.py in the backend repo). Keep in step with those when the rules change.
 */
const SCORE_STEPS = [
  {
    lead: 'Filter.',
    text: 'Only lots your permit allows at your arrival time make it through. Rules ParkSmart cannot confirm, like D stalls, reserved stalls, or holiday hours, count as not allowed. Lots over a 20-minute walk from your building, or with no survey history for that time, are skipped, never guessed.',
  },
  {
    lead: 'Score: 65% space, 35% walk.',
    text: 'Parking experts advised favoring the lot more likely to have space, so the share of spots open in past surveys counts 65%. The walk counts 35%: right next door earns full marks, 20 minutes earns none. A close lot that is usually full can lose to one a bit farther that is usually open.',
  },
  {
    lead: 'Pick two.',
    text: 'The top lot is your first choice. Your backup is the best different lot, so if the first one is full you are not sent back to the same place.',
  },
  {
    lead: 'Add notes, not points.',
    text: 'Weather at your arrival time and UCSD construction near your trip show under the result. They never change a score or hide a lot.',
  },
] as const;

export const LandingPage: React.FC<LandingPageProps> = ({ isExiting, onPlanClick }) => {
  const [introActive, setIntroActive] = React.useState(shouldPlayIntro);
  const [screen, setScreen] = React.useState(1);
  const docRef = React.useRef<HTMLDivElement | null>(null);
  React.useEffect(() => {
    const root = docRef.current;
    if (!root || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) setScreen(Number((e.target as HTMLElement).dataset.screen));
        });
      },
      { rootMargin: '-45% 0px -50% 0px' },
    );
    root.querySelectorAll('[data-screen]').forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
  const goTo = (id: string) => (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    const target = document.getElementById(id);
    if (!target) return;
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    target.scrollIntoView({ behavior: prefersReduced ? 'auto' : 'smooth', block: 'start' });
  };

  return (
    <div
      className={`ps-landing${isExiting ? ' ps-landing--exiting' : ''}${introActive ? ' ps-landing--intro' : ''}`}
    >
      <CarCursor />
      {introActive && <LandingIntro onDone={() => setIntroActive(false)} />}

      {!introActive && (
        <header className="lp-nav">
          <div className="lp-container lp-nav-inner">
            <a href="#top" className="lp-wordmark" onClick={goTo('top')} aria-label="ParkSmart, back to top">
              <img src={parkSmartLogoHd} alt="ParkSmart logo" className="lp-wordmark-logo" width={36} height={36} />
              ParkSmart
            </a>
            <nav className="lp-nav-links" aria-label="Sections">
              {NAV.map((item) => (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  onClick={goTo(item.id)}
                  aria-current={(item.screens as readonly number[]).includes(screen) ? 'location' : undefined}
                >
                  {item.label}
                </a>
              ))}
            </nav>
            <button type="button" className="lp-btn lp-btn--yellow lp-nav-cta" onClick={onPlanClick}>
              Plan my parking
            </button>
          </div>
        </header>
      )}

      <div className="lp-doc" id="top" ref={docRef}>
        <section data-screen="1" className="lp-hero2 lp-dark" aria-label="ParkSmart introduction">
          <div className="lp-container lp-hero2-grid">
            <div className="lp-hero2-copy">
              <h1 className="lp-h1">Know where to park before you get to campus.</h1>
              <p className="lp-lede">
                ParkSmart plans UCSD parking around your class schedule: your permit, a first choice and a backup, and weather and construction alerts.
              </p>
              <div className="lp-top-actions">
                <button type="button" className="lp-btn lp-btn--yellow" onClick={onPlanClick}>
                  Plan my parking
                </button>
                <a href="#permit" className="lp-textlink" onClick={goTo('permit')}>
                  See how it thinks
                </a>
              </div>
              <div className="lp-result" role="group" aria-label="Example result">
                <p className="lp-result-tag">Example result</p>
                <p className="lp-result-main">
                  <strong>Lot P503</strong> · 5 min walk · usually open
                </p>
                <p className="lp-result-backup">Backup: Lot P510</p>
              </div>
              <p className="lp-fineprint">UCSD student prototype. Uses historical survey estimates, not live data.</p>
            </div>
            <div className="lp-hero2-demo">{!introActive && <HeroDemo />}</div>
          </div>
        </section>

        <section id="problem" data-screen="2" className="lp-block lp-block--paper" aria-labelledby="problem-heading">
          <div className="lp-container lp-faq">
            <div className="lp-problem-lead">
              <h2 id="problem-heading" className="lp-big lp-big--navy">
                Why ParkSmart.
              </h2>
              <p className="lp-sub">
                Other apps show you every spot on campus. ParkSmart narrows it down to the one that fits your day.
              </p>
              <button type="button" className="lp-btn lp-btn--yellow lp-why-cta" onClick={onPlanClick}>
                Plan my parking
              </button>
            </div>
            <WhyFunnel />
          </div>
        </section>

        <section id="classes" data-screen="3" className="lp-block lp-block--navy lp-dark" aria-labelledby="classes-heading">
          <div className="lp-container lp-split">
            <div className="lp-split-head">
              <h2 id="classes-heading" className="lp-big">
                Import your classes.
              </h2>
              <p className="lp-sub">One import covers your whole quarter. No typing in every trip.</p>
              <ol className="cp-steps">
                <li>
                  <span>
                    <strong>Export your calendar</strong> as an .ics file.
                  </span>
                </li>
                <li>
                  <span>
                    <strong>Import it once.</strong> ParkSmart reads each room code, like CENTR 115, and finds the building.
                  </span>
                </li>
                <li>
                  <span>
                    <strong>Tap a class.</strong> You get a first choice and a backup, with arrival set 20 minutes early.
                  </span>
                </li>
              </ol>
              <p className="lp-permit-help">
                Google Calendar: Settings, Import &amp; export, Export. Apple Calendar: File, Export. The file stays on your
                device.
              </p>
            </div>
            <ClassPlanDemo />
            <p className="lp-note lp-split-note">Example classes and lots, not real UCSD data. Room matching and the 20-minute lead are what the planner uses.</p>
          </div>
        </section>

        <section id="permit" data-screen="4" className="lp-block lp-block--yellow" aria-labelledby="permit-heading">
          <div className="lp-container lp-split">
            <div className="lp-split-head">
              <h2 id="permit-heading" className="lp-big">
                Your permit decides the map.
              </h2>
              <p className="lp-sub">Pick your permit and when you arrive. Lots you can&apos;t use fade out.</p>
              <p className="lp-permit-help">
                The rules change with the clock: an S permit also gets A and B lots after 4 PM and on weekends. ParkSmart
                checks them for your arrival time.
              </p>
              <p className="lp-permit-help">
                <strong>Set it once.</strong> ParkSmart remembers your permit. The letter is on your UCSD permit and in your
                parking account.
              </p>
              <p className="lp-note">Example map with made-up lots. The permit rules are the ones ParkSmart uses.</p>
            </div>
            <PermitMap />
          </div>
        </section>

        <section id="alerts" data-screen="5" className="lp-block lp-block--paper" aria-labelledby="alerts-heading">
          <div className="lp-container lp-split">
            <div className="lp-split-head">
              <h2 id="alerts-heading" className="lp-big lp-big--navy">
                Weather and construction, built in.
              </h2>
              <p className="lp-sub">Every result shows the forecast for your arrival time and UCSD construction notices near your trip.</p>
            </div>
            <AlertsDemo />
            <p className="lp-note lp-split-note">
              Example values. Weather comes from Open-Meteo, construction from UCSD&apos;s public construction map.
            </p>
          </div>
        </section>

        <section id="how" data-screen="6" className="lp-block lp-block--hood lp-dark" aria-labelledby="hood-heading">
          <div className="lp-container">
            <div className="lp-block-head">
              <h2 id="hood-heading" className="lp-big">
                How it works.
              </h2>
              <p className="lp-sub">Each stage: what it does, why, and how far along it is.</p>
            </div>
            <Pipeline />
          </div>
        </section>

        <section id="scoring" data-screen="7" className="lp-block lp-block--navy lp-dark" aria-labelledby="score-heading">
          <div className="lp-container lp-faq">
            <div>
              <h2 id="score-heading" className="lp-big">
                How a pick is chosen.
              </h2>
              <div className="lp-mix">
                <ScoreMix />
              </div>
            </div>
            <ol className="lp-score-list lp-score-list--steps">
              {SCORE_STEPS.map((item) => (
                <li key={item.lead}>
                  <strong>{item.lead}</strong> {item.text}
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="evidence" data-screen="8" className="lp-block lp-block--blue lp-dark" aria-labelledby="evidence-heading">
          <div className="lp-container">
            <EvidenceTest
              heading={
                <h2 id="evidence-heading" className="lp-big">
                  How accurate is it?
                </h2>
              }
            />
          </div>
        </section>

        <section id="limits" data-screen="9" className="lp-block lp-block--caution" aria-labelledby="limits-heading">
          <div className="lp-stripe" aria-hidden="true" />
          <div className="lp-container lp-cover">
            <h2 id="limits-heading" className="lp-big lp-big--navy lp-cover-title">
              What it covers, and what it doesn&apos;t.
            </h2>
            <div className="lp-cover-col">
              <h3 className="lp-cover-head">
                <Check aria-hidden="true" /> Covers
              </h3>
              <ul className="lp-cover-list">
                {COVERS.map((item) => (
                  <li key={item.lead}>
                    <strong>{item.lead}</strong> {item.text}
                  </li>
                ))}
              </ul>
            </div>
            <div className="lp-cover-col">
              <h3 className="lp-cover-head">
                <X aria-hidden="true" /> Doesn&apos;t cover yet
              </h3>
              <ul className="lp-cover-list">
                {NOT_COVERED.map((item) => (
                  <li key={item.lead}>
                    <strong>{item.lead}</strong> {item.text}
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div className="lp-stripe" aria-hidden="true" />
        </section>

        <section id="next" data-screen="10" className="lp-block lp-block--navy lp-dark" aria-labelledby="next-heading">
          <div className="lp-container">
            <NextUp
              heading={
                <h2 id="next-heading" className="lp-big">
                  What&apos;s next.
                </h2>
              }
            />
          </div>
        </section>

        <footer className="lp-footer lp-dark">
          <div className="lp-container lp-footer-inner">
            <div>
              <p className="lp-footer-text">
                Team lead: Yra. Built by Vivaan, Hanrong, Dylan, and Daira for UCSD DS3, Fall 2026.
              </p>
              <p className="lp-footer-text lp-footer-text--note">A student project, not an official UCSD service.</p>
              <nav className="lp-footer-links" aria-label="Project links and sources">
                {LINKS.map((l) => (
                  <a key={l.href} href={l.href} target="_blank" rel="noopener noreferrer">
                    {l.label}
                  </a>
                ))}
              </nav>
            </div>
            <button type="button" className="lp-btn lp-btn--yellow" onClick={onPlanClick}>
              Plan my parking
            </button>
          </div>
        </footer>
      </div>

    </div>
  );
};
