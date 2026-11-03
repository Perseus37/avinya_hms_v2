"""Encounters domain."""

# Register queue ORM metadata whenever the encounters package is loaded.
from backend.domains.encounters import opd_queue_models as opd_queue_models  # noqa: F401
