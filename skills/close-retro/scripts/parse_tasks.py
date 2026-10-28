"""
Parse Numeric list_tasks TSV output into structured JSON.

Input: path to raw MCP tool-result file (JSON array [{type, text}])
       max_tasks: optional cap on number of tasks to parse (default: all)
Output: saves to output_dir/tasks.json with:
  - total_tasks, by_status, by_task_type, assignees, due_date_coverage, tasks[]

Usage: python3 parse_tasks.py <input_file> <output_dir> [max_tasks] --root <work_dir>

<input_file> and <output_dir> must both resolve under --root — if <input_file> is a
harness-saved tool-result file outside the working directory, copy it into <work_dir>
first.
"""
import argparse
import json, sys, os, csv
from io import StringIO


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


def parse(input_file, output_dir, max_tasks=None):
    """Caller must have already resolved input_file/output_dir with _require_root."""
    with open(input_file) as f:
        raw = json.load(f)
    text = raw[0]["text"]

    lines = text.strip().split("\n")
    # First line is "N tasks", second is header, rest are data
    count_line = lines[0]
    total_reported = int(count_line.split()[0])

    if total_reported == 0:
        result = {
            "total_in_period": 0, "total_parsed": 0,
            "by_status": {}, "by_task_type": {}, "assignees": {},
            "due_date_coverage": {}, "tasks": [],
        }
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, "tasks.json"), "w") as f:
            json.dump(result, f, indent=2)
        print(f"0 tasks in period")
        return result

    reader = csv.DictReader(StringIO("\n".join(lines[1:])), delimiter="\t")
    tasks = []
    for i, row in enumerate(reader):
        if max_tasks and i >= max_tasks:
            break
        tasks.append({k: (v or "").strip() for k, v in row.items()})

    # Compute aggregates
    by_status = {"completed": 0, "partially_complete": 0, "pending": 0, "skipped_immaterial": 0}
    by_type = {}
    assignees = {}
    due_cov = {"tasks_with_prep_due": 0, "tasks_with_review_due": 0, "tasks_without_any_due": 0}

    for t in tasks:
        tt = t.get("task_type", "unknown")
        by_type[tt] = by_type.get(tt, 0) + 1

        ps, rs = t.get("prep_status", ""), t.get("review_status", "")
        if ps in ("SKIPPED", "IMMATERIAL") or rs in ("SKIPPED", "IMMATERIAL"):
            by_status["skipped_immaterial"] += 1
        elif ps == "COMPLETE" and rs == "COMPLETE":
            by_status["completed"] += 1
        elif ps == "COMPLETE" or rs == "COMPLETE":
            by_status["partially_complete"] += 1
        else:
            by_status["pending"] += 1

        has_pd = bool(t.get("prep_due", ""))
        has_rd = bool(t.get("review_due", ""))
        if has_pd: due_cov["tasks_with_prep_due"] += 1
        if has_rd: due_cov["tasks_with_review_due"] += 1
        if not has_pd and not has_rd: due_cov["tasks_without_any_due"] += 1

        for role, akey, skey in [
            ("prep", "prep_assignee", "prep_status"),
            ("review", "review_assignee", "review_status"),
        ]:
            name = t.get(akey, "")
            if not name:
                continue
            if name not in assignees:
                assignees[name] = {
                    "prep_assigned": 0, "prep_complete": 0,
                    "review_assigned": 0, "review_complete": 0,
                    "task_types": {},
                }
            a = assignees[name]
            a[f"{role}_assigned"] += 1
            if t.get(skey, "") == "COMPLETE":
                a[f"{role}_complete"] += 1
            a["task_types"][tt] = a["task_types"].get(tt, 0) + 1

    result = {
        "total_in_period": total_reported,
        "total_parsed": len(tasks),
        "by_status": by_status,
        "by_task_type": by_type,
        "assignees": assignees,
        "due_date_coverage": due_cov,
        "tasks": tasks,
    }

    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "tasks.json"), "w") as f:
        json.dump(result, f, indent=2)

    print(f"Parsed {len(tasks)} of {total_reported} tasks")
    print(f"  Status: {json.dumps(by_status)}")
    print(f"  Types: {json.dumps(by_type)}")
    print(f"  Assignees: {len(assignees)}")
    print(f"  Due dates: {due_cov['tasks_with_prep_due']} prep, {due_cov['tasks_with_review_due']} review, {due_cov['tasks_without_any_due']} without")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input_file")
    ap.add_argument("output_dir")
    ap.add_argument("max_tasks", nargs="?", default=None)
    ap.add_argument("--root", required=True,
                     help="Working directory. input_file and output_dir must resolve under this directory.")
    args = ap.parse_args()

    root = os.path.realpath(args.root)
    os.makedirs(root, exist_ok=True)
    args.input_file = _require_root(args.input_file, root)
    args.output_dir = _require_root(args.output_dir, root)

    max_t = int(args.max_tasks) if args.max_tasks is not None else None
    parse(args.input_file, args.output_dir, max_t)
