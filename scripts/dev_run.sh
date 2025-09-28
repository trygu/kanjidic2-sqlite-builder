#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
source .venv/bin/activate
pip install -e .
mkdir -p out
k2sqlite build --input "${1:-tests/fixtures/sample_kanjidic2.xml}" --db out/kanjidic2.sqlite --batch 50
echo "SQLite written to out/kanjidic2.sqlite"
