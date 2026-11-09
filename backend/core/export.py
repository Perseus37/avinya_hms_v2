"""Universal Streaming Data Export Utility for Avinya HMS.

Provides constant-memory O(1) streaming of tabular data in RFC 4180 compliant CSV
with UTF-8 Byte Order Mark (BOM) for native Microsoft Excel and Google Sheets compatibility.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Dict, Generator, Iterable, List, Optional, Sequence, Union
from urllib.parse import quote

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Query


def sanitize_spreadsheet_cell(val: str) -> str:
    """Neutralizes spreadsheet formula injection (CSV/Excel DDE injection).

    If text begins with =, +, -, @, \t, or \r, prefix with a single quote (')
    so that spreadsheet processors (Excel, Calc, Google Sheets) treat it strictly
    as text literal rather than executable formula/macro.
    Valid signed numeric strings (e.g. '-42', '+3.14', '-0.05') are preserved.
    """
    if not val:
        return val

    stripped = val.strip()
    if stripped.startswith(("-", "+")):
        try:
            float(stripped)
            return val
        except ValueError:
            pass

    if val[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{val}"
    return val


def format_export_cell(val: Any) -> str:
    """Formats Python types into clean, human-readable tabular text for CSV/Excel with formula injection neutralization."""
    if val is None:
        return ""
    if isinstance(val, bool):
        return "YES" if val else "NO"
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return f"{val:.2f}"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, (dict, list)):
        return sanitize_spreadsheet_cell(json.dumps(val, ensure_ascii=False))
    return sanitize_spreadsheet_cell(str(val))


def generate_csv_chunks(
    rows_generator: Iterable[Union[Dict[str, Any], Sequence[Any]]],
    fieldnames: Sequence[str],
    *,
    chunk_size: int = 250,
    field_transformer: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
) -> Generator[str, None, None]:
    """
    Yields CSV text chunks starting with UTF-8 BOM.
    Constant memory overhead: buffer is flushed and cleared every chunk_size rows.
    """
    buffer = io.StringIO()
    # UTF-8 BOM so Microsoft Excel automatically recognizes UTF-8 (including ₹ symbol, accents)
    buffer.write("\ufeff")

    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow(fieldnames)
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    count = 0
    for row in rows_generator:
        if isinstance(row, dict):
            if field_transformer:
                row = field_transformer(row)
            formatted_row = [format_export_cell(row.get(col, "")) for col in fieldnames]
        else:
            formatted_row = [format_export_cell(c) for c in row]

        writer.writerow(formatted_row)
        count += 1
        if count >= chunk_size:
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            count = 0

    if buffer.tell() > 0:
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)


def stream_csv_response(
    rows_generator: Iterable[Union[Dict[str, Any], Sequence[Any]]],
    fieldnames: Sequence[str],
    filename: str,
    *,
    chunk_size: int = 250,
    field_transformer: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
) -> StreamingResponse:
    """Wraps CSV chunk generator in a FastAPI StreamingResponse with proper Content-Disposition."""
    safe_filename = filename if filename.lower().endswith(".csv") else f"{filename}.csv"
    encoded_filename = quote(safe_filename)

    return StreamingResponse(
        generate_csv_chunks(
            rows_generator=rows_generator,
            fieldnames=fieldnames,
            chunk_size=chunk_size,
            field_transformer=field_transformer,
        ),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{encoded_filename}',
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


def stream_jsonl_response(
    records_generator: Iterable[Dict[str, Any]],
    filename: str,
) -> StreamingResponse:
    """Streams records as newline-delimited JSON (NDJSON) for data science / ETL pipelines."""
    safe_filename = filename if filename.lower().endswith(".jsonl") else f"{filename}.jsonl"
    encoded_filename = quote(safe_filename)

    def jsonl_generator() -> Generator[str, None, None]:
        for rec in records_generator:
            yield json.dumps(rec, default=format_export_cell, ensure_ascii=False) + "\n"

    return StreamingResponse(
        jsonl_generator(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{encoded_filename}',
            "Cache-Control": "no-cache",
        },
    )


def chunked_query_fetcher(
    query: Query,
    chunk_size: int = 500,
    max_rows: Optional[int] = None,
) -> Generator[Any, None, None]:
    """Safely iterates through an ORM query in batches without loading all results into RAM.

    Uses offset/limit windowing with an optional max_rows safety ceiling.
    """
    offset = 0
    total_yielded = 0
    while True:
        limit = chunk_size
        if max_rows is not None:
            remaining = max_rows - total_yielded
            if remaining <= 0:
                break
            limit = min(limit, remaining)

        batch = query.offset(offset).limit(limit).all()
        if not batch:
            break
        for item in batch:
            yield item
            total_yielded += 1
            if max_rows is not None and total_yielded >= max_rows:
                return
        if len(batch) < limit:
            break
        offset += len(batch)

