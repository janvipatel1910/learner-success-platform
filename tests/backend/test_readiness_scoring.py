import pytest

from skillpulse.core.readiness import COMPONENTS, calculate_readiness


WEIGHTS = {
    "quiz": 0.20,
    "mock": 0.30,
    "lab": 0.20,
    "attendance": 0.15,
    "blockers": 0.15,
}


def components_with_score(score: float) -> dict[str, float]:
    return {name: score for name in COMPONENTS}


def test_calculates_weighted_score_and_ready_level() -> None:
    components = {
        "quiz": 80,
        "mock": 90,
        "lab": 100,
        "attendance": 80,
        "blockers": 70,
    }

    result = calculate_readiness(
        components=components,
        weights=WEIGHTS,
        readiness_threshold=80,
        minimum_mock_score=80,
        minimum_lab_completion=80,
    )

    assert result["overall_score"] == 85.5
    assert result["readiness_level"] == "ready"


def test_returns_nearly_ready_when_score_is_close_but_gate_fails() -> None:
    components = {
        "quiz": 80,
        "mock": 75,
        "lab": 70,
        "attendance": 80,
        "blockers": 70,
    }

    result = calculate_readiness(
        components=components,
        weights=WEIGHTS,
        readiness_threshold=80,
        minimum_mock_score=80,
        minimum_lab_completion=60,
    )

    assert result["overall_score"] == 75.0
    assert result["readiness_level"] == "nearly_ready"


def test_returns_developing_level() -> None:
    result = calculate_readiness(
        components=components_with_score(65),
        weights=WEIGHTS,
        readiness_threshold=80,
        minimum_mock_score=60,
        minimum_lab_completion=60,
    )

    assert result["overall_score"] == 65.0
    assert result["readiness_level"] == "developing"


def test_returns_not_ready_level() -> None:
    result = calculate_readiness(
        components=components_with_score(40),
        weights=WEIGHTS,
        readiness_threshold=80,
        minimum_mock_score=60,
        minimum_lab_completion=60,
    )

    assert result["overall_score"] == 40.0
    assert result["readiness_level"] == "not_ready"


def test_rejects_weights_that_do_not_add_up_to_one() -> None:
    invalid_weights = {name: 0.1 for name in COMPONENTS}

    with pytest.raises(ValueError, match="add up to 1.0"):
        calculate_readiness(
            components=components_with_score(70),
            weights=invalid_weights,
            readiness_threshold=80,
            minimum_mock_score=60,
            minimum_lab_completion=60,
        )


def test_rejects_component_scores_outside_zero_to_one_hundred() -> None:
    invalid_components = components_with_score(70)
    invalid_components["quiz"] = 101

    with pytest.raises(ValueError, match="between 0 and 100"):
        calculate_readiness(
            components=invalid_components,
            weights=WEIGHTS,
            readiness_threshold=80,
            minimum_mock_score=60,
            minimum_lab_completion=60,
        )
