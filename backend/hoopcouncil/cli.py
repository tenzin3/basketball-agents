"""`hoop` command line.

  hoop ingest [--players curry,kobe] [--no-gamelogs] [--with-nba-stats] [--offline] [--refresh]
  hoop load                 # processed JSON -> PostgreSQL
  hoop derive               # aggregates, peaks, phases, archetypes, validation -> DB + data/reports
  hoop build-context        # career_context_cache/*.json + retrieval documents
  hoop pipeline             # ingest + load + derive + build-context
  hoop report               # print data-quality reports
  hoop simulate ...         # CLI debate (same as python simulate.py)
  hoop serve                # FastAPI on :8000
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import textwrap

from . import config


def _players(arg):
    return [p.strip() for p in arg.split(",")] if arg else None


def cmd_ingest(a):
    from .ingest.pipeline import ingest

    ingest(_players(a.players), include_gamelogs=not a.no_gamelogs, with_nba_stats=a.with_nba_stats,
           offline=a.offline, refresh=a.refresh)


def cmd_load(a):
    from .ingest.pipeline import load_to_db

    load_to_db(_players(a.players))


def cmd_derive(a):
    from .ingest.pipeline import derive_and_validate
    from .quality.validate import format_report

    reps = derive_and_validate(_players(a.players), use_db=not a.files)
    for rep in reps.values():
        print(format_report(rep))
        print("-" * 60)


def cmd_build_context(a):
    from .context.cache import build_all, build_player

    if a.players:
        for p in _players(a.players):
            from .players import get_player

            build_player(get_player(p).slug)
    else:
        build_all()
    print(f"context packages written to {config.CONTEXT_CACHE_DIR}")


def cmd_pipeline(a):
    cmd_ingest(a)
    if not a.files:
        cmd_load(a)
    cmd_derive(a)
    cmd_build_context(a)


def cmd_report(a):
    for p in sorted(config.REPORTS_DIR.glob("*.txt")):
        print(p.read_text())
        print("-" * 60)


def _print_block(title, body, width=100):
    print(f"\n🏀 {title}")
    for line in body:
        print(textwrap.fill(line, width=width, initial_indent="   ", subsequent_indent="     "))


def cmd_simulate(a):
    from .orchestrator import run_simulation

    scenario = {"question": a.question, "context": a.context, "score_margin": a.margin, "game_clock": a.clock,
                "defensive_scheme": a.defense}
    scenario = {k: v for k, v in scenario.items() if v is not None}
    if a.scenario:
        scenario.update(json.load(open(a.scenario)))
    print("AI simulation based on player statistics and career tendencies. Agents are not the real players.\n")
    print("You asked:", scenario["question"])

    def on_event(kind, payload):
        if kind == "round_start":
            names = {1: "ROUND 1: FIRST ANSWERS", 2: "ROUND 2: DEBATE", 3: "ROUND 3: FINAL WORD", 4: "COACH"}
            print(f"\n{'=' * 25} {names.get(payload, payload)} {'=' * 25}")
        elif kind == "round_complete":
            for m in payload["messages"]:
                c = m["content"]
                if c.get("parse_error"):
                    _print_block(m["player"].upper() + " AGENT", ["(could not parse JSON)", m["raw_text"][:800]])
                    continue
                lines = [c.get("message") or c.get("huddle_line") or ""]
                rnd = payload["round"]
                if rnd == 1:
                    lines.append(f"POSITION: {c.get('position')}")
                    if isinstance(c.get("play"), dict):
                        pl = c["play"]
                        lines.append(f"PLAY: {pl.get('play_name')} | primary: {pl.get('primary_option')} | then: {pl.get('secondary_option')}")
                    lines += [f"DATA: {x}" for x in c.get("data_support", [])[:4]]
                elif rnd == 2:
                    lines += [f"{str(e.get('stance', '')).upper()} {e.get('of_player')}: {e.get('comment')}"
                              for e in c.get("evaluations", []) if isinstance(e, dict)]
                    lines.append(f"NOW: {c.get('revised_position')} (changed: {c.get('changed_position')})")
                else:
                    lines.append(f"FINAL: {c.get('final_answer')} | backs {c.get('backs')}")
                lines.append(f"CONFIDENCE: {c.get('confidence')}")
                _print_block(m["player"].upper() + " AGENT", lines)
        elif kind == "coach":
            d = payload["decision"]
            print("\n# COACH'S ANSWER\n")
            print(textwrap.fill(str(d.get("verdict") or d.get("play_name")), 100))
            if d.get("answer"):
                print("\n" + textwrap.fill(str(d["answer"]), 100, initial_indent="   ", subsequent_indent="   "))
            pl = d.get("play") if isinstance(d.get("play"), dict) else None
            if pl:
                for k, lab in (("play_name", "PLAY"), ("ball_handler", "BALL HANDLER"), ("primary_option", "PRIMARY"),
                               ("secondary_option", "SECONDARY"), ("third_option", "THIRD"), ("counter", "COUNTER")):
                    if pl.get(k):
                        print(f"\n{lab}\n   {pl.get(k)}")
            print("\nWHY\n" + textwrap.fill(str(d.get("reasoning")), 100, initial_indent="   ", subsequent_indent="   "))
            if d.get("key_data_points"):
                print("\nDATA")
                for x in d["key_data_points"]:
                    print(f"   - {x}")
            print(f"\nCONFIDENCE {d.get('confidence')}")

    store = None
    if a.save:
        from .simulation_store import MemorySimulationStore, SQLSimulationStore

        store = MemorySimulationStore() if a.files else SQLSimulationStore()
    res = asyncio.run(run_simulation(scenario, store=store, provider=a.provider, player_model=a.player_model,
                                     coach_provider=a.coach_provider, coach_model=a.coach_model, on_event=on_event))
    if a.json_out:
        with open(a.json_out, "w") as f:
            json.dump(res, f, indent=1, default=str)
        print(f"\nfull transcript written to {a.json_out}")


def cmd_serve(a):
    import uvicorn

    uvicorn.run("hoopcouncil.api.main:app", host=a.host, port=a.port, reload=a.reload)


def build_parser():
    ap = argparse.ArgumentParser(prog="hoop", description="HoopCouncil data pipeline and simulation CLI")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--players", help="comma list, e.g. curry,kobe (default: all five)")
        p.add_argument("--files", action="store_true", help="skip the database (dev/test only)")

    p = sub.add_parser("ingest"); common(p)
    for x in (p,):
        x.add_argument("--no-gamelogs", action="store_true")
        x.add_argument("--with-nba-stats", action="store_true", help="also pull clutch/Synergy/tracking from NBA.com (opt-in)")
        x.add_argument("--offline", action="store_true", help="only use the raw cache")
        x.add_argument("--refresh", action="store_true", help="ignore the raw cache")
    p.set_defaults(fn=cmd_ingest)
    p = sub.add_parser("load"); common(p); p.set_defaults(fn=cmd_load)
    p = sub.add_parser("derive"); common(p); p.set_defaults(fn=cmd_derive)
    p = sub.add_parser("build-context"); common(p); p.set_defaults(fn=cmd_build_context)
    p = sub.add_parser("pipeline"); common(p)
    p.add_argument("--no-gamelogs", action="store_true"); p.add_argument("--with-nba-stats", action="store_true")
    p.add_argument("--offline", action="store_true"); p.add_argument("--refresh", action="store_true")
    p.set_defaults(fn=cmd_pipeline)
    p = sub.add_parser("report"); p.set_defaults(fn=cmd_report)
    p = sub.add_parser("simulate"); add_sim_args(p); p.set_defaults(fn=cmd_simulate)
    p = sub.add_parser("serve"); p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true"); p.set_defaults(fn=cmd_serve)
    return ap


def add_sim_args(p):
    p.add_argument("question", nargs="?", default="We're down 1 with 9 seconds left and they switch everything. Who takes the last shot?",
                   help="any basketball question, in quotes")
    p.add_argument("--context", help="optional extra context")
    p.add_argument("--margin", type=int, help="optional: score margin from the offense's view")
    p.add_argument("--clock", type=float, help="optional: seconds left")
    p.add_argument("--defense", help="optional: defensive scheme")
    p.add_argument("--scenario", help="JSON file with fields (overrides the above)")
    p.add_argument("--provider", help="anthropic|openai|gemini|local|mock (default from HOOP_LLM_PROVIDER)")
    p.add_argument("--player-model"); p.add_argument("--coach-provider"); p.add_argument("--coach-model")
    p.add_argument("--save", action="store_true", help="persist the simulation")
    p.add_argument("--files", action="store_true", help="with --save: store as JSON instead of DB")
    p.add_argument("--json-out", help="write the full transcript to this file")


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if getattr(a, "files", False):
        import os

        os.environ["HOOP_STORE"] = "files"
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        a.fn(a)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
