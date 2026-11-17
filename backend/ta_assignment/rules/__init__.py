"""Config-driven eligibility and scoring: department profiles and their compiler."""

from .compiler import CompiledProfile, Session, compile_profile, load_profile
from .fields import FIELDS
from .schema import DepartmentProfile

__all__ = ["CompiledProfile", "Session", "compile_profile", "load_profile",
           "FIELDS", "DepartmentProfile"]
