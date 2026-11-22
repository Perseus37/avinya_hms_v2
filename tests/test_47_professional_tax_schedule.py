"""Focused regression tests for Karnataka professional-tax effective-date schedules."""

import pytest

from backend.domains.workforce.services import calculate_indian_statutory_deductions


def test_professional_tax_requires_explicit_payroll_period():
    with pytest.raises(TypeError, match="payroll_period"):
        calculate_indian_statutory_deductions(
            gross_paise=5_000_000,
            prorated_fixed_paise=5_000_000,
            state="KA",
        )


@pytest.mark.parametrize(
    ("payroll_period", "gross_paise", "expected_pt_paise"),
    [
        ("2023-03", 1_499_999, 0),
        ("2023-03", 1_500_000, 20_000),
        ("2023-04", 2_499_999, 0),
        ("2023-04", 2_500_000, 20_000),
        ("2025-02", 2_500_000, 20_000),
        ("2025-03", 2_500_000, 20_000),
        ("2025-04", 2_500_000, 20_000),
        ("2026-01", 2_500_000, 20_000),
        ("2026-02", 2_500_000, 30_000),
    ],
)
def test_karnataka_professional_tax_effective_schedule_boundaries(
    payroll_period, gross_paise, expected_pt_paise
):
    result = calculate_indian_statutory_deductions(
        gross_paise=gross_paise,
        prorated_fixed_paise=gross_paise,
        pf_opt_out=True,
        state="KA",
        payroll_period=payroll_period,
    )
    assert result["professional_tax_paise"] == expected_pt_paise
    assert result["payroll_period"] == payroll_period


@pytest.mark.parametrize(
    "payroll_period",
    [
        "",
        "2026-00",
        "2026-13",
        "0000-01",
        "+026-01",
        "２０２６-01",
        "2026/01",
        None,
    ],
)
def test_karnataka_professional_tax_rejects_malformed_periods(payroll_period):
    with pytest.raises(ValueError, match="payroll_period"):
        calculate_indian_statutory_deductions(
            gross_paise=5_000_000,
            prorated_fixed_paise=5_000_000,
            state="KA",
            payroll_period=payroll_period,
        )


@pytest.mark.parametrize("state", ["AP", " ", "XX"])
def test_professional_tax_fails_closed_for_unsupported_states(state):
    with pytest.raises(ValueError, match="not configured"):
        calculate_indian_statutory_deductions(
            gross_paise=5_000_000,
            prorated_fixed_paise=5_000_000,
            state=state,
            payroll_period="2026-01",
        )
