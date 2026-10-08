"""Persistence for simulations (rounds, messages, coach decisions)."""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timedelta, timezone

from . import config


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class SimulationStore:
    def create(self, scenario: dict, llm_config: dict) -> str: ...
    def set_status(self, sim_id: str, status: str, error: str | None = None) -> None: ...
    def start_round(self, sim_id: str, n: int, name: str) -> None: ...
    def complete_round(self, sim_id: str, n: int) -> None: ...
    def add_message(self, sim_id: str, msg: dict) -> None: ...
    def set_coach(self, sim_id: str, coach: dict) -> None: ...
    def get(self, sim_id: str) -> dict | None: ...
    def list(self, limit: int = 20) -> list: ...

    # Step-by-step mode (the browser asks for one stage at a time).
    def claim_stage(self, sim_id: str, stage: int, stale_after_s: int = 330) -> bool:
        """True if this caller may run `stage` now: nobody has claimed it, or an earlier claim went stale
        (that request probably hit the hosting time limit)."""
        ...

    def finish_stage(self, sim_id: str, stage: int) -> None: ...
    def reset_stage(self, sim_id: str, stage: int) -> None:
        """Drop anything a stale attempt left behind for this stage before running it again."""
        ...

    def count_since(self, hours: float) -> int:
        """Simulations created in the last `hours` (for the optional daily limit)."""
        ...


class MemorySimulationStore(SimulationStore):
    """In-process store; optionally mirrors each simulation to data/simulations/<id>.json."""

    def __init__(self, persist: bool = True):
        self._d: dict = {}
        self._lock = threading.Lock()
        self.persist = persist
        self.dir = config.DATA_DIR / "simulations"

    def _save(self, sim_id):
        if self.persist:
            self.dir.mkdir(parents=True, exist_ok=True)
            (self.dir / f"{sim_id}.json").write_text(json.dumps(self._d[sim_id], default=str, indent=1))

    def create(self, scenario, llm_config):
        sim_id = str(uuid.uuid4())
        with self._lock:
            self._d[sim_id] = {"id": sim_id, "created_at": _now(), "status": "queued", "scenario": scenario,
                               "llm_config": llm_config, "error": None, "rounds": [], "messages": [], "coach_decision": None}
            self._save(sim_id)
        return sim_id

    def set_status(self, sim_id, status, error=None):
        with self._lock:
            self._d[sim_id]["status"] = status
            self._d[sim_id]["error"] = error
            self._d[sim_id]["updated_at"] = _now()
            self._save(sim_id)

    def start_round(self, sim_id, n, name):
        with self._lock:
            self._d[sim_id]["rounds"].append({"round_number": n, "name": name, "started_at": _now(), "completed_at": None})
            self._save(sim_id)

    def complete_round(self, sim_id, n):
        with self._lock:
            for r in self._d[sim_id]["rounds"]:
                if r["round_number"] == n:
                    r["completed_at"] = _now()
            self._save(sim_id)

    def add_message(self, sim_id, msg):
        with self._lock:
            self._d[sim_id]["messages"].append({**msg, "created_at": _now()})
            self._save(sim_id)

    def set_coach(self, sim_id, coach):
        with self._lock:
            self._d[sim_id]["coach_decision"] = coach
            self._save(sim_id)

    def get(self, sim_id):
        if sim_id not in self._d and self.persist:
            p = self.dir / f"{sim_id}.json"
            if p.exists():
                self._d[sim_id] = json.loads(p.read_text())
        d = self._d.get(sim_id)
        return {k: v for k, v in d.items() if k != "_steps"} if d else None

    def list(self, limit=20):
        items = list(self._d.values())
        if self.persist and self.dir.exists():
            known = {x["id"] for x in items}
            for p in self.dir.glob("*.json"):
                if p.stem not in known:
                    try:
                        items.append(json.loads(p.read_text()))
                    except ValueError:
                        pass
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return [{k: x.get(k) for k in ("id", "created_at", "status", "scenario")} for x in items[:limit]]


    # step mode (in-process)
    def claim_stage(self, sim_id, stage, stale_after_s=330):
        now = datetime.now(timezone.utc)
        with self._lock:
            steps = self._d[sim_id].setdefault("_steps", {})
            st = steps.get(stage)
            if st is None or (st.get("finished_at") is None and now - st["started_at"] > timedelta(seconds=stale_after_s)):
                steps[stage] = {"started_at": now, "finished_at": None}
                return True
            return False

    def finish_stage(self, sim_id, stage):
        with self._lock:
            st = self._d[sim_id].get("_steps", {}).get(stage)
            if st:
                st["finished_at"] = datetime.now(timezone.utc)

    def reset_stage(self, sim_id, stage):
        with self._lock:
            d = self._d[sim_id]
            d["messages"] = [m for m in d["messages"] if m.get("round") != stage]
            d["rounds"] = [r for r in d["rounds"] if r["round_number"] != stage]
            if stage == 4:
                d["coach_decision"] = None

    def count_since(self, hours):
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        return sum(1 for x in self._d.values() if x.get("created_at", "") >= cutoff)


