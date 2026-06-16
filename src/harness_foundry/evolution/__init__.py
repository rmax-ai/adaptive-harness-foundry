"""Evolution plane exports for Adaptive Harness Foundry."""

from harness_foundry.evolution.critic import CandidateCritic
from harness_foundry.evolution.digester import TraceDigester
from harness_foundry.evolution.evolver import CandidateEvolver
from harness_foundry.evolution.linter import PatchLinter
from harness_foundry.evolution.pipeline import EvolutionPipeline, EvolutionResult
from harness_foundry.evolution.planner import FailurePlanner
from harness_foundry.evolution.promotion import (
    GateCheck,
    GateResult,
    PromotionGate,
    PromotionPolicy,
)

__all__ = [
    "CandidateCritic",
    "CandidateEvolver",
    "EvolutionPipeline",
    "EvolutionResult",
    "FailurePlanner",
    "GateCheck",
    "GateResult",
    "PatchLinter",
    "PromotionGate",
    "PromotionPolicy",
    "TraceDigester",
]
