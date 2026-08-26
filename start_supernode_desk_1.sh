#!/bin/bash
# Auto-generated: Start SuperNode for DESK_B
# Run this in a separate terminal

DESK_ID=1 /Users/molyleelatham/flowerhackathon/supernode_setup.sh

# After setup completes, run this command:
flower-supernode \
  --insecure \
  --superlink supergrid.flower.ai \
  --federation @molyleela/Vanna \
  --node-config="data-path=/Users/molyleelatham/vanna_data/desk_1.npz"
