"""Official CLI for Agent Workflow."""

from __future__ import annotations

import argparse


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="agent-workflow",
        description="Run Agent Workflow experiments and analysis workflows.",
    )
    commands = [
        "parallel",
        "parallel-shared",
        "single-long",
        "single-memory",
        "swarm",
        "merge",
        "certified-time",
        "baseline-calibration",
        "doctor",
        "demo",
    ]
    parser.add_argument("command", nargs="?", choices=commands, help="Command to run.")
    parser.add_argument("args", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)
    rest = args.args
    if args.command == "parallel":
        from agent_workflow.modes.parallel import main_parallel
        main_parallel(rest)
    elif args.command == "parallel-shared":
        from agent_workflow.launcher import main_parallel_shared
        main_parallel_shared(rest)
    elif args.command == "single-long":
        from agent_workflow.modes.single_long import main_single_long
        main_single_long(rest)
    elif args.command == "single-memory":
        from agent_workflow.launcher import main_single_memory
        main_single_memory(rest)
    elif args.command == "swarm":
        from agent_workflow.modes.swarm import main_swarm
        main_swarm(rest)
    elif args.command == "merge":
        from scripts.run_merge_phase import main as merge_main
        merge_main(rest)
    elif args.command == "certified-time":
        from agent_workflow.instrumentation.certified_time import main as certified_time_main
        certified_time_main(rest)
    elif args.command == "baseline-calibration":
        from agent_workflow.baseline_calibration import main as baseline_calibration_main
        baseline_calibration_main(rest)
    elif args.command == "doctor":
        from agent_workflow.doctor import main as doctor_main
        doctor_main(rest)
    elif args.command == "demo":
        from agent_workflow.demo import main as demo_main
        demo_main(rest)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
