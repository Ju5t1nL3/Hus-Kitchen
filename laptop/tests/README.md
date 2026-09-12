# Laptop tests

Add behavioral tests here with the implementation task they verify. Keep contract,
domain, storage and application scenarios in separate files or subdirectories so
contributors do not all edit one shared test module.

Run every current laptop test from `laptop/`:

```sh
uv run python -m unittest discover -s tests -v
```

Contract tests read the repository-level `../contracts/` JSON Lines files also
used by firmware tests. Adapter tests use the in-memory clock, device and event
store in `src/deskpet/adapters/fakes.py`.
