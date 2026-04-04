"""B+ Tree table display helpers for notebooks and terminal output.

Renders the contents of one or more tables stored in a DatabaseManager as
pandas DataFrames (in notebooks) or plain CSV text (in terminals).

Design notes:
- Reads are done outside any transaction via ``Table.get_all()``. Call these
  helpers *after* a commit or rollback so the snapshot reflects a consistent
  committed state.
- Column ordering follows the table's schema key order (stable insertion
  order from Python 3.7+).
- ``snapshot_for_ipython`` displays each table as a styled pandas DataFrame
  directly in the notebook cell output.  It falls back to CSV text when
  pandas / IPython are unavailable.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .db_manager import DatabaseManager


# ---------------------------------------------------------------------------
# Low-level row reader
# ---------------------------------------------------------------------------

def read_table_rows(
    dbm: DatabaseManager,
    db_name: str,
    table_name: str,
) -> List[Tuple[Any, Dict[str, Any]]]:
    """Return all ``(key, record)`` pairs from *table_name*, sorted by key.

    Raises ``ValueError`` if the table or database does not exist.
    """
    table, msg = dbm.get_table(db_name, table_name)
    if table is None:
        raise ValueError(f"Cannot read '{db_name}.{table_name}': {msg}")
    return table.get_all()


# ---------------------------------------------------------------------------
# DataFrame conversion
# ---------------------------------------------------------------------------

def rows_to_dataframe(
    rows: List[Tuple[Any, Dict[str, Any]]],
    columns: Optional[List[str]] = None,
    predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
    max_rows: Optional[int] = None,
) -> "pd.DataFrame":  # type: ignore[name-defined]
    """Convert ``(key, record)`` pairs to a :class:`pandas.DataFrame`.

    Args:
        rows: Output of :func:`read_table_rows` or ``Table.get_all()``.
        columns: Ordered list of columns to include. ``None`` uses all columns
            from the first row (schema order).
        predicate: Optional row filter; only rows where ``predicate(record)``
            is ``True`` are included.
        max_rows: Cap on the number of rows returned.

    Returns:
        A :class:`pandas.DataFrame` with one row per record.  An empty
        DataFrame is returned when *rows* is empty.
    """
    import pandas as pd  # type: ignore[import]

    if predicate is not None:
        rows = [(k, v) for k, v in rows if predicate(v)]
    if max_rows is not None:
        rows = rows[:max_rows]

    if not rows:
        cols = columns or []
        return pd.DataFrame(columns=cols)

    if columns is None:
        columns = list(rows[0][1].keys())

    records = [{col: rec.get(col, "") for col in columns} for _, rec in rows]
    return pd.DataFrame(records, columns=columns)


def table_to_dataframe(
    dbm: DatabaseManager,
    db_name: str,
    table_name: str,
    columns: Optional[List[str]] = None,
    predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
    max_rows: Optional[int] = None,
) -> "pd.DataFrame":  # type: ignore[name-defined]
    """Read a single table and return it as a :class:`pandas.DataFrame`."""
    rows = read_table_rows(dbm, db_name, table_name)
    return rows_to_dataframe(rows, columns=columns, predicate=predicate, max_rows=max_rows)


# ---------------------------------------------------------------------------
# Plain-text CSV fallback (no pandas required)
# ---------------------------------------------------------------------------

def format_table_csv(
    rows: List[Tuple[Any, Dict[str, Any]]],
    columns: Optional[List[str]] = None,
    title: Optional[str] = None,
    predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
    max_rows: Optional[int] = None,
) -> str:
    """Render rows as a CSV block (header + data lines).  Used as a fallback
    when pandas is not available."""
    if predicate is not None:
        rows = [(k, v) for k, v in rows if predicate(v)]
    if max_rows is not None:
        rows = rows[:max_rows]

    heading = f"### {title}\n" if title else ""
    if not rows:
        return f"{heading}(no rows)\n"

    if columns is None:
        columns = list(rows[0][1].keys())

    lines = [",".join(columns)]
    for _, rec in rows:
        lines.append(",".join(str(rec.get(c, "")) for c in columns))
    return heading + "\n".join(lines) + "\n"


def format_database_tables(
    dbm: DatabaseManager,
    db_name: str,
    table_names: Optional[Iterable[str]] = None,
    max_rows: Optional[int] = None,
    predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
) -> str:
    """Return a plain-text CSV representation of all tables (terminal use).

    For rich notebook rendering use :func:`snapshot_for_ipython` instead.
    """
    if table_names is None:
        names, msg = dbm.list_tables(db_name)
        if not names and msg != "OK":
            return f"(database '{db_name}' not found)\n"
    else:
        names = list(table_names)

    parts: List[str] = [f"=== Snapshot: {db_name} ===\n"]
    for name in names:
        try:
            rows = read_table_rows(dbm, db_name, name)
        except ValueError as exc:
            parts.append(f"### {name}\n(error: {exc})\n")
            continue
        parts.append(format_table_csv(rows, title=name, max_rows=max_rows, predicate=predicate))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Notebook helper — renders each table as a pandas DataFrame
# ---------------------------------------------------------------------------

def snapshot_for_ipython(
    dbm: DatabaseManager,
    db_name: str,
    table_names: Optional[Iterable[str]] = None,
    max_rows: Optional[int] = None,
    predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
) -> None:
    """Display every table in *db_name* as a pandas DataFrame in the notebook.

    Each table is printed with a heading and rendered as a styled DataFrame
    using ``IPython.display.display``.  Falls back to CSV text output when
    pandas or IPython are unavailable.

    Usage::

        snapshot_for_ipython(dbm, "campus")

        # subset of tables
        snapshot_for_ipython(dbm, "campus", ["Offer", "Listing"])
    """
    if table_names is None:
        names, msg = dbm.list_tables(db_name)
        if not names and msg != "OK":
            print(f"(database '{db_name}' not found)")
            return
    else:
        names = list(table_names)

    try:
        import pandas as pd  # type: ignore[import]
        from IPython.display import display, HTML  # type: ignore[import]
        _pandas_ok = True
    except ImportError:
        _pandas_ok = False

    for name in names:
        try:
            rows = read_table_rows(dbm, db_name, name)
        except ValueError as exc:
            print(f"[{name}] error: {exc}")
            continue

        if _pandas_ok:
            display(HTML(f"<h4 style='margin-bottom:4px'>{name}</h4>"))
            df = rows_to_dataframe(rows, predicate=predicate, max_rows=max_rows)
            display(df)
        else:
            print(format_table_csv(rows, title=name, predicate=predicate, max_rows=max_rows))
