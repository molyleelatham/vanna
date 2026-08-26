#!/bin/bash
# Start SuperNode for DESK_E (desk 4) — Flower 1.35.0 / SuperGrid
# Run this in a separate terminal; keep it open for the whole run.

set -e

# 1. Stage + verify desk partition (idempotent)
DESK_ID=4 /Users/molyleelatham/flowerhackathon/supernode_setup.sh

# 2. Start SuperNode (registered as node 819782348755101228)
exec flower-supernode \
  --superlink fleet-supergrid.flower.ai:443 \
  --auth-supernode-private-key "$HOME/vanna_data/keys/desk_4_private.pem" \
  --node-config="partition-id=4" \
  --port 9098 \
  --allow-runtime-dependency-installation
