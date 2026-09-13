"""Offline model double using the same graph nodes as the DeepSeek entry."""
from agent_graph import ScriptedModel, parse_agent_args, run_demo


def main() -> None:
    args = parse_agent_args()
    print("offline model double; no API calls")
    state = run_demo(ScriptedModel(args.city, args.task, args.language), args)
    if state["error"] is not None:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
