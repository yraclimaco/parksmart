/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { RECOMMENDATION_SOURCE } from '../config';
import parkSmartLogoHd from '../assets/parksmart-logo-hd.png';
import { HeroDemo } from './HeroDemo';
import { PermitLot } from './PermitLot';
import { ProblemLot } from './ProblemLot';
import { Pipeline } from './Pipeline';
import { ScoreMix } from './ScoreMix';
import { TimeLot } from './TimeLot';
import { LandingIntro } from './LandingIntro';
import { CarCursor } from './CarCursor';

/** The hosted build talks to the AWS backend; other builds (previews) use labeled sample data. */
const LIVE = RECOMMENDATION_SOURCE === 'api';

interface LandingPageProps {
  isExiting: boolean;
  onPlanClick: () => void;
}

const LIMITS = [
  {
    lead: 'Past counts, not live ones.',
    text: 'There is no live feed, so a lot can be full when the estimate says it is usually open.',
  },
  {
    lead: 'Mostly the first two weeks of each quarter.',
    text: 'The detailed counts cover little else, and the model has not been checked across all ten weeks.',
  },
  {
    lead: 'Simplified permit rules.',
    text: LIVE
      ? 'Ordinary stalls only. Reserved, accessible, and A 24/7 stalls are left out, options that need holiday verification are not shown, and only your arrival moment is checked.'
      : 'Ordinary stalls only. Reserved, accessible, and A 24/7 stalls are left out, holidays count as weekdays, and only your arrival moment is checked.',
  },
  {
    lead: 'The scoring mix is a starting point.',
    text: 'The 65/35 balance has not been tuned on user data and still needs review with experts.',
  },
  {
    lead: LIVE ? 'Historical estimates.' : 'Sample data in this preview.',
    text: LIVE
      ? 'Results come from past survey patterns through the hosted backend. Walk times are estimates for now.'
      : 'The numbers you see here are samples. The hosted app uses the real backend.',
  },
  {
    lead: 'No promises.',
    text: 'No reservations, no payments, and not an official UCSD service.',
  },
] as const;

const FAQ = [
  {
    q: 'Is this an official UCSD service?',
    a: 'No. ParkSmart is a student project and is not affiliated with UC San Diego.',
  },
  {
    q: 'Will it work with my permit?',
    a: 'You choose your permit type (A, B, S, SR, D, or V) and lots it cannot use are filtered out. Your permit letter is on your UCSD permit or in your parking account. Always check UCSD\'s permit pages for the final rules.',
  },
  {
    q: 'Can I use my class schedule?',
    a: 'Yes. Import your calendar (.ics) in the planner and it lists your classes. Tap one and ParkSmart sets your arrival 20 minutes before it starts and finds parking near that building. If it cannot tell the building, you pick one. The file stays on your device.',
  },
  {
    q: 'Is the data live?',
    a: 'No. Estimates come from past parking counts, not a live feed.',
  },
  {
    q: 'Will it guarantee me a space?',
    a: 'No. It shows where you are most likely to find one, based on typical patterns. Lots can still be full.',
  },
  {
    q: 'Does it cost anything?',
    a: 'There is nothing to buy and nothing to sign up for.',
  },
  {
    q: 'Does it work for visitors?',
    a: 'Partly. You can pick V (Visitor / Daily Pay) and see where visitors may park, but prices and pay-station rules are not covered. Visitor estimates are also less reliable: in our tests they ran about 24 points too optimistic when lots were nearly full. Check UCSD\'s visitor parking page before you go.',
  },
] as const;

/** The intro plays once per browser session, not on every reload or return from the planner. */
const INTRO_SEEN_KEY = 'parksmart:intro-seen';
let introPlayedThisLoad = false;

const shouldPlayIntro = (): boolean => {
  if (introPlayedThisLoad) return false;
  introPlayedThisLoad = true;
  try {
    if (window.sessionStorage.getItem(INTRO_SEEN_KEY)) return false;
  } catch {
    /* storage blocked: fall through and play once per load */
  }
  try {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
  } catch {
    /* no matchMedia: play it */
  }
  try {
    window.sessionStorage.setItem(INTRO_SEEN_KEY, '1');
  } catch {
    /* ignore */
  }
  return true;
};

