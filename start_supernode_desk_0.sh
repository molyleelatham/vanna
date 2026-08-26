#!/bin/bash
# Start SuperNode for DESK_A (desk 0) — Flower 1.35.0 / SuperGrid
# Run this in a separate terminal; keep it open for the whole run.

set -e

# 1. Stage + verify desk partition (idempotent)
DESK_ID=0 /Users/molyleelatham/flowerhackathon/supernode_setup.sh

# 2. Start SuperNode (registered as node 14730157165456493861)
exec flower-supernode \
  --superlink fleet-supergrid.flower.ai:443 \
  --auth-supernode-private-key "$HOME/vanna_data/keys/desk_0_private.pem" \
  --node-config="partition-id=0" \
  --port 9094 \
  --allow-runtime-dependency-installation
