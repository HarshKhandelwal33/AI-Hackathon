# Response-quality benchmark

Run the 15 questions in questions.json with the agent and save each answer, elapsed time,
model name and executed tool evidence. Live runs send selected evidence to the configured provider.
No benchmark answers have been scored yet.

Score each answer 0 (fails), 1 (partial), or 2 (passes) for each criterion:
- Retrieval: relevant dataset, scope and evidence; negative search handled honestly.
- Numbers: match executed aggregations, not sample sizes; log rows distinguished from incidents.
- Citations: every material factual claim references an existing evidence ID and supporting result.
- Reasoning: observed facts separated from hypotheses; competing explanation and a discriminating check.
- Action: concrete role-appropriate next step; unknown ownership and impact acknowledged.

Compare total /10 and elapsed seconds before and after changes with the same database,
question and model. A human must verify citation support and numeric correctness; headings
alone do not prove quality. Target zero fabricated numbers or references.

Enrichment:
`python scripts/enrich_logs.py --ownership ownership.csv` imports genuine mapping columns
`dataset,component,team`. No invented team assignments are supplied.
`python scripts/enrich_logs.py --templates openstack --limit 10000` fills missing templates
in bounded batches. Repeat for remaining rows and BGL. Templates are explicitly heuristic:
UUIDs, hex addresses and timestamps are masked; error codes and ordinary numbers remain.
Partial coverage must be disclosed and these templates are not incident identifiers.
