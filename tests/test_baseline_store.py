from app.analysis.plan_comparator import snapshot_plan
from app.analysis.plan_parser import parse_explain
from app.baseline_store import BaselineNotFoundError, SQLiteBaselineStore


def _snapshot():
    return snapshot_plan(
        parse_explain(
            [
                {
                    "Plan": {
                        "Node Type": "Seq Scan",
                        "Relation Name": "customers",
                        "Plan Rows": 10,
                        "Actual Rows": 10,
                        "Actual Loops": 1,
                        "Total Cost": 20,
                        "Actual Total Time": 3,
                    },
                    "Planning Time": 0.5,
                    "Execution Time": 3,
                }
            ]
        )
    )


def test_sqlite_store_persists_and_lists_baselines(tmp_path) -> None:
    database_path = tmp_path / "baselines.sqlite3"
    store = SQLiteBaselineStore(database_path)

    created = store.create(
        name="customer lookup",
        query_fingerprint="a" * 64,
        normalized_sql="SELECT * FROM customers",
        plan=_snapshot(),
        sample_count=3,
    )
    reopened = SQLiteBaselineStore(database_path)

    loaded = reopened.get(created.baseline_id)
    listed = reopened.list()

    assert loaded == created
    assert listed == [created]
    assert loaded.sample_count == 3


def test_sqlite_store_rejects_unknown_baseline(tmp_path) -> None:
    store = SQLiteBaselineStore(tmp_path / "baselines.sqlite3")

    try:
        store.get("missing")
    except BaselineNotFoundError:
        pass
    else:
        raise AssertionError("Unknown baseline ID should be rejected.")


def test_sqlite_store_applies_retention_and_supports_delete(tmp_path) -> None:
    store = SQLiteBaselineStore(
        tmp_path / "baselines.sqlite3",
        max_items=2,
    )
    created = [
        store.create(
            name=f"baseline-{index}",
            query_fingerprint=str(index) * 64,
            normalized_sql=f"SELECT {index}",
            plan=_snapshot(),
            sample_count=1,
        )
        for index in range(3)
    ]

    retained = store.list()

    assert len(retained) == 2
    assert created[0].baseline_id not in {
        baseline.baseline_id for baseline in retained
    }

    store.delete(created[2].baseline_id)

    assert [baseline.baseline_id for baseline in store.list()] == [
        created[1].baseline_id
    ]
