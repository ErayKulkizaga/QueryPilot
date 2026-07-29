import pytest

from app.analysis.workload_handoff import (
    RepresentativeSQLRequiredError,
    prepare_representative_sql,
)


def test_representative_sql_rejects_postgresql_placeholders() -> None:
    with pytest.raises(
        RepresentativeSQLRequiredError,
        match="Replace every PostgreSQL parameter placeholder",
    ):
        prepare_representative_sql(
            "SELECT count(*) FROM orders WHERE total_amount > $1"
        )


def test_representative_sql_rejects_blank_input() -> None:
    with pytest.raises(
        RepresentativeSQLRequiredError,
        match="requires a representative SQL statement",
    ):
        prepare_representative_sql("   ")


def test_representative_sql_accepts_reviewable_literal_values() -> None:
    sql = " SELECT count(*) FROM orders WHERE total_amount > 250.00 "

    assert prepare_representative_sql(sql) == (
        "SELECT count(*) FROM orders WHERE total_amount > 250.00"
    )