/** Public links for judges and teammates. All verified targets in this repo's docs. */
const LINKS = [
  { label: 'GitHub', href: 'https://github.com/yraclimaco/parksmart' },
  { label: 'Design doc', href: 'https://github.com/yraclimaco/parksmart/blob/main/docs/DesignDoc.md' },
  { label: 'UCSD QPASS surveys', href: 'https://rmp-wapps.ucsd.edu/TS/Survey/QPASS/Contents.html' },
  { label: 'Imagery: USGS NAIP', href: 'https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer' },
  { label: 'Map: OpenFreeMap, OpenStreetMap', href: 'https://openfreemap.org/' },
] as const;

/** Facts from ParkSmart's own dataset notes (docs/issue11_findings.md, docs/issue18_predictions.md). */
const PROBLEM_FACTS = [
  {
    lead: 'UCSD publishes survey counts, not a live feed.',
    text: 'UCSD Transportation posts QPASS survey workbooks after each quarter. Nothing tells you what is open right now.',
  },
  {
    lead: 'The detailed counts are early-quarter snapshots.',
    text: 'Surveys mostly cover the first weeks of a quarter, and several years and quarters are missing from the public archive.',
  },
  {
    lead: 'ParkSmart turns 76,102 survey readings into a forecast.',
    text: 'They span 86 facilities, from June 2018 to October 2026. Forecasts are typical conditions, not today\'s.',
  },
] as const;

const NEXT_ITEMS = [
  { name: 'Hosted planner and backend', status: LIVE ? 'Live' : 'Live in the hosted app', text: 'Historical estimates on AWS. Walk times are estimates for now.' },
  { name: 'Trip alerts', status: 'In progress', text: 'Weather comes from the Open-Meteo hourly forecast. Construction comes from UCSD\'s public construction map layers, matched within 200 m of your trip. Both are shown as notes only: they never exclude a lot or change its score.' },
  { name: 'Mobile app', status: 'Planned', text: 'The same planner as an iOS app.' },
  { name: 'Live lot counts', status: 'Planned', text: 'Only if a validated source exists, always shown with its retrieval time.' },
] as const;

const SCREEN_COUNT = 9;

/** Header links. `screens` are the data-screen numbers that highlight each link. */
const NAV = [
  { id: 'permit', label: 'Demo', screens: [3, 4] },
  { id: 'how', label: 'How it works', screens: [5, 6] },
  { id: 'evidence', label: 'Evidence', screens: [7] },
  { id: 'limits', label: 'Limits & FAQ', screens: [8] },
  { id: 'next', label: 'What\'s next', screens: [9] },
] as const;