class SQLSimulationStore(SimulationStore):
    def __init__(self):
        from .db.session import ensure_runtime_tables

        ensure_runtime_tables()

    def _s(self):
        from .db.session import session_scope

        return session_scope()

    def claim_stage(self, sim_id, stage, stale_after_s=330):
        from sqlalchemy import select, update
        from sqlalchemy.exc import IntegrityError

        from .db import models as m

        try:
            with self._s() as s:
                s.add(m.SimulationStep(simulation_id=sim_id, stage=stage))
            return True
        except IntegrityError:
            pass
        now = datetime.now(timezone.utc)
        with self._s() as s:
            row = s.scalar(select(m.SimulationStep).where(m.SimulationStep.simulation_id == sim_id,
                                                          m.SimulationStep.stage == stage))
            if row is None or row.finished_at is not None:
                return False
            started = row.started_at if row.started_at.tzinfo else row.started_at.replace(tzinfo=timezone.utc)
            if now - started <= timedelta(seconds=stale_after_s):
                return False
            # take over the stale claim; the WHERE on started_at makes this a compare-and-swap
            res = s.execute(update(m.SimulationStep).where(m.SimulationStep.id == row.id,
                                                           m.SimulationStep.started_at == row.started_at)
                            .values(started_at=now))
            return res.rowcount == 1

    def finish_stage(self, sim_id, stage):
        from sqlalchemy import update

        from .db import models as m

        with self._s() as s:
            s.execute(update(m.SimulationStep).where(m.SimulationStep.simulation_id == sim_id, m.SimulationStep.stage == stage)
                      .values(finished_at=datetime.now(timezone.utc)))

    def reset_stage(self, sim_id, stage):
        from sqlalchemy import delete

        from .db import models as m

        with self._s() as s:
            s.execute(delete(m.SimulationMessage).where(m.SimulationMessage.simulation_id == sim_id,
                                                        m.SimulationMessage.round_number == stage))
            s.execute(delete(m.SimulationRound).where(m.SimulationRound.simulation_id == sim_id,
                                                      m.SimulationRound.round_number == stage))
            if stage == 4:
                s.execute(delete(m.CoachDecision).where(m.CoachDecision.simulation_id == sim_id))

    def count_since(self, hours):
        from sqlalchemy import func, select

        from .db import models as m

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with self._s() as s:
            return s.scalar(select(func.count()).select_from(m.Simulation).where(m.Simulation.created_at >= cutoff)) or 0

    def create(self, scenario, llm_config):
        from .db import models as m

        sim_id = str(uuid.uuid4())
        with self._s() as s:
            s.add(m.Simulation(id=sim_id, scenario=scenario, llm_config=llm_config, status="queued"))
        return sim_id

    def set_status(self, sim_id, status, error=None):
        from .db import models as m

        with self._s() as s:
            sim = s.get(m.Simulation, sim_id)
            sim.status, sim.error = status, error

    def start_round(self, sim_id, n, name):
        from .db import models as m

        with self._s() as s:
            s.add(m.SimulationRound(simulation_id=sim_id, round_number=n, name=name))

    def complete_round(self, sim_id, n):
        from sqlalchemy import select

        from .db import models as m

        with self._s() as s:
            r = s.scalar(select(m.SimulationRound).where(m.SimulationRound.simulation_id == sim_id,
                                                          m.SimulationRound.round_number == n))
            if r:
                r.completed_at = datetime.now(timezone.utc)

    def add_message(self, sim_id, msg):
        from .db import models as m

        with self._s() as s:
            s.add(m.SimulationMessage(simulation_id=sim_id, round_number=msg["round"], player=msg["slug"],
                                      content=msg["content"], raw_text=msg.get("raw_text"),
                                      data_considered=msg.get("data_considered"), model=msg.get("model"),
                                      latency_ms=msg.get("latency_ms")))

    def set_coach(self, sim_id, coach):
        from .db import models as m

        with self._s() as s:
            s.add(m.CoachDecision(simulation_id=sim_id, decision=coach["decision"], raw_text=coach.get("raw_text"),
                                  model=coach.get("model")))

    def get(self, sim_id):
        from .db import models as m
        from .players import get_player

        with self._s() as s:
            sim = s.get(m.Simulation, sim_id)
            if sim is None:
                return None
            msgs = []
            for x in sim.messages:
                try:
                    name = get_player(x.player).full_name
                except KeyError:
                    name = x.player
                msgs.append({"round": x.round_number, "slug": x.player, "player": name, "content": x.content,
                             "data_considered": x.data_considered, "model": x.model, "latency_ms": x.latency_ms,
                             "created_at": x.created_at.isoformat() if x.created_at else None})
            cd = sim.coach_decision
            return {"id": sim.id, "created_at": sim.created_at.isoformat() if sim.created_at else None,
                    "status": sim.status, "scenario": sim.scenario, "llm_config": sim.llm_config, "error": sim.error,
                    "rounds": [{"round_number": r.round_number, "name": r.name,
                                "started_at": r.started_at.isoformat() if r.started_at else None,
                                "completed_at": r.completed_at.isoformat() if r.completed_at else None} for r in sim.rounds],
                    "messages": msgs,
                    "coach_decision": {"decision": cd.decision, "model": cd.model} if cd else None}

    def list(self, limit=20):
        from sqlalchemy import select

        from .db import models as m

        with self._s() as s:
            rows = s.scalars(select(m.Simulation).order_by(m.Simulation.created_at.desc()).limit(limit))
            return [{"id": r.id, "created_at": r.created_at.isoformat() if r.created_at else None, "status": r.status,
                     "scenario": r.scenario} for r in rows]
