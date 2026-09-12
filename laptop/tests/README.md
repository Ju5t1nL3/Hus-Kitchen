# Laptop tests

Add behavioral tests here with the implementation task they verify. Keep contract,
domain, storage and application scenarios in separate files or subdirectories so
contributors do not all edit one shared test module.

Run every current laptop test from `laptop/`:

```sh
uv run python -m unittest discover -s tests -v
```
