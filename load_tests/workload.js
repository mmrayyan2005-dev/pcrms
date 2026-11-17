import http from 'k6/http';
import { check } from 'k6';

const BASE = __ENV.BASE_URL || 'http://localhost:8000';
const PROFILE = __ENV.PROFILE || 'smoke';
const PEAK = Number(__ENV.PEAK || 20);
const STEP = Number(__ENV.STEP_SECONDS || 60);

function rand(a, b) {
  return Math.floor(Math.random() * (b - a + 1)) + a;
}

// Fractions of PEAK requests/second, one value per STEP seconds.
const SHAPES = {
  wave:   [0.2, 0.3, 0.5, 0.8, 1.0, 0.8, 0.5, 0.3, 0.2, 0.2, 0.6, 1.0, 0.4, 0.2],
  spikes: [0.2, 0.2, 1.0, 0.2, 0.2, 0.2, 0.9, 0.3, 0.2, 1.0, 0.2, 0.2, 0.8, 0.2],
  ramp:   [0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.0, 0.6, 0.2],
  noisy:  [0.3, 0.6, 0.4, 0.8, 0.5, 1.0, 0.7, 0.9, 0.4, 0.6, 0.3, 0.8, 0.5, 0.2],
};

function stagesFor(name) {
  return SHAPES[name].map((f) => ({
    duration: STEP + 's',
    target: Math.max(1, Math.round(PEAK * f)),
  }));
}

const scenarios = {
  smoke: {
    executor: 'constant-arrival-rate',
    rate: 5,
    timeUnit: '1s',
    duration: '20s',
    preAllocatedVUs: 10,
    maxVUs: 50,
  },
};
for (const name of Object.keys(SHAPES)) {
  scenarios[name] = {
    executor: 'ramping-arrival-rate',
    startRate: 1,
    timeUnit: '1s',
    stages: stagesFor(name),
    preAllocatedVUs: 20,
    maxVUs: 200,
  };
}

export const options = {
  scenarios: { [PROFILE]: scenarios[PROFILE] },
};

export default function () {
  const r = Math.random();
  let res;
  if (r < 0.4) {
    res = http.get(BASE + '/io?delay_ms=' + rand(20, 150));
  } else if (r < 0.75) {
    res = http.get(BASE + '/cpu?iterations=' + rand(50000, 200000));
  } else if (r < 0.9) {
    res = http.get(BASE + '/memory?mb=' + rand(5, 20) + '&hold_ms=' + rand(50, 300));
  } else {
    res = http.get(BASE + '/health');
  }
  check(res, { 'status is 200': (x) => x.status === 200 });
}
