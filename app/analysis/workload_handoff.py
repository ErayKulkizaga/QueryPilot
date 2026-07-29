import re

POSTGRES_PARAMETER_PATTERN = re.compile(r"\$\d+\b")


class RepresentativeSQLRequiredError(ValueError):
    """Raised when workload statistics do not contain executable sample SQL."""


def prepare_representative_sql(sql: str) -> str:
    representative_sql = sql.strip()
    if not representative_sql:
        raise RepresentativeSQLRequiredError(
            "Plan analysis requires a representative SQL statement."
        )
    if POSTGRES_PARAMETER_PATTERN.search(representative_sql):
        raise RepresentativeSQLRequiredError(
            "Replace every PostgreSQL parameter placeholder with a "
            "representative literal before plan analysis."
        )
    return representative_sql
