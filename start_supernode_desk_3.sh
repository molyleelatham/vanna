#!/bin/bash
# Start SuperNode for DESK_D (desk 3) — Flower 1.35.0 / SuperGrid
# Run this in a separate terminal; keep it open for the whole run.

set -e

# 1. Stage + verify desk partition (idempotent)
DESK_ID=3 /Users/molyleelatham/flowerhackathon/supernode_setup.sh

# 2. Start SuperNode (registered as node 165198172234468922)
exec flower-supernode \
  --superlink fleet-supergrid.flower.ai:443 \
  --auth-supernode-private-key "$HOME/vanna_data/keys/desk_3_private.pem" \
  --node-config="partition-id=3" \
  --port 9097
