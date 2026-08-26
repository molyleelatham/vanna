"""Copy Flower's approved aggregate output into the AgentApp bundle."""

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "apps/federation/artifacts/generated/provider_evidence.json"
TARGET = ROOT / "apps/agent/vanna_agent/artifacts/provider_evidence.json"


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(
            "Federation artifact missing. Run `uv run flwr run . local-simulation --stream` "
            "from apps/federation first."
        )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE, TARGET)
    print(f"Copied approved aggregate evidence to {TARGET}")


if __name__ == "__main__":
    main()
