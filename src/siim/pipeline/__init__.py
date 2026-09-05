"""The deliverable pipeline: estimate -> refine -> re-estimate -> verify (D-044, D-045),
plus engine agreement as an independent verifier (R2)."""

from .agreement import AGREEMENT_FLOOR_PX, EngineAgreement, engine_agreement
from .register import (
    PIPELINE_ORDER,
    RegistrationResult,
    register_pair,
    register_pair_two_engines,
    with_agreement,
)
from .select import MODELS, ModelSelection, reestimate, select_model

__all__ = [
    "AGREEMENT_FLOOR_PX",
    "EngineAgreement",
    "engine_agreement",
    "PIPELINE_ORDER",
    "RegistrationResult",
    "register_pair",
    "register_pair_two_engines",
    "with_agreement",
    "MODELS",
    "ModelSelection",
    "reestimate",
    "select_model",
]
