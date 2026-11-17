SELF=$(readlink -f "$0")
cd ~/pcrms
mkdir -p data/raw scripts docs load_tests

echo "=========== PREPARE ==========="
minikube stop || true
docker start prometheus node-exporter > /dev/null 2>&1 || true
for i in $(seq 1 20); do curl -sf localhost:9090/-/ready > /dev/null && break; sleep 1; done
curl -sf localhost:9090/-/ready > /dev/null || { echo "PROMETHEUS NOT RUNNING - tell Claude"; exit 1; }
[ -f src/collector/export_metrics.py ] || { echo "export_metrics.py MISSING - tell Claude"; exit 1; }

cat > load_tests/workload.js << 'EOF'
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
EOF

PS=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
win() { $PS -NoProfile -Command "[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()" | tr -d '\r'; }

rm -f data/raw/runs_meta.csv
echo "run,profile,peak,start_wsl,end_wsl,elapsed_wsl_s,elapsed_win_s,elapsed_uptime_s" > data/raw/runs_meta.csv

run_one() {
  name=$1; profile=$2; peak=$3
  echo ""
  echo "=========== RUN $name (profile=$profile, peak=$peak) ==========="
  pkill -f "uvicorn app.main:app" 2>/dev/null
  sleep 2
  nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/uvicorn.log 2>&1 &
  for i in $(seq 1 20); do curl -sf localhost:8000/health > /dev/null && break; sleep 1; done
  curl -sf localhost:8000/health > /dev/null || { echo "APP FAILED TO START - tell Claude"; return 1; }

  W0=$(win); L0=$(date +%s); U0=$(awk '{print $1}' /proc/uptime)
  sleep 30
  k6 run -e PROFILE=$profile -e PEAK=$peak load_tests/workload.js 2>&1 \
    | grep -E "checks_failed|http_req_duration|http_req_failed|http_reqs|dropped|iterations" \
    | tee data/raw/k6_$name.log
  sleep 30
  W1=$(win); L1=$(date +%s); U1=$(awk '{print $1}' /proc/uptime)
  sleep 10

  .venv/bin/python src/collector/export_metrics.py --start $L0 --end $L1 --out data/raw/$name.csv | head -1
  echo "$name,$profile,$peak,$L0,$L1,$((L1-L0)),$((W1-W0)),$(awk -v a=$U1 -v b=$U0 'BEGIN{printf "%.1f", a-b}')" >> data/raw/runs_meta.csv
}

run_one wave_a wave 50
run_one spikes_a spikes 60
run_one ramp_a ramp 50
run_one noisy_a noisy 40
pkill -f "uvicorn app.main:app" 2>/dev/null

echo ""
echo "=========== QUALITY REPORT ==========="
.venv/bin/python - << 'EOF'
import pandas as pd

meta = pd.read_csv("data/raw/runs_meta.csv")
meta["timer_vs_real"] = (meta.elapsed_uptime_s / meta.elapsed_win_s).round(3)
meta["wallclock_vs_real"] = (meta.elapsed_wsl_s / meta.elapsed_win_s).round(3)
print(meta[["run", "elapsed_win_s", "elapsed_wsl_s", "elapsed_uptime_s", "timer_vs_real", "wallclock_vs_real"]].to_string(index=False))
print()
for _, r in meta.iterrows():
    df = pd.read_csv("data/raw/%s.csv" % r.run, parse_dates=["timestamp"], index_col="timestamp")
    act = df.req_rate > 0.5
    print(r.run, "| rows", len(df),
          "| active min", round(act.sum() * 5 / 60, 1),
          "| req_rate max", round(df.req_rate.max(), 1),
          "| p95 max", round(df.latency_p95_s.max(), 2),
          "| app_cpu mean(active)", round(df.app_cpu_cores[act].mean(), 3),
          "| node_cpu<0:", int((df.node_cpu_util < 0).sum()),
          "| app_cpu>1:", int((df.app_cpu_cores > 1).sum()))
EOF

echo ""
echo "=========== COMMIT ==========="
cp "$SELF" scripts/collect_runs.sh
cp data/raw/runs_meta.csv docs/runs_meta.csv
git add load_tests scripts docs
git commit -m "Add multi-profile workload and automated multi-run collection"
git push || echo "PUSH FAILED - tell Claude"
echo "=========== DONE ==========="