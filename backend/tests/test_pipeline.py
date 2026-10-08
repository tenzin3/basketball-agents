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
        from hoopcouncil.agents import prompts as P

        rules = P.GROUNDING_RULES.format(name="X")
        sysp = P.PLAYER_SYSTEM.format(name="X", focus="a", context="C", teammates="T", rules=rules)
        self.assertNotIn("{name}", sysp)
        for t in (P.ROUND1_USER.format(question="q", lineup="l"), P.ROUND2_USER.format(question="q", proposals="p"),
                  P.ROUND3_USER.format(question="q", proposals="p", debate="d"),
                  P.COACH_USER.format(question="q", round1="a", round2="b", round3="c", vocab="v")):
            self.assertIn('"', t)

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


if __name__ == "__main__":
    unittest.main()
