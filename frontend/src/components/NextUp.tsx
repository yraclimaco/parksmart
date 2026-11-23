/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import parkSmartLogoHd from '../assets/parksmart-logo-hd.png';
import { useInView } from './LotParts';

/**
 * The closing screen: what ParkSmart does next. The flagship is a reminder built from the imported
 * schedule (UCSD Transportation's suggestion: schedule import plus notifications), shown as a mockup
 * that reuses the CSE 100 example from ClassPlanDemo. Nothing here is built yet; keep it to plans
 * the team has agreed on.
 */
const NEXT = [
  { name: 'iOS app', text: 'The same planner on your phone, with the reminders below.' },
  { name: '"Did you find a spot?"', text: 'One tap after you park, so forecasts get checked against real trips.' },
  { name: 'Real walking routes', text: 'Mapped paths instead of straight-line estimates.' },
] as const;

const LATER = [
  { name: 'Live counts', text: 'If UCSD shares a live source, shown with the time it was read.' },
  { name: 'Visitor prices', text: 'Daily pay rates beside visitor options.' },
  { name: 'Entrance photos and permit levels', text: 'See the entrance and which floors your permit can use.' },
] as const;

const RoadList: React.FC<{ title: string; items: readonly { name: string; text: string }[] }> = ({ title, items }) => (
  <div className="nu-col">
    <h3 className="nu-col-title">{title}</h3>
    <ul className="nu-list">
      {items.map((item) => (
        <li key={item.name}>
          <strong>{item.name}</strong> {item.text}
        </li>
      ))}
    </ul>
  </div>
);

export const NextUp: React.FC<{ heading: React.ReactNode }> = ({ heading }) => {
  const [ref, inView] = useInView<HTMLDivElement>();
  return (
    <div className="nu">
      <div className="nu-lead">
        {heading}
        <p className="nu-headline">Your schedule tells you when to leave.</p>
        <p className="nu-text">
          Import your classes once. Before each one, ParkSmart sends a reminder with when to leave, where to park, and a
          backup.
        </p>
        <div ref={ref} className={`nu-phone${inView ? ' nu-phone--in' : ''}`} role="img" aria-label="Mockup of a ParkSmart reminder: leave by 10:20 for CSE 100, park at Hopkins Parking Structure, backup Gilman">
          <div className="nu-note">
            <img src={parkSmartLogoHd} alt="" className="nu-note-icon" width={32} height={32} />
            <div className="nu-note-body">
              <p className="nu-note-top">
                <span>ParkSmart</span>
                <span>now</span>
              </p>
              <p className="nu-note-title">Leave by 10:20 for CSE 100</p>
              <p className="nu-note-text">Park at Hopkins Parking Structure, backup Gilman. Class at 11:00 in Center Hall.</p>
            </div>
          </div>
          <p className="nu-mock-label">Mockup. Not built yet.</p>
        </div>
      </div>
      <div className="nu-road">
        <RoadList title="Next" items={NEXT} />
        <RoadList title="Later" items={LATER} />
      </div>
    </div>
  );
};
