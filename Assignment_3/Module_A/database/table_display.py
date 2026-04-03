"""B+ Tree table display helpers for notebooks and terminal output.

Renders the contents of one or more tables stored in a DatabaseManager as
formatted ASCII / Markdown tables. Works in both IPython notebook contexts
(via ``snapshot_for_ipython``) and plain terminal output (via ``print()``).

Design notes:
- Reads are done outside any transaction via ``Table.get_all()``. Call these
  helpers *after* a commit or rollback so the snapshot reflects a consistent
  committed state.
- Column ordering follows the table's schema key order (stable insertion
  order from Python 3.7+).
- No dependency on IPython at import time; the notebook helper imports it
  lazily and falls back to a plain string when unavailable.
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
# Formatters
# ---------------------------------------------------------------------------

def format_table(
    rows: List[Tuple[Any, Dict[str, Any]]],
    columns: Optional[List[str]] = None,
    title: Optional[str] = None,
    max_rows: Optional[int] = None,
    predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
) -> str:
    """Render ``(key, record)`` pairs as a fixed-width ASCII / Markdown table.

    Args:
        rows: Output of ``read_table_rows()`` or ``Table.get_all()``.
        columns: Column names to display and their order. ``None`` infers the
            order from the first row's dictionary keys (i.e., schema order).
        title: Optional heading printed above the table border.
        max_rows: Truncate to at most this many rows; appends a note when rows
            are omitted.
        predicate: Optional ``(record) -> bool`` filter applied before
            rendering. Only rows where ``predicate(record)`` is ``True`` are
            shown.

    Returns:
        A multi-line string suitable for ``print()`` or
        ``IPython.display.Markdown``.
    """
    if predicate is not None:
        rows = [(k, v) for k, v in rows if predicate(v)]

    truncated = 0
    if max_rows is not None and len(rows) > max_rows:
        truncated = len(rows) - max_rows
        rows = rows[:max_rows]

    header_line = f"\n### {title}\n" if title else ""

    if not rows:
        return f"{header_line}*(no rows)*\n"

    if columns is None:
        columns = list(rows[0][1].keys())

    col_widths = {
        col: max(len(col), max((len(str(row.get(col, ""))) for _, row in rows), default=0))
        for col in columns
    }

    sep = "+-" + "-+-".join("-" * col_widths[c] for c in columns) + "-+"

    def _header() -> str:
        return "| " + " | ".join(col.ljust(col_widths[col]) for col in columns) + " |"

    def _row(record: Dict[str, Any]) -> str:
        return "| " + " | ".join(str(record.get(col, "")).ljust(col_widths[col]) for col in columns) + " |"

    lines: List[str] = []
    if title:
        lines.append(f"\n### {title}")
    lines.append(sep)
    lines.append(_header())
    lines.append(sep)
    for _, record in rows:
        lines.append(_row(record))
    lines.append(sep)
    if truncated:
        lines.append(f"*... {truncated} more row(s) not shown*")
    lines.append("")

    return "\n".join(lines)


def format_database_tables(
    dbm: DatabaseManager,
    db_name: str,
    table_names: Optional[Iterable[str]] = None,
    max_rows: Optional[int] = None,
    predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
) -> str:
    """Render all (or selected) tables in *db_name* as concatenated ASCII tables.

    Args:
        dbm: The DatabaseManager holding the tables.
        db_name: Logical database name.
        table_names: Tables to render. Defaults to all tables in the database.
        max_rows: Per-table row cap passed to ``format_table``.
        predicate: Optional row filter applied to every table.

    Returns:
        Multi-line string with one table block per table. Suitable for
        ``print()`` or ``IPython.display.Markdown``.
    """
    if table_names is None:
        names, msg = dbm.list_tables(db_name)
        if not names and msg != "OK":
            return f"*(database '{db_name}' not found)*\n"
    else:
        names = list(table_names)

    parts: List[str] = [f"\n## Snapshot: `{db_name}`\n"]
    for name in names:
        try:
            rows = read_table_rows(dbm, db_name, name)
        except ValueError as exc:
            parts.append(f"\n### {name}\n*(error: {exc})*\n")
            continue
        parts.append(format_table(rows, title=name, max_rows=max_rows, predicate=predicate))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# IPython helper
# ---------------------------------------------------------------------------

def snapshot_for_ipython(
    dbm: DatabaseManager,
    db_name: str,
    table_names: Optional[Iterable[str]] = None,
    max_rows: Optional[int] = None,
    predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
) -> Any:
    """Return an ``IPython.display.Markdown`` object for rich notebook rendering.

    Falls back to a plain string when IPython is not installed. Use inside
    a notebook cell like::

        display(snapshot_for_ipython(dbm, "campus"))

    Or for a subset of tables after a specific step::

        display(snapshot_for_ipython(dbm, "campus", ["Offer", "Listing"]))
    """
    text = format_database_tables(
        dbm, db_name,
        table_names=table_names,
        max_rows=max_rows,
        predicate=predicate,
    )
    try:
        from IPython.display import Markdown  # type: ignore[import]
        return Markdown(text)
    except ImportError:
        return text
