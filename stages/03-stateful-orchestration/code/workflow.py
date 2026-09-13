"""One weather brief, from collection through content checks to publication."""
from __future__ import annotations

import argparse
from copy import deepcopy
import math
from typing import Any, Callable

from state_graph import END, START, MiniStateGraph, append_events, merge_update

State = dict[str, Any]
TEACHING_WEATHER = {
    "Tokyo": {"temperature_c": 18.0, "condition": "cloudy"},
    "Paris": {"temperature_c": 12.0, "condition": "light rain"},
}
NOTICES = {"zh-CN": "固定教学数据，不是实时天气。", "en": "Fixed teaching data, not live weather."}


def finite_number(value: Any) -> float:
    if type(value) not in (int, float):
        raise ValueError("Expected a finite number, not a string or boolean")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError("Number is out of range") from exc
    if not math.isfinite(number):
        raise ValueError("Expected a finite number")
    return number


def fahrenheit(value: Any) -> float:
    return finite_number(round(finite_number(value) * 9 / 5 + 32, 1))


def read_weather(city: str) -> dict[str, Any]:
    if not isinstance(city, str) or city not in TEACHING_WEATHER:
        raise ValueError("Unsupported teaching city")
    return {"city": city, **deepcopy(TEACHING_WEATHER[city]), "source": "fixed teaching record"}


def initial_state(cities: tuple[str, ...] | list[str] = ("Tokyo", "Paris"),
                  include_fahrenheit: bool = True, language: str = "zh-CN") -> State:
    if type(cities) not in (tuple, list) or not 1 <= len(cities) <= 2:
        raise ValueError("Select one or two cities")
    if any(not isinstance(city, str) or city not in TEACHING_WEATHER for city in cities):
        raise ValueError("Only Tokyo and Paris are supported")
    if len(set(cities)) != len(cities) or type(include_fahrenheit) is not bool:
        raise ValueError("Cities must be unique and the unit switch must be boolean")
    if language not in NOTICES:
        raise ValueError("Unsupported language")
    return {
        "cities": list(cities), "include_fahrenheit": include_fahrenheit, "language": language,
        "readings": [], "draft": None, "review": None, "revisions": 0,
        "events": [], "answer": None, "status": "working",
    }


def expected_rows(state: State) -> list[dict[str, Any]]:
    readings = state["readings"]
    if [reading["city"] for reading in readings] != state["cities"]:
        raise ValueError("Collected readings do not match requested cities")
    rows = deepcopy(readings)
    for row in rows:
        if state["include_fahrenheit"]:
            row["temperature_f"] = fahrenheit(row["temperature_c"])
    return rows


def review_issues(state: State) -> list[str]:
    draft = state["draft"]
    if not isinstance(draft, dict) or set(draft) != {"rows", "notice"}:
        return ["invalid_draft_shape"]
    issues = []
    if draft["rows"] != expected_rows(state):
        issues.append("rows_do_not_match_records_and_units")
    if draft["notice"] != NOTICES[state["language"]]:
        issues.append("missing_fixed_data_notice")
    return issues


def render_report(draft: dict[str, Any]) -> str:
    lines = []
    for row in draft["rows"]:
        units = f"{row['temperature_c']:.1f}°C"
        if "temperature_f" in row:
            units += f" / {row['temperature_f']:.1f}°F"
        lines.append(f"{row['city']}: {units}, {row['condition']}.")
    return "\n".join([*lines, draft["notice"]])


