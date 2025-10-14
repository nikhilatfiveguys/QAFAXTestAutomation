# QAFAX Test Automation

This repository contains an MVP implementation of the Fax QA automation platform described in the engineering plan. It includes a
seeded fax negotiation simulator, a lightweight verification pipeline, and report generators that output JSON/CSV/HTML summaries
for each run.

## Getting Started

1. Ensure you have Python 3.11 or newer available.
2. Install runtime dependencies (only the Python standard library is required for the MVP).
3. Run the CLI with a reference and candidate document:

```bash
python -m app.main docs/samples/control_reference.txt docs/samples/control_candidate.txt \
  --iterations 3 --seed 42 --run-id demo
```

Reports are written to the `artifacts/` directory. The default configuration uses the `Brother_V34_33k6_ECM256` profile and the
`verify_policy.normal` policy; you can supply alternatives with `--profile` and `--policy`.

## Documentation

* [Engineering Plan](docs/ENGINEERING_PLAN.md)
