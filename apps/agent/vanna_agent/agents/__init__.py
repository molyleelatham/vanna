"""Independent Vanna agent roles, ready for the final orchestrator merge."""

from .counterparty_risk import CounterpartyRiskAgent
from .governance import GovernanceAgent
from .last_look import LastLookAgent
from .manipulation_watch import ManipulationWatch
from .margin import MarginAgent
from .vanna import VannaAgent

AGENT_REGISTRY = {
    agent.name: agent
    for agent in (
        VannaAgent,
        LastLookAgent,
        CounterpartyRiskAgent,
        MarginAgent,
        ManipulationWatch,
        GovernanceAgent,
    )
}

__all__ = [
    "AGENT_REGISTRY",
    "CounterpartyRiskAgent",
    "GovernanceAgent",
    "LastLookAgent",
    "ManipulationWatch",
    "MarginAgent",
    "VannaAgent",
]
