# Vanna status — 26 Aug 2026

Branch: `supergrid-connectivity`  
PR: https://github.com/molyleelatham/flowerhackathon/pull/1  
Federation: `@molyleela/Vanna` (SuperGrid, deployment, active)

---

## What has been done

**Two Flower apps (do not combine them)**

| App | Path | Role |
|---|---|---|
| Federation | `apps/federation` | 5 desks, FedAvg, evidence export |
| AgentApp | `apps/agent` | Orchestrator + 6 agents |

**Working locally (no SuperGrid needed)**

- `uv run pytest -q` — 15 tests pass
- Local 5-desk simulation: `cd apps/federation && uv run flwr run . --federation-config="num-supernodes=5" --stream`
- Live path: `uv run python scripts/local_demo.py` (never waits on SuperGrid)
- Demo story: LP_A looks cheapest displayed; Vanna recommends **LP_B**; LastLook flags LP_A as review only; 0 raw records shared

**Infrastructure Melanie added**

- Stable agent interfaces (`assess()`) in `apps/agent/vanna_agent/agents/interfaces.py`
- Orchestrator calls those interfaces; swap constructors only in `OrchestratorAgent.__init__`
- Desk-local HMAC vault + IDs/UTIs stay in the ClientApp process
- Shared messages are weights + numeric metrics only
- Console handoff chain printed on the local demo
- Melanie is logged into SuperGrid and can see `@molyleela/Vanna`

---

## What still needs to be done

1. **5 SuperNodes on SuperGrid** — `@molyleela/Vanna` is a *deployment* federation. Local simulation is not SuperGrid. A SuperGrid run needs 5 connected nodes.
2. **Submit federation on SuperGrid** once those nodes are up.
3. **Run AgentApp on SuperGrid** with the AMD model endpoint (optional for the demo; local demo already shows the agent chain).
4. **Polish** — LLM narration prompts, timeout/malformed-output tests, write down only numbers from a real run.
5. **Merge PR #1 into `main`** when Moly is ready (additive; does not replace Vanna agents).

`flwr federation status` is **not** a real command. Use:

```bash
uv run flwr federation list --federation @molyleela/Vanna supergrid
uv run flwr supernode list --federation @molyleela/Vanna supergrid
```

---

## What Moly (developer) needs to do

**SuperGrid / nodes**

1. Confirm `@molyleela/Vanna` still has Melanie (and other teammates) invited.
2. Start or attach **5 SuperNodes** to `@molyleela/Vanna` and keep them connected.
3. Tell Melanie when `supernode list` shows 5 nodes. She can then run:

```bash
cd apps/federation
uv run flwr run . supergrid --federation @molyleela/Vanna --stream
```

4. Share the AMD endpoint + model id in Slack if you want AgentApp narration on SuperGrid (do not commit keys).

**Code / merge**

5. Review PR #1. Keep method name `assess` — do not rename to recommend/analyse/review.
6. If you change an agent class, only swap the constructor in `OrchestratorAgent.__init__`.
7. Pull `supergrid-connectivity` before editing the same files so we do not collide.
8. Merge to `main` when you are happy; Melanie can keep SuperGrid work on this branch until then.

**Demo fallback if SuperNodes are late**

Use the local path (already proven):

```bash
cd apps/federation
uv run flwr run . --federation-config="num-supernodes=5" --stream
cd ../..
uv run python scripts/sync_federation_artifact.py
uv run python scripts/local_demo.py
```

---

## Do not

- Commit Flower tokens, AMD keys, or `.env` files
- Combine AgentApp + ServerApp in one FAB
- Auto-execute trades or blacklist LPs
- Treat a last-look signal as proof of misconduct
