"""CAN-016b: dataset import utilities.

Parses CSV bytes (from a multipart upload or a fetched URL) into the
``(inputs, targets)`` numpy-array pair that ``DemoMode.import_dataset``
expects. Kept out of ``main.py`` so the parsing logic is unit-testable
without spinning up FastAPI.

Format expected:
- Comma-separated values (CSV)
- All columns numeric
- Last column = integer class label
- All preceding columns = float features
- An optional header row is auto-detected by attempting to parse the first
  row as floats — non-parseable → treated as header and skipped.

Limits enforced here (not just at the HTTP layer) so reuse is safe:
- ``MAX_FILE_BYTES`` cap on raw input size (default 10 MB)
- ``MAX_ROWS`` cap on row count (default 50,000)
- ``MAX_FEATURES`` cap on feature columns (default 100)

Out of scope for this version:
- String / categorical labels (last column must be numeric)
- Missing values (each row must have the full feature count)
- TSV, JSON, parquet, NPZ — CSV only
"""

from __future__ import annotations

import csv
import io
from typing import Tuple

import numpy as np

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_ROWS = 50_000
MAX_FEATURES = 100


class DatasetImportError(ValueError):
    """Raised when uploaded/fetched bytes can't be parsed into a dataset."""


def parse_csv_bytes(raw: bytes, *, max_bytes: int = MAX_FILE_BYTES) -> Tuple[np.ndarray, np.ndarray]:
    """Parse CSV bytes into ``(inputs_float32, targets_int64)``.

    Raises ``DatasetImportError`` with a user-facing message on any parse
    issue — the caller (HTTP route or test) surfaces it directly. Internal
    error details (stack traces, etc.) are not embedded in the message.
    """
    if not isinstance(raw, (bytes, bytearray)):
        raise DatasetImportError("Expected bytes payload")
    if len(raw) == 0:
        raise DatasetImportError("Uploaded file is empty")
    if len(raw) > max_bytes:
        raise DatasetImportError(f"File too large: {len(raw)} bytes (limit {max_bytes})")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DatasetImportError(f"File is not valid UTF-8 text: {exc.reason}") from exc

    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader if row and any(cell.strip() for cell in row)]
    if not rows:
        raise DatasetImportError("CSV contained no non-empty rows")

    # Header auto-detection: try parsing the first row's values as floats.
    # If any cell can't, treat row as header and skip.
    if _looks_like_header(rows[0]):
        rows = rows[1:]
        if not rows:
            raise DatasetImportError("CSV header found but no data rows")

    if len(rows) > MAX_ROWS:
        raise DatasetImportError(f"Too many rows: {len(rows)} (limit {MAX_ROWS})")

    n_cols = len(rows[0])
    if n_cols < 2:
        raise DatasetImportError("Need at least 2 columns: feature(s) + label")
    if n_cols - 1 > MAX_FEATURES:
        raise DatasetImportError(f"Too many feature columns: {n_cols - 1} (limit {MAX_FEATURES})")

    inputs = np.empty((len(rows), n_cols - 1), dtype=np.float32)
    targets = np.empty(len(rows), dtype=np.int64)

    for i, row in enumerate(rows):
        if len(row) != n_cols:
            raise DatasetImportError(f"Row {i + 1} has {len(row)} columns; expected {n_cols} (matching first data row)")
        try:
            for j in range(n_cols - 1):
                inputs[i, j] = float(row[j].strip())
        except ValueError as exc:
            raise DatasetImportError(f"Row {i + 1}: feature column not numeric — {exc}") from exc
        try:
            label_val = float(row[-1].strip())
        except ValueError as exc:
            raise DatasetImportError(f"Row {i + 1}: label column not numeric — {exc}") from exc
        if label_val != int(label_val):
            raise DatasetImportError(f"Row {i + 1}: label {row[-1]!r} is not an integer (last column must be a class index)")
        targets[i] = int(label_val)

    if int(targets.min()) < 0:
        raise DatasetImportError("Class labels must be non-negative integers")

    return inputs, targets


def _looks_like_header(row: list[str]) -> bool:
    """Return True if EVERY cell is non-numeric.

    Mixed-numeric rows (e.g. ``0.1,abc,0``) are NOT headers — they're data
    with a stringy error, and the caller should surface that as a parse
    error rather than silently dropping the row.
    """
    for cell in row:
        try:
            float(cell.strip())
        except ValueError:
            continue
        # At least one cell parses as a float → not a pure header row.
        return False
    return True
