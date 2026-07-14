"""Hard safety envelopes, arming tokens, and clamp logic.

Zero-trust rule: optimizers never write outside envelopes. Arming is explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
import time
import secrets


class SafetyError(Exception):
    """Raised when a proposed action violates hard envelopes or arming policy."""


@dataclass
class SafetyEnvelopes:
    """Exploration ceilings — not the operating point."""

    max_velocity_mm_s: float = 500.0
    max_precision_wall_velocity_mm_s: float = 300.0
    max_accel_mm_s2: float = 10000.0
    start_accel_mm_s2: float = 5000.0
    nozzle_temp_c: Tuple[float, float] = (190.0, 240.0)
    bed_temp_c: Tuple[float, float] = (0.0, 75.0)
    max_z_offset_step_mm: float = 0.02
    dim_error_100mm_fail_mm: float = 0.20
    precision_span_3x_fail_mm: float = 0.10
    require_hardened_for_abrasive: bool = True


@dataclass
class ArmingToken:
    purpose: str
    token: str
    expires_at: float
    armed: bool = True

    def is_valid(self, purpose: str, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        return self.armed and self.purpose == purpose and now <= self.expires_at


@dataclass
class SafetyGate:
    envelopes: SafetyEnvelopes = field(default_factory=SafetyEnvelopes)
    _tokens: Dict[str, ArmingToken] = field(default_factory=dict)

    def arm(self, purpose: str, ttl_s: float = 3600.0) -> str:
        if purpose not in {"autotune", "campaign", "runtime_micro"}:
            raise SafetyError("unknown arming purpose: %s" % purpose)
        token = secrets.token_hex(16)
        self._tokens[purpose] = ArmingToken(
            purpose=purpose,
            token=token,
            expires_at=time.time() + float(ttl_s),
        )
        return token

    def disarm(self, purpose: str) -> None:
        tok = self._tokens.get(purpose)
        if tok is not None:
            tok.armed = False

    def require_armed(self, purpose: str, token: Optional[str]) -> None:
        held = self._tokens.get(purpose)
        if held is None or not held.is_valid(purpose):
            raise SafetyError("not armed for purpose=%s (zero-trust refuse)" % purpose)
        if token is None or token != held.token:
            raise SafetyError("invalid arming token for purpose=%s" % purpose)

    def clamp_velocity(self, value: float, role: str = "travel") -> float:
        if role in {"outer_wall", "first_layer", "precision"}:
            ceiling = self.envelopes.max_precision_wall_velocity_mm_s
        else:
            ceiling = self.envelopes.max_velocity_mm_s
        return max(1.0, min(float(value), ceiling))

    def clamp_accel(self, value: float) -> float:
        return max(100.0, min(float(value), self.envelopes.max_accel_mm_s2))

    def clamp_nozzle_temp(self, value: float) -> float:
        lo, hi = self.envelopes.nozzle_temp_c
        return max(lo, min(float(value), hi))

    def clamp_bed_temp(self, value: float) -> float:
        lo, hi = self.envelopes.bed_temp_c
        return max(lo, min(float(value), hi))

    def clamp_z_offset_delta(self, delta: float) -> float:
        lim = self.envelopes.max_z_offset_step_mm
        return max(-lim, min(float(delta), lim))

    def preflight_nozzle(self, abrasive: bool, nozzle_type: str, nozzle_diameter_mm: float, min_diameter_mm: float) -> None:
        if abrasive and self.envelopes.require_hardened_for_abrasive:
            if str(nozzle_type).lower() not in {"hardened", "ruby", "tungsten", "olsson_ruby"}:
                raise SafetyError(
                    "abrasive filament requires hardened nozzle (got %s)" % nozzle_type
                )
        if nozzle_diameter_mm + 1e-9 < float(min_diameter_mm):
            raise SafetyError(
                "nozzle diameter %.2f < material minimum %.2f"
                % (nozzle_diameter_mm, min_diameter_mm)
            )

    def assert_dim_gate(self, abs_error_100mm: float) -> None:
        if abs(abs_error_100mm) > self.envelopes.dim_error_100mm_fail_mm:
            raise SafetyError(
                "dimensional gate FAIL |err|=%.3f > %.3f mm"
                % (abs(abs_error_100mm), self.envelopes.dim_error_100mm_fail_mm)
            )

    def assert_precision_gate(self, span_mm: float) -> None:
        if span_mm > self.envelopes.precision_span_3x_fail_mm:
            raise SafetyError(
                "precision gate FAIL span=%.3f > %.3f mm"
                % (span_mm, self.envelopes.precision_span_3x_fail_mm)
            )
