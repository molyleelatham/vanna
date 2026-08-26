#!/bin/bash
# Start SuperNode for DESK_C (desk 2) — Flower 1.35.0 / SuperGrid
# Run this in a separate terminal; keep it open for the whole run.

set -e

# 1. Stage + verify desk partition (idempotent)
DESK_ID=2 /Users/molyleelatham/flowerhackathon/supernode_setup.sh

# 2. Start SuperNode (registered as node 9164357068139953982)
exec flower-supernode \
  --superlink fleet-supergrid.flower.ai:443 \
  --auth-supernode-private-key "$HOME/vanna_data/keys/desk_2_private.pem" \
  --node-config="partition-id=2" \
  --port 9096
