from math import isclose, isfinite
from typing import Mapping

COMPONENTS = (
    "quiz",
    "mock",
    "lab",
    "attendance",
    "blockers",
)


def calculate_readiness(
    components: Mapping[str, float],
    weights: Mapping[str, float],
    readiness_threshold: float,
    minimum_mock_score: float,
    minimum_lab_completion: float,
) -> dict[str, object]:
    """Calculate an explainable learner-readiness result."""

    if set(components) != set(COMPONENTS):
        raise ValueError(f"components must contain exactly: {COMPONENTS}")

    if set(weights) != set(COMPONENTS):
        raise ValueError(f"weights must contain exactly: {COMPONENTS}")

    component_values = {name: float(components[name]) for name in COMPONENTS}
    weight_values = {name: float(weights[name]) for name in COMPONENTS}

    for name, value in component_values.items():
        if not isfinite(value) or not 0 <= value <= 100:
            raise ValueError(f"{name} must be between 0 and 100")

    for name, value in weight_values.items():
        if not isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"weight for {name} must be between 0 and 1")

    if not isclose(sum(weight_values.values()), 1.0, abs_tol=0.000001):
        raise ValueError("component weights must add up to 1.0")

    thresholds = {
        "readiness_threshold": float(readiness_threshold),
        "minimum_mock_score": float(minimum_mock_score),
        "minimum_lab_completion": float(minimum_lab_completion),
    }

    for name, value in thresholds.items():
        if not isfinite(value) or not 0 <= value <= 100:
            raise ValueError(f"{name} must be between 0 and 100")

    overall_score = round(
        sum(
            component_values[name] * weight_values[name]
            for name in COMPONENTS
        ),
        2,
    )

    gates = {
        "overall_threshold_met": overall_score >= thresholds["readiness_threshold"],
        "minimum_mock_score_met": (
            component_values["mock"]
            >= thresholds["minimum_mock_score"]
        ),
        "minimum_lab_completion_met": (
            component_values["lab"]
            >= thresholds["minimum_lab_completion"]
        ),
    }

    if all(gates.values()):
        readiness_level = "ready"
    elif overall_score >= max(50.0, thresholds["readiness_threshold"] - 10.0):
        readiness_level = "nearly_ready"
    elif overall_score >= 50.0:
        readiness_level = "developing"
    else:
        readiness_level = "not_ready"

    explanation = {
        "algorithm_version": "1.0",
        "method": "weighted_average",
        "components": component_values,
        "weights": weight_values,
        "gates": gates,
    }

    return {
        "overall_score": overall_score,
        "readiness_level": readiness_level,
        "explanation_json": explanation,
    }