/** Why the scores look the way they do (docs/recommendations.md in the backend repo). */
const SCORE_NOTES = [
  {
    lead: 'Why 65/35.',
    text: 'It is a product choice carried over from the first prototype, not tuned on user data. Experts still need to review it.',
  },
  {
    lead: 'One mix for every search.',
    text: 'There is no walk-or-space switch, so everyone gets the same balance. Expected availability counts about twice as much as the walk, and a lot that is close but usually full can still lose to one a bit farther that is usually open.',
  },
  {
    lead: 'Before scoring, lots are filtered.',
    text: 'Lots your permit cannot use, and lots more than a 20-minute walk from your destination, never reach the ranking.',
  },
  {
    lead: 'Weather and construction do not change the score.',
    text: 'They show as a collapsed line on your result instead.',
  },
] as const;
const TOP_LIMITS = 3;
/** The first FAQ answers start open so the page answers the obvious questions without a click. */
const FAQ_OPEN = 3;

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
              <p className="lp-lede">Tell it your trip. Get a first choice and a backup.</p>
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
              <p className="lp-fineprint">{LIVE ? 'UCSD student prototype. Uses historical survey estimates, not live data.' : 'UCSD student prototype. This preview runs on sample data.'}</p>
            </div>
            <div className="lp-hero2-demo">{!introActive && <HeroDemo />}</div>
          </div>
        </section>

        <section id="problem" data-screen="2" className="lp-block lp-block--paper" aria-labelledby="problem-heading">
          <div className="lp-container lp-faq">
            <div className="lp-problem-lead">
              <h2 id="problem-heading" className="lp-big lp-big--navy">
                Nobody tells you what is open.
              </h2>
              <ProblemLot />
              <p className="lp-note">Illustration. Stalls marked ? are the ones nothing can tell you about.</p>
            </div>
            <ul className="lp-fact-list">
              {PROBLEM_FACTS.map((item) => (
                <li key={item.lead}>
                  <strong>{item.lead}</strong> {item.text}
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="permit" data-screen="3" className="lp-block lp-block--yellow" aria-labelledby="permit-heading">
          <div className="lp-container lp-split">
            <div className="lp-split-head">
              <h2 id="permit-heading" className="lp-big">
                Your permit decides the map.
              </h2>
              <p className="lp-sub">Pick yours. Everything you can&apos;t use fades out.</p>
              <p className="lp-permit-help">
                Not sure which one you have? The letter is printed on your UCSD permit and listed in your parking account.
              </p>
            </div>
            <PermitLot />
            <p className="lp-note lp-split-note">Simplified example lot. Real rules live on UCSD&apos;s permit pages.</p>
          </div>
        </section>

        <section data-screen="4" className="lp-block lp-block--blue lp-dark" aria-labelledby="time-heading">
          <div className="lp-container lp-split">
            <div className="lp-split-head">
              <h2 id="time-heading" className="lp-big">
                Drag the clock.
              </h2>
              <p className="lp-sub">Watch a busy lot fill up through the day.</p>
            </div>
            <TimeLot />
            <p className="lp-note lp-split-note">Example pattern, not real UCSD data.</p>
          </div>
        </section>

        <section id="how" data-screen="5" className="lp-block lp-block--hood lp-dark" aria-labelledby="hood-heading">
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

        <section id="scoring" data-screen="6" className="lp-block lp-block--navy lp-dark" aria-labelledby="score-heading">
          <div className="lp-container lp-faq">
            <div>
              <h2 id="score-heading" className="lp-big">
                How a pick is chosen.
              </h2>
              <div className="lp-mix">
                <ScoreMix />
              </div>
            </div>
            <ul className="lp-score-list">
              {SCORE_NOTES.map((item) => (
                <li key={item.lead}>
                  <strong>{item.lead}</strong> {item.text}
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="evidence" data-screen="7" className="lp-block lp-block--blue lp-dark" aria-labelledby="evidence-heading">
          <div className="lp-container lp-faq">
            <h2 id="evidence-heading" className="lp-big">
              Checked against what happened.
            </h2>
            <div className="lp-evidence">
              <p className="lp-evidence-num">
                21 <span>points off, on average</span>
              </p>
              <p className="lp-evidence-text">
                On 11,665 held-out survey readings from the newest dates, the forecast missed the actual open
                share by 21.0 percentage points on average (MAE). When a lot was nearly full, the miss was 13.7 points.
                Another 4,458 held-out readings had no usable history, so ParkSmart shows no estimate for those
                instead of a guess. Scores come from ParkSmart&apos;s own test split; expert review is still planned.
              </p>
            </div>
          </div>
        </section>

        <section id="limits" data-screen="8" className="lp-block lp-block--caution" aria-labelledby="limits-heading">
          <div className="lp-stripe" aria-hidden="true" />
          <div className="lp-container lp-limits">
            <div>
              <h2 id="limits-heading" className="lp-big lp-big--navy">
                A forecast, not a promise.
              </h2>
              <ul className="lp-limit-list">
                {LIMITS.slice(0, TOP_LIMITS).map((item) => (
                  <li key={item.lead}>
                    <strong>{item.lead}</strong> {item.text}
                  </li>
                ))}
              </ul>
              <details className="lp-more">
                <summary>More limits</summary>
                <ul className="lp-limit-list">
                  {LIMITS.slice(TOP_LIMITS).map((item) => (
                    <li key={item.lead}>
                      <strong>{item.lead}</strong> {item.text}
                    </li>
                  ))}
                </ul>
              </details>
            </div>
            <div className="lp-faq-list" aria-label="Quick answers">
              {FAQ.map((item, i) => (
                <details key={item.q} className="lp-faq-item" open={i < FAQ_OPEN || undefined}>
                  <summary>{item.q}</summary>
                  <p>{item.a}</p>
                </details>
              ))}
            </div>
          </div>
          <div className="lp-stripe" aria-hidden="true" />
        </section>

        <section id="next" data-screen="9" className="lp-block lp-block--yellow" aria-labelledby="next-heading">
          <div className="lp-container lp-faq">
            <h2 id="next-heading" className="lp-big">
              What is next.
            </h2>
            <ul className="lp-next-list">
              {NEXT_ITEMS.map((item) => (
                <li key={item.name}>
                  <span className="lp-status">{item.status}</span>
                  <strong>{item.name}</strong> {item.text}
                </li>
              ))}
            </ul>
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

      {!introActive && (
        <p className="lp-counter" aria-label={`Screen ${screen} of ${SCREEN_COUNT}`}>
          {screen} of {SCREEN_COUNT}
        </p>
      )}

    </div>
  );
};
