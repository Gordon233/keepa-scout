import pytest
from app.services.sql_guard import UnsafeSqlError, ensure_safe


# --- PASS cases ---

def test_simple_select():
    ensure_safe("SELECT * FROM asins")


def test_select_with_where():
    ensure_safe("SELECT asin, computed_roi_pct FROM asins WHERE eligible = 1")


def test_select_trailing_semicolon():
    ensure_safe("SELECT * FROM asins;")


def test_select_keyword_in_string_literal():
    """DELETE inside a LIKE string should NOT trigger rejection."""
    ensure_safe("SELECT * FROM asins WHERE title LIKE '%DELETE%'")


def test_select_keyword_in_value():
    """'Drop Stop' is a string value, not a keyword."""
    ensure_safe("SELECT * FROM asins WHERE brand = 'Drop Stop'")


# --- REJECT cases ---

def test_reject_drop_table():
    with pytest.raises(UnsafeSqlError):
        ensure_safe("DROP TABLE asins")


def test_reject_delete():
    with pytest.raises(UnsafeSqlError):
        ensure_safe("DELETE FROM asins")


def test_reject_insert():
    with pytest.raises(UnsafeSqlError):
        ensure_safe("INSERT INTO asins VALUES ('X')")


def test_reject_update():
    with pytest.raises(UnsafeSqlError):
        ensure_safe("UPDATE asins SET eligible = 0")


def test_reject_create():
    with pytest.raises(UnsafeSqlError):
        ensure_safe("CREATE TABLE evil (id INT)")


def test_reject_multiple_statements():
    with pytest.raises(UnsafeSqlError):
        ensure_safe("SELECT 1; DROP TABLE asins")


def test_reject_attach():
    with pytest.raises(UnsafeSqlError):
        ensure_safe("ATTACH DATABASE '/etc/passwd' AS pwn")


def test_reject_pragma():
    with pytest.raises(UnsafeSqlError):
        ensure_safe("PRAGMA table_info(asins)")


def test_reject_empty():
    with pytest.raises(UnsafeSqlError):
        ensure_safe("")
