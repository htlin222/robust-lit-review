#!/usr/bin/env bash
# Build the verdict-style appraisal site from appraisal.json.
#
# FIDELITY NOTE: the templates under templates/web/ are a reverse-engineered
# rebuild of the verdict-4plus2r look. To match the original exactly, rsync the
# source first and port its CSS/markup into templates/web/assets:
#   rsync -av <host>:verdict-4plus2R/ ~/verdict-4plus2R/
#
# Usage: scripts/build_site.sh [appraisal.json] [output_dir]
set -euo pipefail

APPRAISAL="${1:-appraisal.json}"
OUT="${2:-output/site}"

if [ ! -f "$APPRAISAL" ]; then
  echo "appraisal.json not found at: $APPRAISAL" >&2
  echo "Generate it via the claim-appraisal pipeline, or pass a path." >&2
  exit 1
fi

python -m litreview.cli build-site "$APPRAISAL" -o "$OUT"
echo "Site built at: $OUT"
echo "Preview: wrangler pages dev $OUT"
