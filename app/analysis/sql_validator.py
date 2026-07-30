from collections.abc import Iterable

from sqlglot import exp, parse
from sqlglot.errors import ParseError


class SQLValidationError(ValueError):
    """Raised when SQL is malformed or outside the read-only policy."""


_FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.Alter,
    exp.Command,
    exp.Copy,
    exp.Create,
    exp.Delete,
    exp.Drop,
    exp.Insert,
    exp.Into,
    exp.Lock,
    exp.Merge,
    exp.Set,
    exp.Transaction,
    exp.TruncateTable,
    exp.Update,
    exp.Use,
)

_SIDE_EFFECT_FUNCTIONS = {
    "dblink_exec",
    "lo_export",
    "lo_import",
    "nextval",
    "pg_advisory_lock",
    "pg_advisory_xact_lock",
    "pg_cancel_backend",
    "pg_notify",
    "pg_reload_conf",
    "pg_rotate_logfile",
    "pg_sleep",
    "pg_terminate_backend",
    "set_config",
    "setval",
}


def _function_names(statement: exp.Expression) -> Iterable[str]:
    for function in statement.find_all(exp.Func):
        if isinstance(function, exp.Anonymous):
            yield function.name.lower()
        else:
            yield function.sql_name().lower()


def validate_read_only_sql(sql: str) -> str:
    if not sql or not sql.strip():
        raise SQLValidationError("SQL must not be empty.")

    try:
        statements = [statement for statement in parse(sql, read="postgres") if statement]
    except ParseError as exc:
        raise SQLValidationError("SQL could not be parsed as PostgreSQL.") from exc

    if len(statements) != 1:
        raise SQLValidationError("Exactly one SQL statement is allowed.")

    statement = statements[0]
    if not isinstance(statement, exp.Query):
        raise SQLValidationError("Only SELECT or WITH ... SELECT queries are allowed.")

    forbidden = next(
        (node for node in statement.walk() if isinstance(node, _FORBIDDEN_NODES)),
        None,
    )
    if forbidden is not None:
        raise SQLValidationError(
            f"Read-only policy rejected SQL node: {forbidden.key.upper()}."
        )

    side_effect = next(
        (name for name in _function_names(statement) if name in _SIDE_EFFECT_FUNCTIONS),
        None,
    )
    if side_effect is not None:
        raise SQLValidationError(
            f"Function {side_effect} is not allowed in analyzed queries."
        )

    unsupported_function = next(statement.find_all(exp.Anonymous), None)
    if unsupported_function is not None:
        raise SQLValidationError(
            "User-defined or unsupported functions are not allowed in analyzed queries."
        )

    return statement.sql(dialect="postgres", pretty=False)
