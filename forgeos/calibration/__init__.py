"""ForgeOS calibration framework — one-time setup + fine-tuning for Neptune 4 Pro.

Catalog, analysis, G-code helpers, and orchestration aligned with OpenNeptune3D
macros and Klipper best practices for GOD-TIER fixture prints.
"""

from forgeos.calibration.analysis import (
    analyze_flow_wall_thickness,
    analyze_mesh_matrix,
    analyze_pa_tower_height,
    analyze_precision_span,
    analyze_retraction_tower,
    analyze_temp_tower_layer,
    gate_result_from_measurement,
)
from forgeos.calibration.registry import (
    CALIBRATION_CATALOG,
    CalCategory,
    CalPhase,
    CalTestDef,
    fine_tune_tests,
    gate_tests,
    get_calibration_test,
    one_time_tests,
    tests_for_phase,
)

test_by_id = get_calibration_test
from forgeos.calibration.runner import CalibrationRunner, CalStepResult

__all__ = [
    "CALIBRATION_CATALOG",
    "CalCategory",
    "CalPhase",
    "CalStepResult",
    "CalTestDef",
    "CalibrationRunner",
    "analyze_flow_wall_thickness",
    "analyze_mesh_matrix",
    "analyze_pa_tower_height",
    "analyze_precision_span",
    "analyze_retraction_tower",
    "analyze_temp_tower_layer",
    "fine_tune_tests",
    "gate_result_from_measurement",
    "gate_tests",
    "one_time_tests",
    "test_by_id",
    "tests_for_phase",
]
