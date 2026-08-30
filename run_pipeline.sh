#!/usr/bin/env bash
set -euo pipefail

echo "[1/4] Starting MySQL..."
docker compose up -d mysql

echo "[2/4] Loading CSVs into MySQL..."
docker compose run --rm etl python -m src.etl.load_to_mysql --all

echo "[3/4] Creating analytics views..."
docker compose run --rm etl python -m src.etl.create_views

echo "[4/4] Generating report..."
docker compose run --rm etl python -m src.analysis.generate_report

echo "[OK] Pipeline complete. See reports/eda_summary.md"
