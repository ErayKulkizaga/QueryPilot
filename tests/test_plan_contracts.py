import json
from pathlib import Path

from app.analysis.plan_contracts import (
    NamedPlanContract,
    PlanContractSet,
    evaluate_plan_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def _raw_plan(*, node_type: str, index_name: str | None = None) -> list[dict]:
    node = {
        "Node Type": node_type,
        "Relation Name": "customers",
        "Plan Rows": 1,
        "Actual Rows": 1,
        "Actual Loops": 1,
        "Total Cost": 8.31,
        "Actual Total Time": 0.03,
    }
    if index_name:
        node["Index Name"] = index_name
    return [{"Plan": node, "Planning Time": 0.1, "Execution Time": 0.05}]


def test_checked_in_plan_contracts_are_strict_and_named() -> None:
    payload = json.loads(
        (ROOT / "contracts" / "plan_contracts.json").read_text(encoding="utf-8")
    )

    contracts = PlanContractSet.model_validate(payload)

    assert len(contracts.contracts) >= 2
    assert len({contract.name for contract in contracts.contracts}) == len(
        contracts.contracts
    )
    assert all(contract.release == "v2" for contract in contracts.contracts)


def test_plan_contract_accepts_expected_index_access() -> None:
    contract = NamedPlanContract.model_validate(
        {
            "name": "healthy-lookup",
            "release": "v2",
            "sql": "SELECT * FROM customers WHERE id = 17",
            "expected_issue_category": "no_clear_issue",
            "expected_insufficient_context": True,
            "required_nodes": [
                {
                    "node_type": "Index Scan",
                    "relation_name": "customers",
                    "index_name": "customers_pkey",
                }
            ],
            "forbidden_nodes": [
                {"node_type": "Seq Scan", "relation_name": "customers"}
            ],
        }
    )

    result = evaluate_plan_contract(
        contract,
        issue_category="no_clear_issue",
        insufficient_context=True,
        raw_plan=_raw_plan(node_type="Index Scan", index_name="customers_pkey"),
    )

    assert result.passed is True
    assert result.errors == ()


def test_plan_contract_reports_access_path_and_category_regression() -> None:
    contract = NamedPlanContract.model_validate(
        {
            "name": "healthy-lookup",
            "release": "v2",
            "sql": "SELECT * FROM customers WHERE id = 17",
            "expected_issue_category": "no_clear_issue",
            "expected_insufficient_context": True,
            "required_nodes": [
                {
                    "node_type": "Index Scan",
                    "relation_name": "customers",
                    "index_name": "customers_pkey",
                }
            ],
            "forbidden_nodes": [
                {"node_type": "Seq Scan", "relation_name": "customers"}
            ],
        }
    )

    result = evaluate_plan_contract(
        contract,
        issue_category="potential_missing_index",
        insufficient_context=False,
        raw_plan=_raw_plan(node_type="Seq Scan"),
    )

    assert result.passed is False
    assert len(result.errors) == 4
    assert any("Required plan node missing" in error for error in result.errors)
    assert any("Forbidden plan node present" in error for error in result.errors)
