"""Tests run against SYNTHETIC fixtures (tests/fixtures/make_fixtures.py) and the mock LLM.
No real player statistics are used or asserted here."""
import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path

from tests.helpers import synthetic_dataset

from hoopcouncil.agents.agents import validate_court
from hoopcouncil.agents.parsing import extract_json
from hoopcouncil.context.builder import assemble_agent_context, build_package
from hoopcouncil.context.documents import build_documents
from hoopcouncil.context.retrieval import generate_query, retrieve
from hoopcouncil.derive.run import derive_all
from hoopcouncil.ingest.sources.bref import parse_award_tokens
from hoopcouncil.ingest.sources.table_parse import parse_number
from hoopcouncil.quality.validate import validate


class ParsingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = synthetic_dataset()

    def test_numbers(self):
        self.assertEqual(parse_number(".453"), 0.453)
        self.assertEqual(parse_number("45%"), 0.45)
        self.assertEqual(parse_number("1,234"), 1234)
        self.assertIsNone(parse_number(""))
        self.assertEqual(parse_number("36:30"), 36.5)

    def test_award_tokens(self):
        t = {a["achievement_type"] for a in parse_award_tokens("MVP-1,AS,NBA1,DEF2,DPOY-3")}
        self.assertIn("NBA_MVP", t)
        self.assertIn("ALL_STAR", t)
        self.assertIn("ALL_NBA_FIRST", t)
        self.assertIn("ALL_DEFENSIVE_SECOND", t)
        self.assertNotIn("DEFENSIVE_PLAYER_OF_THE_YEAR", t)  # 3rd in voting is not a win
        self.assertIn("DEFENSIVE_PLAYER_OF_THE_YEAR_VOTING_FINISH", t)

    def test_bio(self):
        p = self.ds["player"]
        self.assertEqual(p["height_in"], 75)
        self.assertEqual(p["draft_pick"], 5)
        self.assertIsNone(p["wingspan_in"])  # never estimated
        self.assertEqual(p["teams"], ["AAA", "BBB"])

    def test_traded_season(self):
        rows = [s for s in self.ds["seasons"] if s["season"] == "2014-15" and s["stat_type"] == "regular_season"]
        combined = [r for r in rows if not r["is_team_split"]]
        self.assertEqual(len(combined), 1)
        self.assertEqual(combined[0]["teams"], ["AAA", "BBB"])
        self.assertEqual(len([r for r in rows if r["is_team_split"]]), 2)

    def test_dnp_and_regular_playoff_separation(self):
        self.assertEqual(self.ds["dnp_seasons"][0]["season"], "2013-14")
        self.assertEqual({s["stat_type"] for s in self.ds["seasons"]}, {"regular_season", "playoffs"})

    def test_percent_point_conversion(self):
        s = [s for s in self.ds["seasons"] if s["season"] == "2015-16" and s["stat_type"] == "regular_season"][0]
        self.assertAlmostEqual(s["advanced"]["usg_pct"], 0.31)
        self.assertAlmostEqual(s["shooting"]["fga_share_3p"], 0.45)
        self.assertAlmostEqual(s["pbp"]["pos_pg_share"], 0.90)

    def test_provenance_on_every_stat(self):
        for s in self.ds["seasons"]:
            for k in ("source", "source_url", "season", "retrieved_at", "stat_type"):
                self.assertIn(k, s["provenance"])
        for a in self.ds["achievements"]:
            self.assertTrue(a["provenance"]["source_url"])

    def test_achievements(self):
        types = {(a["achievement_type"], a["season"]) for a in self.ds["achievements"]}
        self.assertIn(("NBA_CHAMPIONSHIP", "2015-16"), types)
        self.assertIn(("NBA_FINALS_MVP", "2015-16"), types)
        self.assertIn(("SCORING_TITLE", "2015-16"), types)
        self.assertIn(("ALL_NBA_THIRD", "2014-15"), types)  # only on award page
        mvps = [a for a in self.ds["achievements"] if a["achievement_type"] == "NBA_MVP"]
        self.assertEqual(len(mvps), 1)  # page + column de-duplicated
        self.assertTrue(mvps[0].get("corroborated_by"))

    def test_playoff_rounds(self):
        g = [x for x in self.ds["game_logs"] if x["stat_type"] == "playoffs" and x["season"] == "2015-16"]
        rounds = {x["opponent"]: x["playoff_round"] for x in g}
        self.assertEqual(rounds["CCC"], "nba_finals")
        self.assertEqual(rounds["ZZZ"], "conference_finals")
        self.assertEqual(rounds["XXX"], "first_round")
        # 2015-16 rounds come from the source series table
        self.assertEqual({x["round_confidence"] for x in g}, {"labeled"})
        # 2014-15 has no series rows -> inferred
        g15 = [x for x in self.ds["game_logs"] if x["stat_type"] == "playoffs" and x["season"] == "2014-15" and x.get("playoff_round")]
        self.assertEqual({x["round_confidence"] for x in g15}, {"inferred"})

    def test_career_row_yrs_label(self):
        self.assertIn("totals", self.ds["career_rows_source"]["regular_season"])
        self.assertEqual(self.ds["career_rows_source"]["regular_season"]["totals"]["g"], 219)

    def test_robots_disallowed_gamelogs(self):
        ds = synthetic_dataset(disallow_gamelogs=True)
        self.assertFalse([g for g in ds["game_logs"] if g["stat_type"] == "regular_season"])
        self.assertTrue([g for g in ds["game_logs"] if g["stat_type"] == "playoffs"])
        self.assertTrue(ds["collection_notes"])
        rep = validate(ds)
        self.assertEqual(rep["coverage"]["Game logs"]["status"], "PLAYOFFS ONLY")
        self.assertEqual(rep["summary"].get("FAIL", 0), 0)

    def test_single_game_efg_above_one_is_valid(self):
        ds = copy.deepcopy(self.ds)
        ds["game_logs"][0]["stats"]["efg_pct"] = 1.5
        rep = validate(ds)
        self.assertEqual({c["check"]: c["status"] for c in rep["checks"]}["value_ranges"], "PASS")


class DeriveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = synthetic_dataset()
        cls.d = derive_all(cls.ds)

    def test_career_matches_source(self):
        rep = validate(self.ds, self.d)
        by = {c["check"]: c for c in rep["checks"]}
        self.assertEqual(by["career_totals[regular_season]"]["status"], "PASS")
        self.assertEqual(by["career_totals[playoffs]"]["status"], "PASS")
        self.assertEqual(rep["summary"].get("FAIL", 0), 0)

    def test_validation_detects_problems(self):
        ds = copy.deepcopy(self.ds)
        s = [x for x in ds["seasons"] if x["season"] == "2015-16" and x["stat_type"] == "regular_season"][0]
        s["totals"]["pts"] += 500
        s["per_game"]["fg_pct"] = 1.7
        ds["achievements"].append(dict(ds["achievements"][0], achievement_type="NBA_MVP", season="2012-13"))
        rep = validate(ds)
        failed = {c["check"] for c in rep["checks"] if c["status"] == "FAIL"}
        self.assertIn("career_totals[regular_season]", failed)
        self.assertIn("value_ranges", failed)
        self.assertIn("award_count[NBA_MVP]", failed)

    def test_aggregates_exclude_team_splits(self):
        agg = self.d["aggregates"]["regular_season"]
        self.assertEqual(agg["num_seasons"], 3)
        self.assertEqual(agg["totals"]["g"], 219)

    def test_peak(self):
        self.assertEqual(self.d["peak_seasons"][0]["season"], "2015-16")
        for p in self.d["peak_scores"]:
            self.assertTrue(0 <= p["peak_score"] <= 1)

    def test_archetypes_have_status_and_evidence(self):
        for a in self.d["archetypes"]:
            self.assertIn(a["status"], ("supported", "not_supported", "insufficient_data"))
            self.assertTrue(a["evidence"])
            self.assertTrue(a["rule"])
        iso = [a for a in self.d["archetypes"] if a["archetype"] == "isolation scorer"][0]
        self.assertEqual(iso["status"], "insufficient_data")  # no Synergy data -> never asserted

    def test_phases(self):
        names = [p["name"] for p in self.d["career_phases"]]
        self.assertIn("Synthetic Guard — AAA", names)
        self.assertIn("Peak", names)


class ContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = synthetic_dataset()
        cls.d = derive_all(cls.ds)
        cls.pkg = build_package(cls.ds, cls.d)
        cls.docs = build_documents(cls.ds, cls.d)

    def test_package_keys(self):
        for k in ("player", "identity", "career_summary", "season_stats", "playoff_summary", "finals_summary",
                  "achievements", "records", "shot_profile_summary", "play_type_tendencies", "career_phases",
                  "peak_seasons", "basketball_archetypes", "strengths", "limitations"):
            self.assertIn(k, self.pkg)
        json.dumps(self.pkg)

    def test_text_sections(self):
        t = self.pkg["text"]["layer1"]
        for sec in ("CAREER PROFILE", "MAJOR ACHIEVEMENTS", "CAREER STATISTICS", "PLAYOFF PROFILE", "SHOT PROFILE",
                    "OFFENSIVE TENDENCIES", "DEFENSIVE PROFILE", "PEAK SEASONS", "CAREER PHASES", "DATA LIMITATIONS"):
            self.assertIn(sec, t)
        self.assertIn("SEASON HISTORY", self.pkg["text"]["layer2"])

    def test_retrieval_intents(self):
        q = generate_query({"question": "Who should take the final shot?", "game_clock": 9, "quarter": 4,
                            "defensive_scheme": "switch everything"})
        self.assertIn("clutch", q["topics"])
        top = retrieve(self.docs, q)[0]
        self.assertTrue(set(top["topics"]) & {"final-shot", "clutch", "shot-creation"})
        q2 = generate_query({"question": "Who should initiate the offense?"})
        self.assertIn("playmaking", q2["topics"])
        top2 = retrieve(self.docs, q2)[0]
        self.assertIn("playmaking", top2["topics"])

    def test_budget(self):
        txt, considered = assemble_agent_context(self.pkg, retrieve(self.docs, generate_query({"question": "x"})), 600)
        self.assertIn("layer2 omitted (token budget)", considered["layers"])


