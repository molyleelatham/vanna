# Melanie — Vanna SuperGrid SuperNode Setup

**Goal:** Connect 5 SuperNodes to federation `@molyleela/Vanna` so the federated training runs on SuperGrid.

---

## Prerequisites (do once)

```bash
# 1. Install Flower 1.35.0+
uv pip install "flwr[simulation]==1.35.0"

# 2. Login to SuperGrid
flwr login supergrid
# → Opens browser; authenticate with your Flower account
# → Creates ~/.flwr/config.yaml with token

# 3. Verify federation exists
flwr federation list
# Should show @molyleela/Vanna

# 4. Check federation config (needs 5 nodes)
flwr federation status @molyleela/Vanna
```

---

## Start a SuperNode (run 5 times, in 5 terminals)

> **Verified on Flower 1.35.0 (2026-08-26).** The SuperGrid Fleet API is at
> `fleet-supergrid.flower.ai:443`. There is no `--federation` flag on
> `flower-supernode` — federation membership is set server-side via
> `flwr federation add-supernode`. Do not use `--insecure` (SuperGrid is TLS).

### One-time per node: key pair + registration (already done for Moly's 5 nodes)

```bash
# 1. Generate an EC P-384 key pair (OpenSSH format)
ssh-keygen -t ecdsa -b 384 -f ~/vanna_data/keys/desk_0_private.pem -N ""

# 2. Register the public key on SuperGrid → returns a node ID
flwr supernode register ~/vanna_data/keys/desk_0_private.pem.pub supergrid

# 3. Add the node to the federation
flwr federation add-supernode <NODE_ID> @molyleela/Vanna supergrid
```

Moly's registered nodes (keys in `~/vanna_data/keys/`, not in Git):

| Desk | Node ID | Script |
|------|---------|--------|
| 0 (DESK_A) | 14730157165456493861 | `start_supernode_desk_0.sh` |
| 1 (DESK_B) | 2606826679259899920 | `start_supernode_desk_1.sh` |
| 2 (DESK_C) | 9164357068139953982 | `start_supernode_desk_2.sh` |
| 3 (DESK_D) | 165198172234468922 | `start_supernode_desk_3.sh` |
| 4 (DESK_E) | 819782348755101228 | `start_supernode_desk_4.sh` |

### Start command (per node)

```bash
# On Moly's machine just run: ./start_supernode_desk_N.sh  (N = 0..4)
# Each script stages the desk partition, then execs:

flower-supernode \
  --superlink fleet-supergrid.flower.ai:443 \
  --auth-supernode-private-key "$HOME/vanna_data/keys/desk_N_private.pem" \
  --node-config="partition-id=N" \
  --port 909N   # unique per node when sharing one machine (9094–9098)
```

**Notes:**
- `--node-config` must be valid TOML-ish: `partition-id=0` (int) works; string
  values need inner quotes, e.g. `--node-config='data-path="/app/data/desk_0.npz"'`.
  The federation ClientApp reads `partition-id`; it loads
  `artifacts/desk_partitions/desk_N.npz` if present and falls back to
  deterministic synthetic data otherwise.
- All 5 must connect **simultaneously** (federation requires `min_train_nodes=5`)
- Keep terminals open — nodes must stay connected for all 3 FedAvg rounds (~15-30s)
- If a node drops, the round fails
- Verify with `flwr supernode list supergrid` — all 5 should show `online`

---

## Prepare Desk Data (for Option B)

Each SuperNode needs its desk partition as an `.npz` file. Generate them:

```bash
# On Moly's machine (or any machine with the repo):
cd /Users/molyleelatham/flowerhackathon
uv run python -c "
from apps.federation.vanna_federation.desk_config import generate_random_desk_configs, save_desk_configs
from apps.federation.vanna_federation.data import generate_all_desks
from apps.federation.vanna_federation.persistence import save_desk_partition, ensure_dirs
from pathlib import Path

# Generate 5 desk configs
configs = generate_random_desk_configs(num_desks=5, seed=20260826)
desks = generate_all_desks(configs)

# Save each partition
for i, (config, desk) in enumerate(zip(configs, desks)):
    save_desk_partition(i, config.to_dict(), desk.x_train, desk.y_train, desk.x_test, desk.y_test)

print('Desk partitions saved to artifacts/desk_partitions/')
"
```

Copy the 5 `.npz` files to each SuperNode machine at `/app/data/desk_N.npz`.

---

## Run the federation (Moly runs this)

Once 5 nodes show as connected:

```bash
cd apps/federation
uv run flwr run . supergrid --federation @molyleela/Vanna --stream
```

This submits the FAB to SuperGrid; the 5 connected SuperNodes will execute the 3 FedAvg rounds using their local desk partitions.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `flwr login supergrid` fails | Check internet, try `flwr login supergrid --insecure` |
| Nodes don't appear in `federation status` | Ensure all 5 terminals running `flower-supernode` simultaneously |
| "Insufficient nodes" error | Federation config requires 5; start all 5 before running |
| Node disconnects mid-run | Restart all 5 nodes, re-run federation |
| `supergrid.flower.ai` unreachable | Check VPN/firewall; SuperGrid requires internet access |

---

## Quick test: local simulation (no SuperNodes needed)

If SuperGrid isn't working, the local path works instantly:

```bash
cd apps/federation
uv run flwr run . --federation-config="num-supernodes=5" --stream
cd ../..
uv run python scripts/sync_federation_artifact.py
uv run python scripts/local_demo.py
```

This uses Ray to simulate 5 SuperNodes locally — no SuperGrid login needed.

---

## Local SuperLink + AgentApp (for full demo)

If you have the AMD model endpoint:

```bash
# Terminal 1: Start local SuperLink
export FLWR_MODEL_API_ENDPOINT="<hackathon /v1/responses endpoint>"
export FLWR_MODEL_API_KEY="<hackathon Slack key>"
export VANNA_MODEL_ID="<matching model ID>"
uv run flower-superlink --insecure

# Terminal 2: Run AgentApp on local SuperLink
cd apps/agent
uv run flwr run . local-superlink --stream
```

This runs the AgentApp against your local SuperLink with the model endpoint.

---

## Files you don't need to touch

| File | Why |
|------|-----|
| `apps/federation/vanna_federation/*.py` | Federation logic — already built into FAB |
| `apps/agent/...` | AgentApp — separate FAB, runs after federation |
| `packages/vanna-core/...` | Shared schemas — embedded in both FABs |

---

## Contact

- **Moly** — federation/agent architecture, OrchestratorAgent, demo flow
- **Hackathon Slack** — SuperGrid credentials, AMD model endpoint
- **Flower docs** — `flwr federation --help`, `flower-supernode --help`

---

**Last updated:** 26 August 2026