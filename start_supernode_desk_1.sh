#!/bin/bash
# Start SuperNode for DESK_B (desk 1) — Flower 1.35.0 / SuperGrid
# Run this in a separate terminal; keep it open for the whole run.

set -e

# 1. Stage + verify desk partition (idempotent)
DESK_ID=1 /Users/molyleelatham/flowerhackathon/supernode_setup.sh

# 2. Start SuperNode (registered as node 2606826679259899920)
exec flower-supernode \
  --superlink fleet-supergrid.flower.ai:443 \
  --auth-supernode-private-key "$HOME/vanna_data/keys/desk_1_private.pem" \
  --node-config="partition-id=1" \
  --port 9095 \
  --allow-runtime-dependency-installation
