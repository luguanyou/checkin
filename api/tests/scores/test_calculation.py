from decimal import Decimal

import pytest
from pydantic import ValidationError

from attendance_api.modules.scores.service import calculate_summary
from attendance_api.schemas.scores import ScoreSettings, SetScoreSettingsRequest


def settings(base: str | None = "70", **factors: str | None) -> ScoreSettings:
    return ScoreSettings(
        base_score=base,
        factors={
            category: factors.get(category, "1")
            for category in ("HOMEWORK", "CLASSROOM", "LAB", "OTHER")
        },
    )


def test_decimal_precision_no_category_caps_and_final_clamp() -> None:
    result = calculate_summary(
        "e",
        settings(),
        {
            "HOMEWORK": [Decimal("0.1"), Decimal("0.2")],
            "CLASSROOM": [Decimal("-0.5")],
            "LAB": [Decimal("100")],
        },
    )
    assert result.raw_score == "169.80"
    assert result.final_score == "100.00"
    assert Decimal(result.categories[0].points) == Decimal("0.30")
    assert result.categories[2].contribution == "100.00"
    low = calculate_summary("e", settings(), {"OTHER": [Decimal("-100")]})
    assert low.raw_score == "-30.00"
    assert low.final_score == "0.00"


def test_round_only_after_exact_accumulation() -> None:
    result = calculate_summary(
        "e",
        settings("0", HOMEWORK="0.5", LAB="0.5"),
        {
            "HOMEWORK": [Decimal("0.005")],
            "LAB": [Decimal("0.005")],
        },
    )
    assert result.raw_score == "0.01"


def test_null_zero_and_disabled_category_are_distinct() -> None:
    pending = calculate_summary("e", settings(), {"HOMEWORK": [None]})
    assert pending.status == "RECORDS_PENDING"
    assert pending.raw_score == "70.00"
    assert pending.final_score == "70.00"
    assert pending.categories[0].points == "0"
    assert pending.categories[0].contribution == "0.00"
    zero = calculate_summary("e", settings(), {"HOMEWORK": [Decimal("0")]})
    assert zero.status == "READY"
    assert zero.final_score == "70.00"
    disabled = calculate_summary("e", settings(HOMEWORK="0"), {"HOMEWORK": [None]})
    assert disabled.status == "READY"
    assert disabled.final_score == "70.00"


@pytest.mark.parametrize("rules", [settings(None), settings(LAB=None)])
def test_missing_rules_never_generate_official_score(rules: ScoreSettings) -> None:
    result = calculate_summary("e", rules, {})
    assert result.status == "RULES_PENDING"
    assert result.raw_score is None
    assert result.final_score is None


@pytest.mark.parametrize("value", ["NaN", "Infinity", "0.00001", "10000000000000000"])
def test_schema_rejects_unrepresentable_decimals(value: str) -> None:
    with pytest.raises(ValidationError):
        SetScoreSettingsRequest(
            expected_version=0, base_score=value, factors={c: "1" for c in settings().factors}
        )


def test_factors_require_all_categories_and_nonnegative_values() -> None:
    for factors in [{"HOMEWORK": "1"}, {**settings().factors, "LAB": "-0.5"}]:
        with pytest.raises(ValidationError):
            SetScoreSettingsRequest(expected_version=0, base_score="70", factors=factors)
