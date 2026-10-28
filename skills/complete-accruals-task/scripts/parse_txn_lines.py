#!/usr/bin/env python3
"""
parse_txn_lines.py — Parses Numeric transaction line TSV output into a vendor × month spend matrix.

Usage:
    python3 parse_txn_lines.py <txn_file_path> <output_json_path> [--entity-org-id <org_id>]

Input:  Path to the raw tool-results file (JSON array wrapping TSV text from query_transaction_lines)
Output: JSON file with structure:
    {
        "vendors": { "Vendor Name": { "YYYY-MM": amount, ... }, ... },
        "months": ["YYYY-MM", ...],
        "entity_filter_applied": "org_id=1" or "none",
        "total_rows_parsed": N,
        "total_rows_after_filter": N
    }
"""

import json
import os
import sys
import argparse
from collections import defaultdict


def _safe_path(raw):
    """Canonicalize a CLI-supplied path before file I/O; reject malformed input."""
    if not raw or "\x00" in str(raw):
        raise SystemExit(f"Refusing invalid path: {raw!r}")
    return os.path.realpath(raw)


def _require_root(raw, root):
    """Resolve a path and hard-require it to stay within the declared --root workspace."""
    resolved = _safe_path(raw)
    root_resolved = os.path.realpath(root)
    if os.path.commonpath([resolved, root_resolved]) != root_resolved:
        raise SystemExit(
            f"Refusing path outside --root: {raw!r} resolves to {resolved!r}, which is "
            f"not inside --root {root_resolved!r}. Copy/stage it into --root (the "
            f"skill's working directory) first."
        )
    return resolved


def parse_tsv_from_tool_result(file_path: str) -> list[dict]:
    """Read the JSON-wrapped TSV from a Numeric MCP tool result file.

    Caller must have already resolved `file_path` with _require_root before calling.
    """
    with open(file_path, "r") as f:
        raw = json.load(f)

    # The tool result is a JSON array: [{"type": "text", "text": "...TSV..."}]
    if isinstance(raw, list):
        text = raw[0].get("text", "")
    elif isinstance(raw, dict):
        text = raw.get("text", "")
    else:
        text = str(raw)

    lines = text.strip().split("\n")
    if len(lines) < 2:
        return []

    headers = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        fields = line.split("\t")
        if len(fields) == len(headers):
            rows.append(dict(zip(headers, fields)))
    return rows


def build_spend_matrix(
    rows: list[dict],
    entity_org_id: str | None = None,
) -> dict:
    """Group transaction rows by vendor × month, optionally filtering by entity."""

    # Filter by entity if specified
    if entity_org_id:
        filtered = [r for r in rows if r.get("organization_id", "") == entity_org_id]
    else:
        filtered = rows

    # Group by vendor × month
    vendor_months = defaultdict(lambda: defaultdict(float))
    all_months = set()

    for row in filtered:
        vendor = row.get("counterparty", row.get("vendor", "Unknown"))
        if not vendor or vendor.strip() == "":
            vendor = "Unknown"

        # Parse date to YYYY-MM
        date_str = row.get("date", row.get("posting_date", ""))
        if not date_str:
            continue

        # Handle various date formats
        if "/" in date_str:
            parts = date_str.split("/")
            if len(parts) == 3:
                month_key = f"{parts[2]}-{parts[0].zfill(2)}"
            else:
                continue
        elif "-" in date_str:
            parts = date_str.split("-")
            month_key = f"{parts[0]}-{parts[1].zfill(2)}"
        else:
            continue

        amount = float(row.get("normal_amount", row.get("amount", 0)) or 0)
        vendor_months[vendor][month_key] += amount
        all_months.add(month_key)

    # Sort months chronologically
    sorted_months = sorted(all_months)

    # Build final structure with zeros for missing months
    vendors_dict = {}
    for vendor in sorted(vendor_months.keys()):
        vendors_dict[vendor] = {m: round(vendor_months[vendor].get(m, 0), 2) for m in sorted_months}

    return {
        "vendors": vendors_dict,
        "months": sorted_months,
        "entity_filter_applied": f"org_id={entity_org_id}" if entity_org_id else "none",
        "total_rows_parsed": len(rows),
        "total_rows_after_filter": len(filtered),
    }


def main():
    parser = argparse.ArgumentParser(description="Parse Numeric transaction lines into vendor spend matrix")
    parser.add_argument("--root", required=True,
                         help="Working directory. txn_file and output_file must resolve under this directory.")
    parser.add_argument("txn_file", help="Path to the raw tool-results JSON file")
    parser.add_argument("output_file", help="Path for output JSON")
    parser.add_argument("--entity-org-id", help="Filter to this organization_id", default=None)
    args = parser.parse_args()

    root = os.path.realpath(args.root)
    os.makedirs(root, exist_ok=True)
    args.txn_file = _require_root(args.txn_file, root)
    args.output_file = _require_root(args.output_file, root)

    rows = parse_tsv_from_tool_result(args.txn_file)
    matrix = build_spend_matrix(rows, args.entity_org_id)

    with open(args.output_file, "w") as f:
        json.dump(matrix, f, indent=2)

    print(f"Parsed {matrix['total_rows_parsed']} rows, {matrix['total_rows_after_filter']} after filter")
    print(f"Found {len(matrix['vendors'])} vendors across {len(matrix['months'])} months")
    print(f"Output: {args.output_file}")


if __name__ == "__main__":
    main()
