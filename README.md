# flowerhackathon

Shared Flower hackathon repo for SuperGrid, SuperLink, and collaborative AgentApps.

This branch (`supergrid-connectivity`) pulls the shared GitHub project into the local workspace and adds the Flower `AgentApp` so SuperGrid / SuperLink / connectivity work can merge back into `main`.

## Team docs

| File | What it is |
|---|---|
| [AGENTS.md](AGENTS.md) | Collaboration rules, ownership (Melanie / Moly), and demo criteria |
| [PRD_FlowSense_FX_Last_Look.md](PRD_FlowSense_FX_Last_Look.md) | FlowSense FX last-look product PRD |
| [TRACK_2_FlowSense_FX_Infrastructure.md](TRACK_2_FlowSense_FX_Infrastructure.md) | Track 2 SuperGrid / SuperLink infrastructure |
| [PRD_Federated_Equity_Intelligence_Network.md](PRD_Federated_Equity_Intelligence_Network.md) | Equity-intelligence exploration PRD |
| [SKILL_Flower_Framework_Documentation.md](SKILL_Flower_Framework_Documentation.md) | Flower SuperGrid, SuperLink, Agent, and FAB reference |

## AgentApp

The `agent/` package is a Flower `AgentApp` that sends a configured prompt through Flower Runtime with the OpenAI SDK, republishes streamed response events, and prints the final text.

Flower Runtime supplies the SDK base URL and task token, so this app does not need provider credentials.

### Requirements

- Python 3.11 or 3.12
- [uv](https://docs.astral.sh/uv/)

### Setup

```shell
uv sync
source .venv/bin/activate
```

### Build and run on SuperGrid

```shell
uv run flwr build
uv run flwr login supergrid
uv run flwr run . supergrid --stream
```

Override the default prompt:

```shell
uv run flwr run . supergrid \
    --run-config 'agent.input="Explain agent harness in one paragraph."' \
    --stream
```

## Git workflow

`main` tracks [molyleelatham/flowerhackathon](https://github.com/molyleelatham/flowerhackathon).

SuperGrid, SuperLink, and connectivity work happens on `supergrid-connectivity`. Merge that branch into `main` when a slice is ready:

```shell
git checkout supergrid-connectivity
git pull origin supergrid-connectivity
# ... build SuperGrid / SuperLink / connectivity ...
git add -A && git commit && git push
```

Then merge via the pull request into `main`.

## License

Apache License 2.0. See [LICENSE](LICENSE).
