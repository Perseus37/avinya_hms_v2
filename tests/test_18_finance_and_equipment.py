from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import sessionmaker

from backend.domains.identity.models import User

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


def test_04_expense_adjudication_and_payment_are_single_transitions(
    client, superuser_headers, multi_tenant_env
):
    """Repeated adjudication/payment attempts cannot overwrite a completed state."""
    draft_res = client.post(
        "/v1/api/finance/ap/expenses",
        headers=superuser_headers,
        json={
            "category": "UTILITY",
            "title": "Single transition guard",
            "amount_paise": 99000,
            "vendor_name": "Concurrency Test Supplier",
        },
    )
    assert draft_res.status_code == 201
    expense_id = draft_res.json()["id"]

    DefaultSession = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with DefaultSession() as db:
        doctor = db.query(User).filter(User.email == "doctor@default.com").one()
        expense = db.get(ExpenseRecord, expense_id)
        expense.created_by_id = doctor.id
        db.commit()

    approval = client.patch(
        f"/v1/api/finance/ap/expenses/{expense_id}/adjudicate",
        headers=superuser_headers,
        json={"status": "APPROVED"},
    )
    assert approval.status_code == 200

    repeated_approval = client.patch(
        f"/v1/api/finance/ap/expenses/{expense_id}/adjudicate",
        headers=superuser_headers,
        json={"status": "REJECTED", "rejection_reason": "Late review"},
    )
    assert repeated_approval.status_code == 409

    payment = client.post(
        f"/v1/api/finance/ap/expenses/{expense_id}/mark-paid",
        headers=superuser_headers,
        params={"receipt_reference": "BANK-REF-ONCE"},
    )
    assert payment.status_code == 200

    repeated_payment = client.post(
        f"/v1/api/finance/ap/expenses/{expense_id}/mark-paid",
        headers=superuser_headers,
        params={"receipt_reference": "BANK-REF-TWICE"},
    )
    assert repeated_payment.status_code == 400

def test_mark_expense_paid_validates_and_normalizes_receipt_reference(client, superuser_headers, multi_tenant_env):
    draft = client.post(
        "/v1/api/finance/ap/expenses",
        headers=superuser_headers,
        json={"category": "UTILITY", "title": "Receipt validation", "amount_paise": 12000},
    )
    assert draft.status_code == 201
    expense_id = draft.json()["id"]

    DefaultSession = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with DefaultSession() as db:
        doctor = db.query(User).filter(User.email == "doctor@default.com").one()
        expense = db.get(ExpenseRecord, expense_id)
        expense.created_by_id = doctor.id
        db.commit()

    approved = client.patch(
        f"/v1/api/finance/ap/expenses/{expense_id}/adjudicate",
        headers=superuser_headers,
        json={"status": "APPROVED"},
    )
    assert approved.status_code == 200

    blank = client.post(
        f"/v1/api/finance/ap/expenses/{expense_id}/mark-paid",
        headers=superuser_headers,
        params={"receipt_reference": "   "},
    )
    assert blank.status_code == 422

    oversized = client.post(
        f"/v1/api/finance/ap/expenses/{expense_id}/mark-paid",
        headers=superuser_headers,
        params={"receipt_reference": "R" * 101},
    )
    assert oversized.status_code == 422

    paid = client.post(
        f"/v1/api/finance/ap/expenses/{expense_id}/mark-paid",
        headers=superuser_headers,
        params={"receipt_reference": "  BANK-REF-VALID  "},
    )
    assert paid.status_code == 200
    assert paid.json()["receipt_reference"] == "BANK-REF-VALID"


def test_expense_rejection_rejects_whitespace_only_reason(
    client, superuser_headers, multi_tenant_env
):
    draft = client.post(
        "/v1/api/finance/ap/expenses",
        headers=superuser_headers,
        json={
            "category": "UTILITY",
            "title": "Whitespace rejection reason test",
            "amount_paise": 25000,
            "vendor_name": "Reason Validation Vendor",
        },
    )
    assert draft.status_code == 201
    expense_id = draft.json()["id"]

    DefaultSession = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with DefaultSession() as db:
        doctor = db.query(User).filter(User.email == "doctor@default.com").one()
        expense = db.get(ExpenseRecord, expense_id)
        expense.created_by_id = doctor.id
        db.commit()

    rejected = client.patch(
        f"/v1/api/finance/ap/expenses/{expense_id}/adjudicate",
        headers=superuser_headers,
        json={"status": "REJECTED", "rejection_reason": "     "},
    )
    assert rejected.status_code == 400
    assert "mandatory" in rejected.json()["message"].lower()



def test_expense_amounts_cannot_exceed_database_integer_capacity(client, superuser_headers):
    """Expense and recurring templates reject values beyond PostgreSQL INTEGER."""
    too_large = 2_147_483_648
    expense = client.post(
        "/v1/api/finance/ap/expenses",
        headers=superuser_headers,
        json={"category": "UTILITY", "title": "Oversized expense", "amount_paise": too_large},
    )
    assert expense.status_code == 422

    recurring = client.post(
        "/v1/api/finance/ap/recurring-templates",
        headers=superuser_headers,
        json={
            "category": "UTILITY",
            "title": "Oversized recurring expense",
            "amount_paise": too_large,
            "frequency": "MONTHLY",
            "next_generation_date": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert recurring.status_code == 422
