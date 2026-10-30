#!/usr/bin/env bash
# Investigator comparison on NVIDIA Nemotron via Nebius Token Factory.
# Needs NEBIUS_API_KEY, exported or in .env. Writes
# ledgerguard/evaluation/outputs/nemotron_comparison.{md,json} and nothing else.
set -euo pipefail
cd "$(dirname "$0")"

PY=.venv/bin/python
if [ ! -x "$PY" ]; then
  echo "Creating virtualenv..."
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi

if [ -z "${NEBIUS_API_KEY:-}" ] && ! grep -q '^NEBIUS_API_KEY=.' .env 2>/dev/null; then
  echo "NEBIUS_API_KEY is not set. Export it or add it to .env, then rerun." >&2
  exit 1
fi

# Reasoning tokens count against the 1200 token completion ceiling, so keep
# Nemotron's thinking short. Hosts that reject the parameter get it dropped.
export LEDGERGUARD_REASONING_EFFORT="${LEDGERGUARD_REASONING_EFFORT:-low}"

echo "Running the test suite..."
$PY -m pytest ledgerguard/tests -q

echo
$PY -m ledgerguard.evaluation.model_comparison --providers nebius --out nemotron_comparison

# A run where the host never answered still writes a table. Refuse to let that
# pass for a measurement.
$PY - <<'EOF'
import json, sys
row = json.load(open("ledgerguard/evaluation/outputs/nemotron_comparison.json"))["providers"][0]
print(f"investigator: {row['provider']}  unavailable: {row['unavailable']}  "
      f"invalid responses: {row['invalid_responses']}")
if row["unavailable"]:
    sys.exit("Some investigations never reached Nemotron. Do not publish these numbers; "
             "check the key, base URL and model id, then rerun.")
EOF
