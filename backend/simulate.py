"""Phase 3 CLI prototype:  python simulate.py [--clock 8 --margin -1 --defense "switch everything"]

Prints each agent's Round 1-3 responses followed by the Coach's decision.
Equivalent to `hoop simulate`.
"""
import argparse
import logging

from hoopcouncil.cli import add_sim_args, cmd_simulate

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    add_sim_args(ap)
    logging.basicConfig(level=logging.WARNING)
    cmd_simulate(ap.parse_args())
