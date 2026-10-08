"""Entry point for hosting the API as one Python function (Vercel looks for `app` in main.py).
Locally, use `make api` / `hoop serve` instead."""
from hoopcouncil.api.main import app  # noqa: F401
