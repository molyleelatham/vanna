#!/bin/bash
# SuperNode Setup Script for Vanna Federation
# Run this on EACH SuperNode machine
# Usage: DESK_ID=0 ./supernode_setup.sh

set -e

# ============================================
# CONFIGURATION — EDIT THESE PER NODE
# ============================================
DESK_ID=${DESK_ID:-0}          # 0, 1, 2, 3, or 4 (unique per SuperNode)
SUPERLINK_URL="supergrid.flower.ai"
FEDERATION="@molyleela/Vanna"
DATA_DIR="${HOME}/vanna_data"   # Writable directory
SOURCE_ROOT="/Users/molyleelatham/flowerhackathon/apps/federation/artifacts/desk_partitions"
UV_PYTHON="/Users/molyleelatham/flowerhackathon/.venv/bin/python3"
# ============================================

echo "=== Vanna SuperNode Setup ==="
echo "Desk ID: $DESK_ID"
echo "SuperLink: $SUPERLINK_URL"
echo "Federation: $FEDERATION"
echo "Data dir: $DATA_DIR"
echo "Python: $UV_PYTHON"

# 1. Verify dependencies exist in uv environment
echo "Verifying dependencies..."
$UV_PYTHON -c "import flwr, numpy, xgboost; print('Dependencies OK: flwr', flwr.__version__, 'numpy', numpy.__version__, 'xgboost', xgboost.__version__)"

# 2. Create data directory
mkdir -p "$DATA_DIR"

# 3. Copy desk partition
SOURCE_FILE="$SOURCE_ROOT/desk_${DESK_ID}.npz"
DEST_FILE="$DATA_DIR/desk_${DESK_ID}.npz"

if [ -f "$SOURCE_FILE" ]; then
    cp "$SOURCE_FILE" "$DEST_FILE"
    echo "Copied desk partition: $DEST_FILE"
else
    echo "ERROR: Source file not found: $SOURCE_FILE"
    echo "Generate it first on Moly's machine."
    exit 1
fi

# 3. Verify NPZ file
echo "Verifying desk partition..."
$UV_PYTHON -c "
import numpy as np
data = np.load('$DEST_FILE', allow_pickle=True)
print(f'  x_train: {data[\"x_train\"].shape}')
print(f'  y_train: {data[\"y_train\"].shape}')
print(f'  x_test: {data[\"x_test\"].shape}')
print(f'  y_test: {data[\"y_test\"].shape}')
print(f'  config: {data[\"config\"].item()}')
"

# 4. Login to SuperGrid (run once per machine)
echo ""
echo "=== SuperGrid Login ==="
echo "Run: flwr login supergrid"
echo "Then authenticate in browser."
echo ""

# 5. Start SuperNode command
echo "=== Start SuperNode ==="
echo "Run this command in terminal:"
echo ""
echo "  flower-supernode \\"
echo "    --insecure \\"
echo "    --superlink $SUPERLINK_URL \\"
echo "    --federation $FEDERATION \\"
echo "    --node-config=\"data-path=$DEST_FILE\""
echo ""

# 6. Quick test command
echo "=== Quick Test (local simulation) ==="
echo "If SuperGrid not available, test locally:"
echo "  cd /Users/molyleelatham/flowerhackathon/apps/federation"
echo "  uv run flwr run . --federation-config=\"num-supernodes=5\" --stream"