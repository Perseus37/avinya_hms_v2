import pytest

from backend.domains.workforce.services import calculate_indian_statutory_deductions


@pytest.mark.parametrize(
    ("period", "gross_paise", "expected_paise"),
    [
        ("2026-01", 2_499_999, 0),
        ("2026-01", 2_500_000, 20_000),
        ("2026-02", 2_500_000, 30_000),
        ("2026-03", 2_500_000, 20_000),
        ("2025-02", 2_000_000, 20_000),
        ("2025-04", 1_500_000, 0),
        ("2025-04", 2_500_000, 20_000),
    ],
)
def test_karnataka_professional_tax_effective_schedule(period, gross_paise, expected_paise):
    result = calculate_indian_statutory_deductions(
        gross_paise=gross_paise,
        prorated_fixed_paise=gross_paise,
        state="KA",
        payroll_period=period,
    )
    assert result["professional_tax_paise"] == expected_paise
    assert result["payroll_period"] == period


def test_professional_tax_fails_closed_for_unconfigured_state():
    with pytest.raises(ValueError, match="not configured"):
        calculate_indian_statutory_deductions(
            gross_paise=5_000_000,
            prorated_fixed_paise=5_000_000,
            state="AP",
            payroll_period="2026-01",
        )


@pytest.mark.parametrize("period", ["2026-1", "2026-13", "not-a-period"])
def test_professional_tax_rejects_invalid_payroll_period(period):
    with pytest.raises(ValueError, match="YYYY-MM"):
        calculate_indian_statutory_deductions(
            gross_paise=5_000_000,
            prorated_fixed_paise=5_000_000,
            state="KA",
            payroll_period=period,
        )