class AgentTests(unittest.TestCase):
    def test_extract_json(self):
        self.assertEqual(extract_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(extract_json('Sure! {"a": {"b": "}"}, } trailing'), {"a": {"b": "}"}})
        self.assertTrue(extract_json("no json")["parse_error"])

    def test_clean_output_flattens_objects(self):
        from hoopcouncil.agents.parsing import clean_output

        out = clean_output({"key_data_points": [{"fact": "TS 61%", "source": "context"}, {"player": "X", "stat": 1}, "plain"],
                            "verdict": {"text": "Curry"}, "play": {"play_name": ["a", "b"], "player_roles": {"A": {"role": "screen"}}},
                            "evaluations": [{"of_player": "Y", "stance": "agree", "comment": {"text": "ok"}}]})
        self.assertTrue(all(isinstance(x, str) for x in out["key_data_points"]))
        self.assertEqual(out["key_data_points"][0], "TS 61% (context)")
        self.assertEqual(out["verdict"], "Curry")
        self.assertEqual(out["play"]["play_name"], "a; b")
        self.assertIsInstance(out["play"]["player_roles"]["A"], str)
        self.assertEqual(out["evaluations"][0]["comment"], "ok")

    def test_court_validation(self):
        out = validate_court({"court": {"start_positions": {"A": "top_of_key", "B": "moon"},
                                        "play_sequence": [{"time": 2, "player": "A", "action": "shoot"},
                                                          {"time": 1, "player": "B", "action": "teleport"},
                                                          {"time": 0, "player": "B", "action": "screen", "location": "nowhere"}]}})
        c = out["court"]
        self.assertEqual([s["time"] for s in c["play_sequence"]], [0.0, 2.0])
        self.assertIsNone(c["play_sequence"][0]["location"])
        self.assertIsNone(c["start_positions"]["B"])
        self.assertEqual(len(c["dropped_steps"]), 1)

    def test_mock_simulation_end_to_end(self):
        from hoopcouncil.orchestrator import run_simulation
        from hoopcouncil.players import PLAYERS
        from hoopcouncil.simulation_store import MemorySimulationStore

        ds = synthetic_dataset()
        d = derive_all(ds)
        pk, docs = {}, {}
        for slug, cfg in PLAYERS.items():
            p = build_package(ds, d)
            p["player"], p["slug"] = cfg.full_name, slug
            pk[slug], docs[slug] = p, build_documents(ds, d)
        store = MemorySimulationStore(persist=False)
        res = asyncio.run(run_simulation({"score_margin": -1, "game_clock": 9, "question": "final shot?"},
                                         store=store, provider="mock", packages=pk, documents=docs))
        self.assertEqual(len(res["round1"]), 5)
        self.assertEqual(len(res["round3"]), 5)
        self.assertIn("verdict", res["coach_call"]["decision"])
        self.assertIsNotNone(res["coach_call"]["decision"]["court"])  # a shot question gets a play + court
        self.assertIn("message", res["round1"][0]["content"])
        sim = store.get(res["id"])
        self.assertEqual(sim["status"], "complete")
        self.assertEqual(len(sim["messages"]), 15)
        self.assertTrue(sim["messages"][0]["data_considered"]["retrieved_documents"])

    def test_open_question_has_no_court(self):
        from hoopcouncil.orchestrator import run_simulation
        from hoopcouncil.players import PLAYERS

        ds = synthetic_dataset()
        d = derive_all(ds)
        pk = {slug: dict(build_package(ds, d), player=cfg.full_name) for slug, cfg in PLAYERS.items()}
        docs = {slug: build_documents(ds, d) for slug in PLAYERS}
        res = asyncio.run(run_simulation({"question": "Who was the best playoff scorer of the five?"},
                                         provider="mock", packages=pk, documents=docs))
        self.assertIsNone(res["coach_call"]["decision"]["court"])
        self.assertIn("comparison / greatness", res["query"]["intents"])

    def test_prompts_format_without_leftover_placeholders(self):
        import re

        from hoopcouncil.agents import prompts as P

        rules = P.GROUNDING_RULES.format(name="X")
        texts = [
            P.PLAYER_SYSTEM.format(name="X", focus="a", context="C", teammates="T", explain=P.EXPLAIN_NUMBERS, rules=rules),
            P.ROUND1_USER.format(question="q", lineup="l"),
            P.ROUND2_USER.format(question="q", proposals="p", name="X"),
            P.ROUND3_USER.format(question="q", proposals="p", debate="d", name="X"),
            P.COACH_SYSTEM.format(contexts="c", explain=P.EXPLAIN_NUMBERS, rules=P.COACH_RULES),
            P.COACH_USER.format(question="q", round1="a", round2="b", round3="c", vocab="v"),
        ]
        for t in texts:
            self.assertIsNone(re.search(r"\{[a-z_]+\}", t), t[:200])

    def test_peers_do_not_see_confidence(self):
        from hoopcouncil.agents.agents import _slim_r1

        r = {"player": "A", "message": "m", "confidence": 90}
        self.assertNotIn("confidence", _slim_r1(r))
        self.assertIn("confidence", _slim_r1(r, coach=True))

    def test_missing_data_is_an_error(self):
        from hoopcouncil.orchestrator import MissingDataError, run_simulation

        with self.assertRaises(MissingDataError):
            asyncio.run(run_simulation({"question": "x"}, provider="mock", packages={}, documents={}))


class FileStoreFlowTests(unittest.TestCase):
    """processed JSON -> derive -> context cache, using the dev-only file repository."""

    def test_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            from hoopcouncil import config
            from hoopcouncil.context import cache
            from hoopcouncil.repository import FileRepository

            ds = synthetic_dataset()
            ds["player"]["slug"] = "synth"
            base = Path(tmp)
            (base / "processed").mkdir()
            (base / "processed" / "synth.json").write_text(json.dumps(ds))
            (base / "derived").mkdir()
            (base / "derived" / "synth.json").write_text(json.dumps(derive_all(ds), default=str))
            old = config.CONTEXT_CACHE_DIR
            config.CONTEXT_CACHE_DIR = base / "cache"
            try:
                pkg = cache.build_player("synth", FileRepository(base))
                self.assertTrue((base / "cache" / "synth.json").exists())
                self.assertTrue((base / "cache" / "synth_context.txt").exists())
                self.assertTrue(FileRepository(base).load_documents("synth"))
                self.assertEqual(pkg["slug"], "synth")
            finally:
                config.CONTEXT_CACHE_DIR = old


def _have(*mods):
    import importlib.util

    return all(importlib.util.find_spec(m) for m in mods)


def _synthetic_packages():
    from hoopcouncil.players import PLAYERS

    ds = synthetic_dataset()
    d = derive_all(ds)
    return {slug: dict(build_package(ds, d), player=cfg.full_name, slug=slug) for slug, cfg in PLAYERS.items()}


class HostingTests(unittest.TestCase):
    """Serverless hosting (Vercel): database URL handling, packages in the DB, and step-by-step debates."""

    @unittest.skipUnless(_have("sqlalchemy"), "needs sqlalchemy")
    def test_database_url_normalisation(self):
        from hoopcouncil.db.session import normalize_url

        self.assertEqual(normalize_url("postgres://u:p@h/db?sslmode=require"), "postgresql+psycopg://u:p@h/db?sslmode=require")
        self.assertEqual(normalize_url("postgresql://u:p@h/db"), "postgresql+psycopg://u:p@h/db")
        self.assertEqual(normalize_url("postgresql+psycopg://u@h/db"), "postgresql+psycopg://u@h/db")
        self.assertEqual(normalize_url("sqlite:///x.db"), "sqlite:///x.db")

    def test_memory_store_runs_stage_by_stage(self):
        from hoopcouncil.orchestrator import run_stage
        from hoopcouncil.players import PLAYERS
        from hoopcouncil.simulation_store import MemorySimulationStore

        pk = _synthetic_packages()
        docs = {slug: [] for slug in PLAYERS}
        store = MemorySimulationStore(persist=False)
        sid = store.create({"question": "Down 1, 9 seconds left. Who takes the last shot?"}, {"provider": "mock"})
        ran = [asyncio.run(run_stage(store, sid, packages=pk, documents=docs)) for _ in range(5)]
        self.assertEqual(ran, [1, 2, 3, 4, None])
        sim = store.get(sid)
        self.assertEqual(sim["status"], "complete")
        self.assertEqual(len(sim["messages"]), 15)
        self.assertEqual([m["round"] for m in sim["messages"]], [1] * 5 + [2] * 5 + [3] * 5)
        self.assertIn("verdict", sim["coach_decision"]["decision"])

    def test_stage_claims(self):
        from hoopcouncil.simulation_store import MemorySimulationStore

        store = MemorySimulationStore(persist=False)
        sid = store.create({"question": "q"}, {})
        self.assertTrue(store.claim_stage(sid, 1))
        self.assertFalse(store.claim_stage(sid, 1))            # someone else is running it
        self.assertTrue(store.claim_stage(sid, 1, stale_after_s=-1))  # ...but a stale claim can be taken over
        store.finish_stage(sid, 1)
        self.assertFalse(store.claim_stage(sid, 1, stale_after_s=-1))  # finished stages never rerun

    @unittest.skipUnless(_have("sqlalchemy", "fastapi", "httpx"), "needs sqlalchemy, fastapi and httpx")
    def test_api_step_mode_on_sqlite(self):
        """The Vercel setup end to end: /api prefix, access code, packages read from the DB, browser-driven rounds."""
        from fastapi.testclient import TestClient

        from hoopcouncil import config
        from hoopcouncil.api import main as api
        from hoopcouncil.context import cache
        from hoopcouncil.db import session
        from hoopcouncil.repository import SQLRepository, get_repository

        saved = {k: getattr(config, k) for k in ("RUN_MODE", "ACCESS_CODE", "DAILY_LIMIT", "ALLOWED_PROVIDERS",
                                                  "CONTEXT_CACHE_DIR", "LLM_PROVIDER", "COACH_PROVIDER")}
        with tempfile.TemporaryDirectory() as tmp:
            try:
                session._engine, session._runtime_ready = None, False
                session.get_engine(f"sqlite:///{tmp}/hoop.db")
                session.init_db()
                get_repository.cache_clear()
                cache.clear_memory_cache()
                config.CONTEXT_CACHE_DIR = Path(tmp) / "no-cache-files"  # force the database path
                config.RUN_MODE, config.ACCESS_CODE, config.DAILY_LIMIT = "steps", "letmein", 2
                config.ALLOWED_PROVIDERS, config.LLM_PROVIDER, config.COACH_PROVIDER = ["mock"], "mock", "mock"
                repo = SQLRepository()
                for slug, pkg in _synthetic_packages().items():
                    repo.save_package(slug, pkg)
                if hasattr(api.app.state, "store"):
                    del api.app.state.store
                c = TestClient(api.app)

                cfg = c.get("/api/config").json()
                self.assertEqual(cfg["run_mode"], "steps")
                self.assertTrue(cfg["access_code_required"])
                self.assertEqual(cfg["providers"], ["mock"])
                self.assertEqual(c.get("/config").status_code, 200)  # root paths still work locally

                body = {"scenario": {"question": "Down 1 with 9 seconds left. Who takes the last shot?"}}
                self.assertEqual(c.post("/api/simulations", json=body).status_code, 401)
                self.assertEqual(c.post("/api/simulations", json={**body, "provider": "anthropic"},
                                        headers={"x-access-code": "letmein"}).status_code, 400)
                r = c.post("/api/simulations", json=body, headers={"x-access-code": "letmein"})
                self.assertEqual(r.status_code, 202, r.text)
                self.assertEqual(r.json()["run_mode"], "steps")
                sid = r.json()["id"]
                self.assertEqual(c.post(f"/api/simulations/{sid}/step").status_code, 401)
                stages = []
                for _ in range(5):
                    j = c.post(f"/api/simulations/{sid}/step", headers={"x-access-code": "letmein"}).json()
                    stages.append(j["ran_stage"])
                self.assertEqual(stages, [1, 2, 3, 4, None])
                sim = c.get(f"/api/simulations/{sid}").json()
                self.assertEqual(sim["status"], "complete", sim.get("error"))
                self.assertEqual(len(sim["messages"]), 15)
                self.assertIsNotNone(sim["coach_decision"])

                c.post("/api/simulations", json=body, headers={"x-access-code": "letmein"})
                self.assertEqual(c.post("/api/simulations", json=body, headers={"x-access-code": "letmein"}).status_code, 429)
            finally:
                for k, v in saved.items():
                    setattr(config, k, v)
                session._engine, session._runtime_ready = None, False
                get_repository.cache_clear()
                cache.clear_memory_cache()
                if hasattr(api.app.state, "store"):
                    del api.app.state.store

    @unittest.skipUnless(_have("sqlalchemy"), "needs sqlalchemy")
    def test_copy_db(self):
        import argparse

        from sqlalchemy import func, select

        from hoopcouncil import cli, config
        from hoopcouncil.db import models as m
        from hoopcouncil.db import session

        with tempfile.TemporaryDirectory() as tmp:
            old_url, old_cache = config.DATABASE_URL, config.CONTEXT_CACHE_DIR
            try:
                src_url, dst_url = f"sqlite:///{tmp}/src.db", f"sqlite:///{tmp}/dst.db"
                src = session.make_engine(src_url)
                m.Base.metadata.create_all(src)
                with src.begin() as c:
                    c.execute(m.Player.__table__.insert(), [{"slug": "synth", "full_name": "Synthetic Guard"}])
                    c.execute(m.Simulation.__table__.insert(), [{"id": "x", "scenario": {"question": "q"}}])
                config.DATABASE_URL = src_url
                config.CONTEXT_CACHE_DIR = Path(tmp) / "cache"
                config.CONTEXT_CACHE_DIR.mkdir()
                (config.CONTEXT_CACHE_DIR / "curry.json").write_text(json.dumps({"player": "Stephen Curry"}))
                cli.cmd_copy_db(argparse.Namespace(url=dst_url, with_chats=False))
                dst = session.make_engine(dst_url)
                with dst.connect() as c:
                    self.assertEqual(c.execute(select(func.count()).select_from(m.Player)).scalar(), 1)
                    self.assertEqual(c.execute(select(func.count()).select_from(m.Simulation)).scalar(), 0)  # chats skipped
                    self.assertEqual(c.execute(select(m.ContextPackage.slug)).scalars().all(), ["curry"])
            finally:
                config.DATABASE_URL, config.CONTEXT_CACHE_DIR = old_url, old_cache


class OpenRouterTests(unittest.TestCase):
    """OpenRouter provider: free models first, paid fallback, and the failure modes free models have."""

    def _provider(self, replies):
        import os

        from hoopcouncil.llm.providers import make_provider

        os.environ["OPENROUTER_API_KEY"] = "test-key"
        p = make_provider("openrouter", tier="player")
        calls = []

        async def fake_post(url, payload, headers, retries=3):
            calls.append(payload)
            r = replies.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        p._post = fake_post
        return p, calls

    def test_defaults_free_first_with_paid_fallback(self):
        p, calls = self._provider([{"choices": [{"message": {"content": "{}"}}], "model": "some/free-model"}])
        self.assertEqual(p.model, "openrouter/free")
        res = asyncio.run(p.complete("sys", "user"))
        self.assertEqual(calls[0]["models"], ["openrouter/free", "meta-llama/llama-3.1-8b-instruct"])
        self.assertEqual(res.model, "some/free-model")
        self.assertGreaterEqual(calls[0]["max_tokens"], 4000)

    def test_empty_reply_retries_on_fallback(self):
        p, calls = self._provider([{"choices": [{"message": {"content": ""}}]},
                                   {"choices": [{"message": {"content": "{\"message\": \"hi\"}"}}], "model": "meta-llama/llama-3.1-8b-instruct"}])
        res = asyncio.run(p.complete("sys", "user"))
        self.assertEqual(calls[1]["model"], "meta-llama/llama-3.1-8b-instruct")
        self.assertIn("hi", res.text)

    def test_error_inside_200_and_http_error_fall_back(self):
        p, calls = self._provider([{"error": {"message": "upstream busy"}},
                                   {"choices": [{"message": {"content": "ok"}}]}])
        self.assertEqual(asyncio.run(p.complete("s", "u")).text, "ok")
        p, calls = self._provider([RuntimeError("openrouter HTTP 400: bad model"),
                                   {"choices": [{"message": {"content": "ok"}}]}])
        self.assertEqual(asyncio.run(p.complete("s", "u")).text, "ok")

    def test_missing_key_is_a_clear_error(self):
        import os

        from hoopcouncil.llm.providers import make_provider

        old = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            with self.assertRaisesRegex(RuntimeError, "OPENROUTER_API_KEY"):
                make_provider("openrouter")._headers()
        finally:
            if old is not None:
                os.environ["OPENROUTER_API_KEY"] = old


class SecurityTests(unittest.TestCase):
    def test_public_error_hides_secrets(self):
        from hoopcouncil.orchestrator import public_error

        msg = public_error(RuntimeError("openrouter HTTP 401: Bearer sk-or-v1-abcdef1234567890 bad\nsecond line"))
        self.assertNotIn("abcdef1234567890", msg)
        self.assertNotIn("second line", msg)
        msg = public_error(RuntimeError("could not connect postgresql+psycopg://hoop:s3cret@db.neon.tech/x?key=AIzaXYZ"))
        self.assertNotIn("s3cret", msg)
        self.assertNotIn("AIzaXYZ", msg)

    @unittest.skipUnless(_have("pydantic"), "needs pydantic")
    def test_request_size_limits(self):
        from pydantic import ValidationError

        from hoopcouncil.api.schemas import SimulationRequest

        with self.assertRaises(ValidationError):
            SimulationRequest(scenario={"question": "x" * 2001})
        with self.assertRaises(ValidationError):
            SimulationRequest(scenario={"question": "q", "lineup": {f"p{i}": "x" for i in range(6)}})
        with self.assertRaises(ValidationError):
            SimulationRequest(scenario={"question": "q", "context": "x" * 5000})

    @unittest.skipUnless(_have("sqlalchemy", "fastapi", "httpx"), "needs sqlalchemy, fastapi and httpx")
    def test_hosted_guards(self):
        from fastapi.testclient import TestClient

        from hoopcouncil import config
        from hoopcouncil.api import main as api

        saved = {k: getattr(config, k) for k in ("HOSTED", "ALLOW_MODEL_OVERRIDE", "ACCESS_CODE", "ALLOWED_PROVIDERS")}
        try:
            config.HOSTED, config.ALLOW_MODEL_OVERRIDE, config.ACCESS_CODE = True, False, ""
            config.ALLOWED_PROVIDERS = ["mock"]
            c = TestClient(api.app)
            self.assertEqual(c.get("/api/simulations").status_code, 404)  # nobody can list others' questions
            r = c.post("/api/simulations", json={"scenario": {"question": "q"}, "player_model": "some/very-expensive-model"})
            self.assertEqual(r.status_code, 400)
            r = c.post("/api/simulations", json={"scenario": {"question": "q"}, "coach_provider": "anthropic"})
            self.assertEqual(r.status_code, 400)
        finally:
            for k, v in saved.items():
                setattr(config, k, v)


class BackupRetryTests(unittest.TestCase):
    def test_unreadable_free_reply_is_retried_on_backup(self):
        import os

        from hoopcouncil.agents.agents import _retry_on_backup
        from hoopcouncil.agents.parsing import extract_json
        from hoopcouncil.llm.providers import LLMResult, make_provider

        os.environ["OPENROUTER_API_KEY"] = "test-key"
        p = make_provider("openrouter")
        calls = []

        async def fake_call(model, fallbacks, system, user):
            calls.append(model)
            return '{"message": "Curry made 42.6% of his threes."}', model, {}
        p._call = fake_call
        bad = LLMResult("sorry, I cannot help", "some/free-model", 5, {})
        res, obj = asyncio.run(_retry_on_backup(p, "s", "u", bad, extract_json(bad.text), extract_json, "message"))
        self.assertEqual(calls, ["meta-llama/llama-3.1-8b-instruct"])
        self.assertIn("42.6", obj["message"])
        good = LLMResult('{"message": "fine"}', "free", 5, {})
        res, obj = asyncio.run(_retry_on_backup(p, "s", "u", good, extract_json(good.text), extract_json, "message"))
        self.assertEqual(len(calls), 1)  # a usable reply is kept as is


if __name__ == "__main__":
    unittest.main()
