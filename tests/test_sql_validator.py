import pytest

from app.analysis.sql_validator import SQLValidationError, validate_read_only_sql


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM customers WHERE email = 'demo@example.com'",
        "WITH recent AS (SELECT * FROM orders) SELECT * FROM recent",
        "SELECT c.id FROM customers AS c JOIN orders AS o ON o.customer_id = c.id",
        "SELECT '; DROP TABLE customers' AS harmless_text",
        "SELECT 1 /* ; DROP TABLE customers */",
    ],
)
def test_accepts_read_only_queries(sql: str) -> None:
    normalized = validate_read_only_sql(sql)
    assert normalized


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM customers",
        "UPDATE customers SET email = 'x'",
        "INSERT INTO customers(email) VALUES ('x')",
        "DROP TABLE customers",
        "SELECT * INTO copied_customers FROM customers",
        "SELECT * FROM customers FOR UPDATE",
        "SELECT pg_sleep(10)",
        "SELECT 1; SELECT 2",
        "SELECT 1; DROP TABLE customers",
        "SELECT dangerous_security_definer()",
        "SELECT dblink_exec('DELETE FROM customers')",
        "WITH changed AS (DELETE FROM orders RETURNING *) SELECT * FROM changed",
    ],
)
def test_rejects_unsafe_queries(sql: str) -> None:
    with pytest.raises(SQLValidationError):
        validate_read_only_sql(sql)
