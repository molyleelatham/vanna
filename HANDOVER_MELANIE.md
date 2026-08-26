# Handover to Melanie — SuperGrid Infrastructure

**Date:** 26 August 2026
**From:** Moly
**Status:** ✅ SuperGrid workstream (Priority 4) is done end-to-end. One thing left from you: the AMD model ID.

---

## TL;DR

5 SuperNodes are registered and online on `@molyleela/Vanna`. A 3-round
federated XGBoost run completed on SuperGrid, and the Vanna AgentApp ran on
SuperGrid with the full 6-agent chain. Everything is committed on `main`.

---

## What's done (verified today)

| Item | Result |
|------|--------|
| 5 SuperNodes registered + added to federation | All `online` (`flwr supernode list supergrid`) |
| Federation run `12309076582906127164` | 3 rounds, 5/5 nodes, 0 failures, **0 raw records / 0 identities shared**, ~2.5 min |
| AgentApp run `1896158749138907396` | Full chain Vanna → LastLook → CounterpartyRisk → Margin → ManipulationWatch → Governance; LP_B @ 2.03 bps; Governance: HUMAN_REVIEW; ~22s |
| Start scripts | Fixed for Flower 1.35.0, committed (`03cbe75`, `da73bc7`) |

### Registered nodes (Moly's machine, keys in `~/vanna_data/keys/` — not in Git)

| Desk | Node ID | Start script | Port |
|------|---------|--------------|------|
| 0 (DESK_A) | 14730157165456493861 | `start_supernode_desk_0.sh` | 9094 |
| 1 (DESK_B) | 2606826679259899920 | `start_supernode_desk_1.sh` | 9095 |
| 2 (DESK_C) | 9164357068139953982 | `start_supernode_desk_2.sh` | 9096 |
| 3 (DESK_D) | 165198172234468922 | `start_supernode_desk_3.sh` | 9097 |
| 4 (DESK_E) | 819782348755101228 | `start_supernode_desk_4.sh` | 9098 |

---

## What I need from you

**1. AMD model ID (the only blocker for live LLM narration)**
The AgentApp ran with the deterministic fallback because the default model ID
(`glm-5.2-fp8`) errored on the runtime endpoint. Grab from hackathon Slack:
- model ID
- endpoint URL and key (if Slack lists them — for the local SuperLink path)

Send to Moly or add to the root `.env` (**never commit `.env`**).

**2. Keep nodes alive during the demo**
If the nodes drop, federation rounds fail (`min_train_nodes=5`). Check anytime:

```bash
flwr supernode list supergrid   # all 5 should say "online"
```

**3. Optional: run your own nodes**
You're a collaborator on the federation (`melapre`). If you want nodes on your
machine, follow `MELANIE.md` — the commands there are now verified against
Flower 1.35.0. You'll register your own key pair under your account.

---

## Operating cheatsheet

```bash
# Start/restart the 5 nodes (on Moly's machine, 5 terminals)
./start_supernode_desk_0.sh   # ... through desk_4

# Re-run federation on SuperGrid
cd apps/federation
uv run flwr run . supergrid --federation @molyleela/Vanna --stream

# Re-run the AgentApp on SuperGrid (add model-id once we have it)
cd apps/agent
uv run flwr run . supergrid --federation @molyleela/Vanna --stream \
  --run-config "agent.input='{\"pair\":\"EUR/USD\",\"side\":\"BUY\",\"size_bucket\":\"1m-5m\",\"volatility\":\"high\",\"available_providers\":[\"LP_A\",\"LP_B\",\"LP_C\"]}' model-id='<MODEL_ID>'"

# Local fallback demo (no SuperGrid needed — always works)
cd apps/federation && uv run flwr run . --federation-config="num-supernodes=5" --stream
cd ../.. && uv run python scripts/sync_federation_artifact.py
uv run python scripts/local_demo.py
```

---

## Gotchas (cost us an hour — don't rediscover these)

- `flower-supernode` has **no `--federation` flag** in 1.35.0 — membership is
  server-side (`flwr supernode register` + `flwr federation add-supernode`).
- Fleet API is `fleet-supergrid.flower.ai:443` (not `supergrid.flower.ai`,
  which is the Control API). No `--insecure` — SuperGrid is TLS.
- Node auth keys must be **OpenSSH format** (`ssh-keygen -t ecdsa -b 384`),
  not openssl PEM.
- Nodes need `--allow-runtime-dependency-installation` or the ClientApp env
  won't have xgboost.
- One `--port` per node when sharing a machine (default 9094 collides).
- `flwr pull` is **not supported** on SuperGrid — run artifacts stay
  server-side; the local demo uses locally generated evidence.

## Demo caveats (be honest if asked)

- Eval loss *rose* across the 3 SuperGrid rounds (0.64 → 0.78) with
  `local-trees=1` — don't claim the federated model "improves" without retuning.
- Model narration falls back to deterministic text if the endpoint fails —
  that's a designed safety feature, show it as such.
- Evidence JSON is partly derived from the model, partly from desk profiles —
  see the audit section in `TODO.md` before making claims about it.

---

**Contact:** Moly — federation/agent architecture. Hackathon Slack — model
endpoint credentials.
