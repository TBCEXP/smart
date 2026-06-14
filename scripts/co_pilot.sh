#!/usr/bin/env bash
# Phase 1.5 哥伦比亚试点 CLI
set -euo pipefail
BASE="${1:-http://127.0.0.1:8000}"
echo "=== SMART CRM CO Pilot ==="
curl -sf -X POST "$BASE/api/pilot/co/start" \
  -H "Content-Type: application/json" \
  -d '{"country_iso":"CO","category_l3":"bakeware","anchor_limit":2,"enqueue_track_a":true}' \
  | python3 -m json.tool 2>/dev/null
