"""Encounters domain."""

# Register queue ORM metadata whenever the encounters package is loaded.
from backend.domains.encounters import opd_queue_models as opd_queue_models  # noqa: F401

# Extend the existing OPD queue router without duplicating the queue state machine.
from backend.domains.encounters import opd_queue_router as opd_queue_router  # noqa: E402,F401
from backend.domains.encounters.opd_queue_lifecycle import register as register_opd_queue_lifecycle

register_opd_queue_lifecycle(opd_queue_router.router)
