import http    from 'k6/http';
import { sleep, check } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// ── Custom Metrics ────────────────────────────────────
const errorRate    = new Rate('errors');
const loginTime    = new Trend('login_duration');
const deployTime   = new Trend('deploy_duration');
const apiTime      = new Trend('api_duration');
const deployCount  = new Counter('deployments_triggered');

// ── Config ────────────────────────────────────────────
const BASE_URL = __ENV.BASE_URL || 'https://13.126.249.86.nip.io';

// ── Test Scenarios ────────────────────────────────────
export const options = {
  scenarios: {

    // Smoke test — just verify it works
    smoke: {
      executor: 'constant-vus',
      vus:      1,
      duration: '30s',
      tags:     { test_type: 'smoke' }
    },

    // Load test — normal traffic
    load: {
      executor:  'ramping-vus',
      startVUs:  0,
      stages: [
        { duration: '1m', target: 10 },  // ramp up
        { duration: '3m', target: 10 },  // hold
        { duration: '1m', target: 0  }   // ramp down
      ],
      tags: { test_type: 'load' }
    },

    // Stress test — find breaking point
    stress: {
      executor:  'ramping-vus',
      startVUs:  0,
      stages: [
        { duration: '2m', target: 20  },
        { duration: '5m', target: 20  },
        { duration: '2m', target: 50  },
        { duration: '5m', target: 50  },
        { duration: '2m', target: 100 },
        { duration: '5m', target: 100 },
        { duration: '2m', target: 0   }
      ],
      tags: { test_type: 'stress' }
    },

    // Spike test — sudden traffic surge
    spike: {
      executor:  'ramping-vus',
      startVUs:  0,
      stages: [
        { duration: '30s', target: 5   },
        { duration: '10s', target: 100 }, // spike!
        { duration: '1m',  target: 100 },
        { duration: '10s', target: 5   },
        { duration: '30s', target: 0   }
      ],
      tags: { test_type: 'spike' }
    }
  },

  // Thresholds
  thresholds: {
    'http_req_duration':       ['p(95)<2000'],  // 95% under 2s
    'http_req_duration{endpoint:health}':       ['p(99)<500'],
    'http_req_duration{endpoint:login}':        ['p(95)<3000'],
    'http_req_duration{endpoint:stats}':        ['p(95)<1000'],
    'errors':                  ['rate<0.05'],   // < 5% errors
    'http_req_failed':         ['rate<0.05']
  }
};

// ── Auth Helper ───────────────────────────────────────
function getToken() {
  const start = Date.now();
  const res   = http.post(
    `${BASE_URL}/auth/login`,
    'username=admin&password=admin123',
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
  );
  loginTime.add(Date.now() - start);

  check(res, { 'login 200': r => r.status === 200 });
  errorRate.add(res.status !== 200);

  try {
    return JSON.parse(res.body).access_token;
  } catch { return null; }
}

function authHeaders(token) {
  return {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type':  'application/json'
    }
  };
}

// ── Main Test ─────────────────────────────────────────
export default function() {
  const token = getToken();
  if (!token) { sleep(1); return; }

  const h = authHeaders(token);

  // 1. Health Check (most frequent)
  {
    const r = http.get(`${BASE_URL}/health`, { tags: { endpoint: 'health' } });
    check(r, { 'health 200': r => r.status === 200 });
    errorRate.add(r.status !== 200);
    sleep(0.2);
  }

  // 2. Stats
  {
    const start = Date.now();
    const r     = http.get(`${BASE_URL}/api/v1/stats`, { ...h, tags: { endpoint: 'stats' } });
    apiTime.add(Date.now() - start);
    check(r, { 'stats 200': r => r.status === 200 });
    errorRate.add(r.status !== 200);
    sleep(0.5);
  }

  // 3. History
  {
    const r = http.get(`${BASE_URL}/api/v1/history`, { ...h, tags: { endpoint: 'history' } });
    check(r, { 'history 200': r => r.status === 200 });
    errorRate.add(r.status !== 200);
    sleep(0.3);
  }

  // 4. Services
  {
    const r = http.get(`${BASE_URL}/api/v1/services`, { ...h, tags: { endpoint: 'services' } });
    check(r, { 'services 200': r => r.status === 200 });
    sleep(0.2);
  }

  // 5. Deploy (only 10% of requests — don't overload)
  if (Math.random() < 0.1) {
    const start = Date.now();
    const r     = http.post(
      `${BASE_URL}/api/v1/deploy`,
      JSON.stringify({
        repo_url:     'https://github.com/GoogleCloudPlatform/microservices-demo',
        service_name: 'emailservice',
        changes:      `Load test deploy ${Date.now()}`
      }),
      { ...h, tags: { endpoint: 'deploy' } }
    );
    deployTime.add(Date.now() - start);
    check(r, { 'deploy 200': r => r.status === 200 });
    errorRate.add(r.status !== 200);
    deployCount.add(1);
  }

  sleep(1);
}

// ── Summary ───────────────────────────────────────────
export function handleSummary(data) {
  const metrics    = data.metrics;
  const duration   = metrics.http_req_duration;
  const errors     = metrics.errors;
  const deploys    = metrics.deployments_triggered;

  console.log('\n📊 LOAD TEST RESULTS');
  console.log('═'.repeat(50));
  console.log(`✅ Total Requests:  ${metrics.http_reqs?.values?.count || 0}`);
  console.log(`⚡ Avg Response:    ${duration?.values?.avg?.toFixed(0) || 0}ms`);
  console.log(`📈 P95 Response:    ${duration?.values?.['p(95)']?.toFixed(0) || 0}ms`);
  console.log(`📈 P99 Response:    ${duration?.values?.['p(99)']?.toFixed(0) || 0}ms`);
  console.log(`❌ Error Rate:      ${((errors?.values?.rate || 0) * 100).toFixed(2)}%`);
  console.log(`🚀 Deployments:     ${deploys?.values?.count || 0}`);
  console.log('═'.repeat(50));

  return {
    'tests/load/results.json': JSON.stringify(data, null, 2)
  };
} 