/**
 * Shared static data: state/region config, location presets, hotlines,
 * emergency tips, and tier descriptions. Bounds match backend STATE_BOUNDS
 * in main.py so frontend/backend stay consistent.
 */

export const STATE_CONFIG = {
  CA: {
    id: 'CA', name: 'California',
    bounds: [[32.5, -124.5], [42.1, -114.1]],
    center: [37.0, -119.5], zoom: 6,
  },
  NY: {
    id: 'NY', name: 'New York',
    bounds: [[40.4, -79.8], [45.1, -71.7]],
    center: [42.9, -75.5], zoom: 6,
  },
  NJ: {
    id: 'NJ', name: 'New Jersey',
    bounds: [[38.9, -75.6], [41.4, -73.9]],
    center: [40.1, -74.7], zoom: 8,
  },
};

export const REGION_ORDER = ['CA', 'NY', 'NJ'];

// Pill-level region config (Fix 3) — distinct from per-state STATE_CONFIG above,
// which is still used for sub-state focus (NJ/NY individually).
export const REGION_PILLS = {
  CA:   { id: 'CA',   label: 'California',            center: [36.7783, -119.4179], zoom: 6 },
  NJNY: { id: 'NJNY', label: 'New Jersey / New York',  center: [41.2033, -74.5894], zoom: 7 },
  ALL:  { id: 'ALL',  label: 'All Regions',            center: [39.5, -98.35],       zoom: 4 },
};

// Sub-state focus targets, shown only when NJNY pill is active (desktop only)
export const SUB_FOCUS = {
  NJ:   { center: [40.0583, -74.4057], zoom: 8 },
  NY:   { center: [42.9538, -75.5268], zoom: 7 },
  BOTH: { center: [41.2033, -74.5894], zoom: 7 },
};

// Maps internal pill values to backend `?region=` query param values
export const REGION_PARAM_MAP = { CA: 'california', NJNY: 'njny', ALL: 'all' };

// Location presets grouped by region (used in Origin/Dest pickers)
export const LA_PRESETS = [
  { label: 'LA Union Station',   lat: 34.0560, lng: -118.2356 },
  { label: 'Santa Monica Pier',  lat: 34.0100, lng: -118.4965 },
  { label: 'LAX Airport',        lat: 33.9425, lng: -118.4081 },
  { label: 'Pasadena City Hall', lat: 34.1478, lng: -118.1445 },
  { label: 'Dodger Stadium',     lat: 34.0739, lng: -118.2400 },
];
export const SF_PRESETS = [
  { label: 'SF Civic Center',    lat: 37.7793, lng: -122.4193 },
  { label: 'SFO Airport',        lat: 37.6213, lng: -122.3790 },
  { label: 'Oakland City Hall',  lat: 37.8044, lng: -122.2712 },
  { label: 'Berkeley UC',        lat: 37.8724, lng: -122.2595 },
  { label: 'Golden Gate Bridge', lat: 37.8199, lng: -122.4783 },
];
export const NJ_PRESETS = [
  { label: 'South Brunswick Twp',    lat: 40.3676, lng: -74.5311 },
  { label: 'Rutgers University',     lat: 40.5008, lng: -74.4474 },
  { label: 'Newark Airport',         lat: 40.6895, lng: -74.1745 },
  { label: 'Princeton University',   lat: 40.3431, lng: -74.6551 },
  { label: 'Hoboken Terminal',       lat: 40.7359, lng: -74.0244 },
  { label: 'New Brunswick Station',  lat: 40.4871, lng: -74.4430 },
  { label: 'Trenton City Hall',      lat: 40.2170, lng: -74.7429 },
  { label: 'Raritan River Gauge',    lat: 40.5676, lng: -74.5694 },
  { label: 'Atlantic City Conv Ctr', lat: 39.3643, lng: -74.4229 },
  { label: 'Meadowlands Stadium',    lat: 40.8135, lng: -74.0745 },
];
export const NY_PRESETS = [
  { label: 'NYC Penn Station',      lat: 40.7506, lng: -73.9971 },
  { label: 'JFK Airport',           lat: 40.6413, lng: -73.7781 },
  { label: 'LaGuardia Airport',     lat: 40.7769, lng: -73.8740 },
  { label: 'Brooklyn Bridge',       lat: 40.7061, lng: -73.9969 },
  { label: 'Yankee Stadium',        lat: 40.8296, lng: -73.9262 },
  { label: 'Albany City Hall',      lat: 42.6526, lng: -73.7562 },
  { label: 'Buffalo City Hall',     lat: 42.8864, lng: -78.8784 },
  { label: 'West Point Academy',    lat: 41.3915, lng: -73.9571 },
  { label: 'Syracuse Hancock Intl', lat: 43.1112, lng: -76.1063 },
  { label: 'Rochester Airport',     lat: 43.1189, lng: -77.6724 },
];

