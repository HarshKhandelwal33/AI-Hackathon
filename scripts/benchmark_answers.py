"""Explicitly opt-in paid benchmark. Run once in each frozen revision."""
import argparse, json, subprocess, sys, time
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument("--allow-paid", action="store_true")
p.add_argument("--label", required=True)
a=p.parse_args()
if not a.allow_paid: p.error("Paid model requests require explicit --allow-paid approval")
out=Path(".runs") / a.label
out.mkdir(parents=True, exist_ok=False)
for q in json.loads(Path("benchmarks/questions.json").read_text()):
    started=time.perf_counter()
    run=subprocess.run([sys.executable,"-m","loglens.agent",q["role"],q["question"]],capture_output=True,text=True,timeout=300)
    record={**q,"seconds":time.perf_counter()-started,"answer":run.stdout,"telemetry":run.stderr,"exit_code":run.returncode,
            "human_scores": {k:None for k in ("retrieval","numbers","citations","reasoning","action")}}
    (out / (q["id"]+".json")).write_text(json.dumps(record,indent=2))
    if run.returncode: break
