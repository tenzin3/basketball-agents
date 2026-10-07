"""career_context_cache/<slug>.json (+ <slug>_context.txt for manual inspection).

Generated from the database; never edited by hand. The database remains the source of truth.
Simulations read the cache and only rebuild when a file is missing.
"""
from __future__ import annotations

import json
import logging

from .. import config
from ..players import DISPLAY_ORDER, PLAYERS
from ..repository import Repository, get_repository
from .builder import build_package
from .documents import build_documents
from .retrieval import embed_texts

log = logging.getLogger(__name__)


def build_player(slug: str, repo: Repository | None = None, write: bool = True) -> dict | None:
    repo = repo or get_repository()
    ds, derived = repo.load_dataset(slug), repo.load_derived(slug)
    if ds is None or derived is None:
        log.warning("no data for %s - run ingest/load/derive first", slug)
        return None
    pkg = build_package(ds, derived)
    docs = build_documents(ds, derived)
    try:
        embs = embed_texts([d["text"] for d in docs])
        if embs:
            for d, e in zip(docs, embs):
                d["embedding"] = e
    except Exception as e:  # embeddings are optional
        log.warning("embeddings skipped: %s", e)
    repo.save_documents(slug, docs)
    if write:
        config.CONTEXT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (config.CONTEXT_CACHE_DIR / f"{slug}.json").write_text(json.dumps(pkg, indent=1, default=str))
        (config.CONTEXT_CACHE_DIR / f"{slug}_context.txt").write_text(pkg["text"]["layer1"] + "\n\n" + pkg["text"]["layer2"])
    return pkg


def build_all(repo: Repository | None = None) -> dict:
    return {slug: build_player(slug, repo) for slug in DISPLAY_ORDER}


_mem: dict = {}


def load_package(slug: str, repo: Repository | None = None) -> dict | None:
    if slug in _mem:
        return _mem[slug]
    p = config.CONTEXT_CACHE_DIR / f"{slug}.json"
    if p.exists():
        pkg = json.loads(p.read_text())
    else:
        pkg = build_player(slug, repo)
    if pkg is not None:
        _mem[slug] = pkg
    return pkg


def clear_memory_cache():
    _mem.clear()


def load_all_packages(repo: Repository | None = None) -> dict:
    return {slug: load_package(slug, repo) for slug in PLAYERS}
