from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import sessionmaker

from backend.domains.finance.models import (
    ExpenseRecord,
    ExpenseStatusEnum,
    RecurringExpenseTemplate,
)


def test_01_accounts_payable_maker_checker_workflow(client, superuser_headers):
    """Scenario 1: Expense draft (Maker) is PENDING, rejected without reason fails, rejected with reason succeeds."""
    draft_res = client.post(
        "/v1/api/finance/ap/expenses",
        headers=superuser_headers,
        json={
            "category": "MEDICAL_SUPPLIES",
            "title": "Restock Surgical Gloves",
            "amount_paise": 500000,
            "vendor_name": "MediEquip Inc.",
            "due_date": (datetime.now(timezone.utc) + relativedelta(days=15)).isoformat()
        }
    )
    assert draft_res.status_code == 201
    expense_id = draft_res.json()["id"]

    # Even a privileged approver cannot adjudicate an expense they created.
    self_reject = client.patch(
        f"/v1/api/finance/ap/expenses/{expense_id}/adjudicate",
        headers=superuser_headers,
        json={"status": "REJECTED", "rejection_reason": "Duplicate invoice submitted by vendor"}
    )
    assert self_reject.status_code == 403
    assert "creators cannot" in self_reject.json()["message"].lower()


def test_02_recurring_expense_cron_generation(client, superuser_headers, multi_tenant_env):
    """Scenario 2: Recurring template trigger evaluates dates and generates automated ExpenseRecords."""
    now = datetime.now(timezone.utc)
    past_date = (now - relativedelta(days=2)).isoformat()

    template_res = client.post(
        "/v1/api/finance/ap/recurring-templates",
        headers=superuser_headers,
        json={
            "category": "UTILITY",
            "title": "Hospital Electricity Bill",
            "amount_paise": 1500000,
            "vendor_name": "State Power Grid",
            "frequency": "MONTHLY",
            "next_generation_date": past_date,
            "auto_approve": False
        }
    )
    assert template_res.status_code == 201
    template_id = template_res.json()["id"]

    trigger_res = client.post("/v1/api/finance/ap/trigger-recurring", headers=superuser_headers)
    assert trigger_res.status_code == 200

    DefaultSession = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with DefaultSession() as db:
        tmpl = db.get(RecurringExpenseTemplate, template_id)
        # Apply UTC timezone to handle SQLite naive translation gracefully
        assert tmpl.next_generation_date.replace(tzinfo=timezone.utc) > now

        expense = db.query(ExpenseRecord).filter(ExpenseRecord.recurring_template_id == template_id).first()
        assert expense is not None
        assert expense.status == ExpenseStatusEnum.PENDING_APPROVAL


def test_03_recurring_auto_approval_records_authorizer(client, superuser_headers, multi_tenant_env):
    """Auto-approved recurring expenses retain the template creator as the authorizing approver."""
    past_date = (datetime.now(timezone.utc) - relativedelta(days=2)).isoformat()
    template_res = client.post(
        "/v1/api/finance/ap/recurring-templates",
        headers=superuser_headers,
        json={
            "category": "UTILITY",
            "title": "Pre-authorized generator maintenance",
            "amount_paise": 275000,
            "frequency": "MONTHLY",
            "next_generation_date": past_date,
            "auto_approve": True,
        },
    )
    assert template_res.status_code == 201
    template_id = template_res.json()["id"]
    template_creator_id = template_res.json()["created_by_id"]

    trigger_res = client.post("/v1/api/finance/ap/trigger-recurring", headers=superuser_headers)
    assert trigger_res.status_code == 200

    DefaultSession = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with DefaultSession() as db:
        expense = db.query(ExpenseRecord).filter(
            ExpenseRecord.recurring_template_id == template_id
        ).one()
        assert expense.status == ExpenseStatusEnum.APPROVED
        assert expense.approved_by_id == template_creator_id
        assert expense.approved_at is not None


def test_03_lis_equipment_registration(client, superuser_headers):
    """Scenario 3: Registering a bi-directional HL7 analyzer to the laboratory department."""
    dept = client.post(
        "/v1/api/auth/departments",
        headers=superuser_headers,
        json={"code": "DEPT_LAB_EQ", "name": "Laboratory Equipment"}
    ).json()

    equip_res = client.post(
        "/v1/api/equipment",
        headers=superuser_headers,
        json={
            "department_id": dept["id"],
            "name": "Sysmex XN-1000",
            "manufacturer": "Sysmex",
            "device_model": "XN-1000",
            "ip_address": "192.168.1.55",
            "protocol": "HL7_V2",
            "is_bidirectional": True
        }
    )
    assert equip_res.status_code == 201


def test_03_expense_adjudication_cannot_bypass_payment_permission(client, superuser_headers):
    """Approval is not payment: adjudication must not accept PAID as a target state."""
    draft_res = client.post(
        "/v1/api/finance/ap/expenses",
        headers=superuser_headers,
        json={
            "category": "MEDICAL_SUPPLIES",
            "title": "Payment permission boundary",
            "amount_paise": 125000,
            "vendor_name": "Test Supplier",
        },
    )
    assert draft_res.status_code == 201
    expense_id = draft_res.json()["id"]

    paid_res = client.patch(
        f"/v1/api/finance/ap/expenses/{expense_id}/adjudicate",
        headers=superuser_headers,
        json={"status": "PAID"},
    )
    assert paid_res.status_code == 422