export const PRESET_GROUPS = [
  { region: 'CA', label: 'Los Angeles',  items: LA_PRESETS },
  { region: 'CA', label: 'San Francisco', items: SF_PRESETS },
  { region: 'NY', label: 'New York',     items: NY_PRESETS },
  { region: 'NJ', label: 'New Jersey',   items: NJ_PRESETS },
];

// Emergency hotlines / assistance numbers
export const HOTLINES = [
  { name: 'Emergency (Police / Fire / Medical)', number: '911', note: 'Immediate life-threatening emergencies' },
  { name: 'FEMA Disaster Assistance',     number: '1-800-621-3362', note: 'Federal disaster relief & registration' },
  { name: 'Red Cross Disaster Relief',    number: '1-800-733-2767', note: 'Shelter, supplies & emergency assistance' },
  { name: 'National Flood Insurance Program', number: '1-800-427-4661', note: 'Flood insurance claims & info' },
  { name: 'CAL FIRE Wildfire Info (CA)',  number: '1-800-468-8488', note: 'Wildfire reporting, California' },
  { name: 'NY State Emergency Management', number: '1-518-292-2200', note: 'New York disaster coordination' },
  { name: 'NJ Office of Emergency Management', number: '1-609-963-6900', note: 'New Jersey disaster coordination' },
  { name: 'Poison Control',               number: '1-800-222-1222', note: '24/7 poisoning emergencies' },
  { name: 'Disaster Distress Helpline',   number: '1-800-985-5990', note: 'Crisis counseling related to disasters (SAMHSA)' },
];

// Emergency guidance per hazard type
export const TIPS = [
  {
    key: 'flood', icon: '🌊', title: 'Flood',
    items: [
      'Move to higher ground immediately — do not wait for instructions.',
      'Never drive or walk through flood water; 6 inches can sweep a person off their feet, 12 inches can float a car.',
      'Avoid bridges over fast-moving water.',
      'If trapped in a building, go to the highest level — do not climb into a closed attic.',
      'After a flood, avoid floodwater — it may be contaminated or electrically charged.',
    ],
    link: 'https://www.ready.gov/floods',
  },
  {
    key: 'wildfire', icon: '🔥', title: 'Wildfire',
    items: [
      'Evacuate immediately if told to do so — do not wait to see the fire yourself.',
      'Close all windows/doors and remove flammable curtains if time permits before leaving.',
      'Keep a "go bag" ready with documents, medication, water, and a flashlight.',
      'If trapped, call 911 and give your location; stay low and away from outside walls.',
      'Watch air quality — wear an N95 mask if smoke is heavy, even far from the fire line.',
    ],
    link: 'https://www.ready.gov/wildfires',
  },
  {
    key: 'seismic', icon: '🌍', title: 'Earthquake',
    items: [
      'Drop, Cover, and Hold On — get under sturdy furniture or against an interior wall.',
      'Stay away from windows, mirrors, and tall furniture that can fall.',
      'If outdoors, move to an open area away from buildings, trees, and power lines.',
      'If driving, pull over away from overpasses/bridges and stay in the vehicle.',
      'After shaking stops, check for gas leaks and structural damage before re-entering buildings.',
    ],
    link: 'https://www.ready.gov/earthquakes',
  },
];

export const TIER_INFO = [
  {
    label: 'Driver',
    short: 'Simple route + safety status for everyday drivers.',
    full: 'Tier 1 — Driver: a simplified view showing your best route, plain-language safety status, and estimated time to safety. Designed for the general public during an evacuation or commute.',
  },
  {
    label: 'First Responder',
    short: 'All route options, hazard scores, and shelter/hospital locations.',
    full: 'Tier 2 — First Responder: shows all computed route alternatives with hazard scores, plus nearby shelters and hospitals. Designed for field personnel making real-time routing decisions.',
  },
  {
    label: 'Emergency Mgr',
    short: 'Full per-segment hazard data + economic impact analysis.',
    full: 'Tier 3 — Emergency Manager: full access to per-segment Multi-Hazard Risk Map data and the economic impact dashboard (infrastructure damage & loss estimates). Designed for coordination and resource-allocation decisions.',
  },
];
