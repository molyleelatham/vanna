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

```bash
# Each terminal runs ONE SuperNode
flower-supernode \
  --superlink supergrid.flower.ai \
  --federation @molyleela/Vanna
```

**Important:**
- All 5 must connect **simultaneously** (federation requires `min_train_nodes=5`)
- Keep terminals open — nodes must stay connected for all 3 FedAvg rounds (~15-30s)
- If a node drops, the round fails

---

## Verify nodes are connected

In another terminal:

```bash
flwr federation status @molyleela/Vanna
```

Should show 5 connected SuperNodes.

---

## Run the federation (Moly runs this)

Once 5 nodes show as connected:

```bash
cd apps/federation
uv run flwr run . supergrid --federation @molyleela/Vanna --stream
```

This submits the FAB to SuperGrid; the 5 connected SuperNodes will execute the 3 FedAvg rounds.

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