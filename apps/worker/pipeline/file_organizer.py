from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from apps.worker.pipeline.config import OUTPUT_ROOT


def _safe_slug(value: str, max_len: int = 60) -> str:
    value = value.strip()
    value = re.sub(r"[^A-Za-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value)
    value = value.strip("_")
    if len(value) > max_len:
        value = value[:max_len]
    return value or "Invoice"


def build_target_path(
    *,
    original_path: Path,
    vendor: Optional[str],
    date: Optional[str],
    category: Optional[str],
) -> Path:
    """
    Build a new path under OUTPUT_ROOT / YYYY / MM / Category / filename.ext
    """
    suffix = original_path.suffix.lower()
    today = datetime.utcnow().date()

    # Year / Month folders
    year = None
    month = None
    if date:
        try:
            dt = datetime.fromisoformat(date)
            year = dt.year
            month = dt.month
        except Exception:
            pass

    year = year or today.year
    month = month or today.month

    year_dir = OUTPUT_ROOT / f"{year:04d}"
    month_dir = year_dir / f"{month:02d}"

    cat = (category or "Uncategorized").strip() or "Uncategorized"
    cat_slug = _safe_slug(cat)

    base_dir = month_dir / cat_slug
    base_dir.mkdir(parents=True, exist_ok=True)

    vendor_slug = _safe_slug(vendor or "Vendor")
    date_part = date or today.strftime("%Y-%m-%d")

    base_name = f"{vendor_slug}_{date_part}_{cat_slug}"
    target = base_dir / f"{base_name}{suffix}"

    # Avoid overwriting existing files – add -1, -2, ...
    counter = 1
    while target.exists():
        target = base_dir / f"{base_name}-{counter}{suffix}"
        counter += 1

    return target


def move_invoice_file(
    original_path: Path,
    vendor: Optional[str],
    date: Optional[str],
    category: Optional[str],
) -> Path:
    """Move the invoice file into the organized tree and return the new path."""
    target = build_target_path(
        original_path=original_path, vendor=vendor, date=date, category=category
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(original_path), str(target))
    return target