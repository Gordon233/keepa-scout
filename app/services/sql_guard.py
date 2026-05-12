"""SQL safety guard using parse-then-check strategy (not keyword scan).

This avoids false positives like:
    SELECT * FROM asins WHERE title LIKE '%DELETE%'
because DELETE appears as a string literal token, not a Keyword token.
"""

import sqlparse
from sqlparse.tokens import Keyword, Keyword as KW


class UnsafeSqlError(Exception):
    """Raised when SQL is deemed unsafe to execute."""


_DANGEROUS_KEYWORDS = {"ATTACH", "PRAGMA", "LOAD_EXTENSION"}

_DANGEROUS_TOKEN_TYPES = (
    sqlparse.tokens.Keyword,
    sqlparse.tokens.Keyword.DDL,
    sqlparse.tokens.Keyword.DML,
)


def ensure_safe(sql: str) -> None:
    """Raise UnsafeSqlError if *sql* is not a safe, single SELECT statement.

    Strategy: parse-then-check (NOT keyword scan).
    """
    sql = sql.strip()
    if not sql:
        raise UnsafeSqlError("Empty SQL")

    # Remove a single trailing semicolon for split counting purposes,
    # but keep original for parsing so sqlparse handles it correctly.
    statements = [s for s in sqlparse.split(sql) if s.strip()]
    if len(statements) > 1:
        raise UnsafeSqlError(
            f"Multiple statements detected ({len(statements)}); only a single SELECT is allowed"
        )

    parsed = sqlparse.parse(sql)[0]

    stmt_type = parsed.get_type()
    if stmt_type != "SELECT":
        raise UnsafeSqlError(
            f"Statement type '{stmt_type}' is not allowed; only SELECT is permitted"
        )

    # Walk every token and check for dangerous keywords by token type,
    # not by string matching — so literals are never confused with keywords.
    for token in parsed.flatten():
        if token.ttype in _DANGEROUS_TOKEN_TYPES:
            normalized = token.normalized.upper()
            if normalized in _DANGEROUS_KEYWORDS:
                raise UnsafeSqlError(
                    f"Dangerous keyword '{normalized}' is not allowed"
                )
