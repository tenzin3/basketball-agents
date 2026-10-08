"""CLI chat:  python simulate.py "any basketball question" [--provider local]

Prints each agent's Round 1-3 messages followed by the Coach's answer.
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