class ReportNodes:
    def __init__(self, *, draft_style: str = "missing-notice", max_revisions: int = 1,
                 reader: Callable[[str], dict[str, Any]] = read_weather) -> None:
        if draft_style not in {"missing-notice", "complete", "stubborn"}:
            raise ValueError("Unknown draft style")
        if type(max_revisions) is not int or max_revisions < 0:
            raise ValueError("max_revisions must be a nonnegative integer")
        self.draft_style = draft_style
        self.max_revisions = max_revisions
        self.reader = reader

    def collect(self, state: State) -> State:
        readings = []
        for city in state["cities"]:
            record = deepcopy(self.reader(city))
            if set(record) != {"city", "temperature_c", "condition", "source"} or record["city"] != city:
                raise ValueError("Reader returned an invalid weather record")
            record["temperature_c"] = finite_number(record["temperature_c"])
            if any(not isinstance(record[key], str) or not record[key].strip() for key in ("condition", "source")):
                raise ValueError("Reader must identify the condition and source")
            readings.append(record)
        return {"readings": readings, "events": ["collected requested records"]}

    def write_draft(self, state: State) -> State:
        notice = NOTICES[state["language"]] if self.draft_style == "complete" else ""
        return {
            "draft": {"rows": expected_rows(state), "notice": notice},
            "review": None, "events": ["wrote draft"],
        }

    def check_draft(self, state: State) -> State:
        issues = review_issues(state)
        return {
            "review": {"passed": not issues, "issues": issues, "checked_draft": deepcopy(state["draft"])},
            "events": ["checked draft: " + (", ".join(issues) if issues else "accepted")],
        }

    def route_after_check(self, state: State) -> str:
        review = state["review"]
        if review is None or review["checked_draft"] != state["draft"]:
            raise ValueError("The current draft has not been checked")
        if review["passed"]:
            return "accept"
        return "revise" if state["revisions"] < self.max_revisions else "hold"

    def revise_draft(self, state: State) -> State:
        if state["review"] is None or state["review"]["passed"]:
            raise ValueError("Revision requires a rejected review")
        if state["revisions"] >= self.max_revisions:
            raise ValueError("Revision budget exhausted")
        notice = "" if self.draft_style == "stubborn" else NOTICES[state["language"]]
        return {
            "draft": {"rows": expected_rows(state), "notice": notice},
            "review": None, "revisions": state["revisions"] + 1,
            "events": ["revised draft"],
        }

    def publish(self, state: State) -> State:
        if self.route_after_check(state) != "accept" or review_issues(state):
            raise ValueError("Only the checked, acceptable draft may be published")
        return {"answer": render_report(state["draft"]), "status": "completed", "events": ["published brief"]}

    def hold(self, state: State) -> State:
        if self.route_after_check(state) != "hold":
            raise ValueError("Hold requires an unsuccessful review and no revision budget")
        return {"answer": None, "status": "needs_attention", "events": ["held brief: revision budget exhausted"]}

    def mapping(self) -> dict[str, Callable[[State], State]]:
        return {name: getattr(self, name) for name in
                ("collect", "write_draft", "check_draft", "revise_draft", "publish", "hold")}


def connect_report(builder: Any, nodes: ReportNodes) -> None:
    for name, function in nodes.mapping().items():
        builder.add_node(name, function)
    builder.add_edge(START, "collect")
    builder.add_edge("collect", "write_draft")
    builder.add_edge("write_draft", "check_draft")
    builder.add_conditional_edges("check_draft", nodes.route_after_check,
                                  {"accept": "publish", "revise": "revise_draft", "hold": "hold"})
    builder.add_edge("revise_draft", "check_draft")
    builder.add_edge("publish", END)
    builder.add_edge("hold", END)


def build_mini_workflow(**options: Any):
    builder = MiniStateGraph(reducers={"events": append_events})
    connect_report(builder, ReportNodes(**options))
    return builder.compile()


def run_plain(state: State, nodes: ReportNodes) -> State:
    """The same bounded business process before introducing a graph engine."""
    state = deepcopy(state)
    reducers = {"events": append_events}
    for node in (nodes.collect, nodes.write_draft):
        state = merge_update(state, node(deepcopy(state)), reducers)
    while True:
        state = merge_update(state, nodes.check_draft(deepcopy(state)), reducers)
        route = nodes.route_after_check(state)
        if route != "revise":
            final = nodes.publish if route == "accept" else nodes.hold
            return merge_update(state, final(deepcopy(state)), reducers)
        state = merge_update(state, nodes.revise_draft(deepcopy(state)), reducers)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review a fixed two-city teaching weather brief.")
    parser.add_argument("--cities", choices=tuple(TEACHING_WEATHER), nargs="+", default=["Tokyo", "Paris"])
    parser.add_argument("--language", choices=tuple(NOTICES), default="zh-CN")
    parser.add_argument("--celsius-only", action="store_true")
    parser.add_argument("--draft-style", choices=("missing-notice", "complete", "stubborn"), default="missing-notice")
    parser.add_argument("--max-revisions", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--show-updates", action="store_true")
    return parser.parse_args()


def show_result(state: State) -> None:
    print("status:", state["status"], "revisions:", state["revisions"])
    print("events:", " -> ".join(state["events"]))
    print(state["answer"] or "No approved brief. Last draft remains in state.")


def main() -> None:
    args = parse_args()
    state = run_plain(initial_state(args.cities, not args.celsius_only, args.language),
                      ReportNodes(draft_style=args.draft_style, max_revisions=args.max_revisions))
    show_result(state)
    if state["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
