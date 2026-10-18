"""Conservative deterministic citation checks, not factual verification."""
import re

def validate_answer(answer, evidence):
    known = {}
    def visit(value):
        if isinstance(value, dict):
            if "evidence_id" in value:
                known[value["evidence_id"]] = value
            for child in value.values(): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
    visit(evidence)
    cited = set(re.findall(r"E-[A-Za-z0-9_-]+", answer))
    unknown = sorted(cited - known.keys())
    warnings = []
    if unknown: warnings.append("Unknown citation IDs: " + ", ".join(unknown))
    # Only compare an unambiguous single-row count; grouped totals need claim-level review.
    for number, eid in re.findall(r"([\d,]+) log rows?\s*\[(E-[a-f0-9]+)\]", answer):
        item = known.get(eid, {})
        rows = item.get("rows", [])
        if isinstance(rows, dict):
            rows = [dict(zip(rows["columns"], row)) for row in rows["values"]]
        counts = [r["log_count"] for r in rows if "log_count" in r]
        if len(counts) == 1 and int(number.replace(",", "")) != counts[0]:
            warnings.append("Log count mismatch for " + eid)
    return {"warnings": warnings, "limitations": "Checks citation existence and directly cited single-row log counts only; citation support, other numbers, causes and role usefulness require review."}

def annotate(answer, evidence):
    result = validate_answer(answer, evidence)
    import sys, json
    print("[validation] " + json.dumps(result), file=sys.stderr)
    if result["warnings"]:
        return answer + "\n\nEvidence validation warnings: " + "; ".join(result["warnings"])
    return answer
