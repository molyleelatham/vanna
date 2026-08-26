# Vanna Agent Guide

Read `TECH_ARCH.md`, `HANDOVER.md`, and `README.md` before changing the project.

## Project boundaries

- Vanna is the product name. Do not reintroduce the former name.
- `apps/federation` owns Flower `ServerApp`/`ClientApp` infrastructure.
- `apps/agent` owns Vanna, LastLookAgent, CounterpartyRiskAgent, MarginAgent,
  ManipulationWatch, and GovernanceAgent.
- Keep these roles independently testable until the orchestrator is merged.
- A Flower FAB can contain either an `AgentApp` or a
  `ServerApp`/`ClientApp` pair; do not combine them.
- Keep SuperGrid and local SuperLink runtime selection outside business logic.
- Keep live decisions local. Federation is a background model-update path.

## Safety invariants

- Never share raw orders, client/account IDs, UTIs, positions, or live intent.
- HMAC values are pseudonyms, not anonymous identities.
- Never implement automatic execution, blacklisting, regulatory filing, or
  collective provider instructions.
- Preserve minimum-cohort, freshness, confidence, fallback, and human-review
  controls.
- Treat last-look asymmetry as a review signal, not proof of misconduct.

## Contribution protocol

- Keep numerical routing and governance deterministic; use models to explain.
- Validate structured inputs and handoffs with strict schemas.
- Bound model/tool loops and handle endpoint failure with a local fallback.
- Add or update tests for every behavior change.
- Run `uv run pytest -q` and build each affected FAB before handover.
- Update `TECH_ARCH.md` when interfaces or data flow change.
- Update `HANDOVER.md` after each meaningful contribution with completed work,
  verification results, open risks, and the next integration step.
- Never commit credentials, local Flower tokens, or model API keys.
# Agent Guide

## Start with context

Before changing code:

1. Read this file, the root `README.md`, relevant package configuration, and the files surrounding the change.
2. Understand the architecture and trace the full data/control flow before editing.
3. Check recent Git history and current working-tree changes so you do not overwrite another contributor's work.
4. Identify conflicts, inconsistent assumptions, broken handoffs, privacy leaks, and logical edge cases. Resolve them when they are in scope; otherwise document them clearly.

## Current architecture

- `apps/federation/` is the Flower federated-learning app. Five isolated desk clients train a transparent NumPy model; the server aggregates with FedAvg and exports approved provider evidence without raw orders or client identities.
- `packages/vanna-core/` owns shared typed schemas, privacy controls, deterministic provider ranking, and governance decisions.
- `apps/agent/` is the collaborative Flower AgentApp layer for Vanna and LastLook. It should consume approved aggregate evidence, use explicit typed handoffs, and keep final decisions locally governed.
- Preserve the boundary: private desk data stays local, only approved aggregates cross boundaries, deterministic calculations precede model-generated explanations, and consequential outcomes remain reviewable.

When the architecture changes, update this section and the root documentation in the same change.

## Collaboration and ownership

- Make ownership explicit before parallel work. Delegate each workstream to either **Melanie** or **Moly**, with a clear scope, inputs, expected output, and handoff point.
- Before delegation, check for overlapping files, incompatible assumptions, duplicated work, and ordering dependencies.
- At every handoff, review the result against the surrounding context, architecture, interfaces, and hackathon goals. Do not merge outputs mechanically.
- Surface disagreements and logical conflicts early. Prefer typed contracts, narrow interfaces, and written assumptions over implicit coordination.

## Git discipline

- Always commit completed changes, including changes produced through delegation to Melanie or Moly.
- Keep commits small, coherent, and attributable to one workstream. Review the diff and run relevant checks before committing.
- Never overwrite, discard, or silently include unrelated work already in the working tree.
- Use commit messages that explain why the change helps the product or demo.
- Do not push, force-push, rewrite history, or amend someone else's commit unless explicitly requested.

## Hackathon north star

Every material decision should support at least one track and strengthen the short demo.

### Track 1: SuperGrid

Show how collaboration multiplies the value of Flower Agents running on SuperGrid. Prefer a visible agent chain or multiple AgentApps that share context and hand work between agents. The demo must make each agent's contribution and the benefit of collaboration obvious.

### Track 2: Infrastructure

Build a new collaborative-agent use case by adapting or extending the infrastructure. A single-agent or multi-agent project may run on SuperGrid or a local SuperLink and may use available models or AMD MI300 compute. Infrastructure work should enable a concrete, understandable use case rather than exist only as plumbing.

### Required delivery

- Produce a working AgentApp.
- Prepare a reliable demo that fits within 3–5 minutes.
- Optimize the critical path for clarity, repeatability, and visible collaboration.
- Keep a fallback path for network, model, or infrastructure failure during the demo.

## Evaluation checklist

Before considering work complete, ask:

- **Impact:** Is the solution useful, and is its value easy to explain?
- **Innovation:** Is the collaborative approach meaningfully original?
- **Use of Flower:** Are Flower Agent and SuperGrid central rather than decorative?
- **Technical execution:** Does the end-to-end flow work, with tests or reproducible checks?
- **Demo and delivery:** Can the result be shown clearly in 3–5 minutes?
- **Safety and oversight:** Are data boundaries, assumptions, provenance, confidence, failures, and human review transparent?

Do not trade safety or correctness for a polished demo. If a feature does not improve these criteria or the working demo, deprioritize it.
