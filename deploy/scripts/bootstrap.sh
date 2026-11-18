#!/usr/bin/env bash
# Fetch Odoo CE at the pinned version into the repo root. EE must be supplied manually (licensed).
set -euo pipefail
cd "$(dirname "$0")/.."; source versions.env
ROOT=$(cd .. && pwd)
[ -d "$ROOT/odoo-c" ] || git clone --depth 1 -b "$ODOO_VERSION" https://github.com/odoo/odoo "$ROOT/odoo-c"
[ -d "$ROOT/odoo-e" ] || echo "Place your licensed Enterprise copy at $ROOT/odoo-e"
