"""
Typed field schema for the finance vault.
Each category defines its fields, each field has a data type and a
sensitivity tag used later for risk weighting.

Sensitivity levels:
  - "high"   : direct PII or highly confidential (salary, credit limit, valuation)
  - "medium" : indirectly sensitive (department, transaction type, growth forecast)
  - "low"    : contextual/non-sensitive on its own (announcement date, manager name)
"""

VAULT_SCHEMA = {
    "employee_compensation": {
        "fields": {
            "salary": {"type": "currency", "sensitivity": "high"},
            "bonus": {"type": "currency", "sensitivity": "high"},
            "department": {"type": "text", "sensitivity": "low"},
            "manager": {"type": "text", "sensitivity": "low"},
            "joining_date": {"type": "date", "sensitivity": "medium"},
        }
    },
    "customer_financial_records": {
        "fields": {
            "income": {"type": "currency", "sensitivity": "high"},
            "credit_limit": {"type": "currency", "sensitivity": "high"},
            "outstanding_balance": {"type": "currency", "sensitivity": "high"},
            "risk_score": {"type": "number", "sensitivity": "medium"},
        }
    },
    "corporate_transactions": {
        "fields": {
            "transaction_amount": {"type": "currency", "sensitivity": "high"},
            "client": {"type": "text", "sensitivity": "medium"},
            "transaction_type": {"type": "text", "sensitivity": "low"},
            "date": {"type": "date", "sensitivity": "low"},
            "approver": {"type": "text", "sensitivity": "low"},
        }
    },
    "internal_financial_reports": {
        "fields": {
            "revenue": {"type": "currency", "sensitivity": "high"},
            "expenses": {"type": "currency", "sensitivity": "high"},
            "profit": {"type": "currency", "sensitivity": "high"},
            "growth_forecast": {"type": "percentage", "sensitivity": "medium"},
        }
    },
    "confidential_deal_information": {
        "fields": {
            "acquisition_price": {"type": "currency", "sensitivity": "high"},
            "valuation": {"type": "currency", "sensitivity": "high"},
            "expected_synergy": {"type": "text", "sensitivity": "medium"},
            "announcement_date": {"type": "date", "sensitivity": "medium"},
        }
    },
}


def get_categories():
    """Return list of all vault category names."""
    return list(VAULT_SCHEMA.keys())


def get_fields(category):
    """Return the field definitions for a given category."""
    if category not in VAULT_SCHEMA:
        raise ValueError(f"Unknown vault category: {category}")
    return VAULT_SCHEMA[category]["fields"]


def get_sensitivity(category, field_name):
    """Return the sensitivity level ('high'/'medium'/'low') for a field."""
    fields = get_fields(category)
    if field_name not in fields:
        raise ValueError(f"Unknown field '{field_name}' in category '{category}'")
    return fields[field_name]["sensitivity"]