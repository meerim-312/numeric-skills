"""
Parse Numeric workspace context into lightweight lookups.

Input: path to the raw MCP tool-result file (JSON array [{type, text}])
Output: prints summary, saves to output_dir:
  - user_map.json: {user_id: {name, active}}
  - periods.json: [{id, slug, status, start, end, frequency_key}]

Usage: python3 parse_context.py <input_file> <output_dir> --root <work_dir>

<input_file> and <output_dir> must both resolve under --root — if <input_file> is a
harness-saved tool-result file outside the working directory, copy it into <work_dir>
first.
"""
import argparse
import json, sys, os


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


def parse(input_file, output_dir):
    """Caller must have already resolved input_file/output_dir with _require_root."""
    with open(input_file) as f:
        raw = json.load(f)
    ctx = json.loads(raw[0]["text"])

    user_map = {}
    for u in ctx.get("users", []):
        user_map[u["id"]] = {
            "name": u.get("name", u["id"]),
            "active": u.get("active", True),
        }

    periods = []
    for p in ctx.get("periods", []):
        s, e = p.get("start", {}), p.get("end", {})
        periods.append({
            "id": p["id"],
            "slug": p.get("slug", ""),
            "status": p.get("status", ""),
            "start": f"{s.get('year','')}-{s.get('month',1):02d}-{s.get('day',1):02d}",
            "end": f"{e.get('year','')}-{e.get('month',1):02d}-{e.get('day',1):02d}",
            "frequency_key": p.get("frequency_key", ""),
        })
    periods.sort(key=lambda x: x["start"])

    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "user_map.json"), "w") as f:
        json.dump(user_map, f, indent=2)
    with open(os.path.join(output_dir, "periods.json"), "w") as f:
        json.dump(periods, f, indent=2)

    print(f"Parsed {len(user_map)} users, {len(periods)} periods")
    closed = [p for p in periods if p["status"] == "closed"]
    open_p = [p for p in periods if p["status"] == "open"]
    print(f"  Closed: {len(closed)}, Open: {len(open_p)}")
    if closed:
        print(f"  Last closed: {closed[-1]['slug']} ({closed[-1]['id']})")
    if open_p:
        print(f"  Current open: {open_p[0]['slug']} ({open_p[0]['id']})")
    return user_map, periods


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input_file")
    ap.add_argument("output_dir")
    ap.add_argument("--root", required=True,
                     help="Working directory. input_file and output_dir must resolve under this directory.")
    args = ap.parse_args()

    root = os.path.realpath(args.root)
    os.makedirs(root, exist_ok=True)
    args.input_file = _require_root(args.input_file, root)
    args.output_dir = _require_root(args.output_dir, root)

    parse(args.input_file, args.output_dir)
