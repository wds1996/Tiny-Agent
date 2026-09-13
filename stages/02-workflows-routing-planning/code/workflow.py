"""Fixed weather workflow and the data used by every Stage 02 example."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

City = Literal["Tokyo", "Paris"]
Source = Literal["primary", "backup"]
Language = Literal["zh-CN", "en"]


class Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, revalidate_instances="always"
    )


class WeatherTask(Contract):
    cities: tuple[City, ...] = Field(min_length=1, max_length=2)
    fahrenheit: bool = False
    language: Language = "zh-CN"

    @model_validator(mode="after")
    def unique_cities(self) -> "WeatherTask":
        if len(set(self.cities)) != len(self.cities):
            raise ValueError("cities must not repeat")
        return self


@dataclass(frozen=True)
class Reading:
    city: str
    temperature_c: float
    condition: str
    source: str
    snapshot: str = "teaching-v1"
    temperature_f: float | None = None


class SourceUnavailable(RuntimeError):
    def __init__(self, city: str, source: str) -> None:
        super().__init__(f"{source} unavailable for {city}")
        self.city = city
        self.source = source


class WeatherService:
    """Two access paths to the SAME fixed snapshot, not real weather services."""

    def __init__(self, *, unavailable: tuple[tuple[str, str], ...] = ()) -> None:
        self.unavailable = frozenset(unavailable)
        self.records = {"Tokyo": (18.0, "cloudy"), "Paris": (12.0, "light rain")}
        self.calls: list[tuple[str, str]] = []

    def read(self, city: str, source: str = "primary") -> Reading:
        if city not in self.records or source not in {"primary", "backup"}:
            raise ValueError("unsupported city or source")
        self.calls.append((source, city))
        if (source, city) in self.unavailable:
            raise SourceUnavailable(city, source)
        temperature, condition = self.records[city]
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
            raise ValueError("the source must return a numeric temperature")
        if not math.isfinite(temperature) or not -100 <= temperature <= 100:
            raise ValueError("temperature is outside the teaching data range")
        return Reading(city, float(temperature), condition, source)


def convert_temperature(reading: Reading) -> Reading:
    if reading.temperature_f is not None:
        raise ValueError("the record was already converted")
    converted = round(reading.temperature_c * 9 / 5 + 32, 1)
    return replace(reading, temperature_f=converted)


def render_brief(task: WeatherTask, readings: tuple[Reading, ...]) -> str:
    if len(readings) != len(task.cities) or {r.city for r in readings} != set(task.cities):
        raise ValueError("the brief must cover each requested city exactly once")
    if len({r.snapshot for r in readings}) != 1:
        raise ValueError("cannot compare different teaching snapshots")
    if any((r.temperature_f is not None) != task.fahrenheit for r in readings):
        raise ValueError("the brief does not have the requested units")
    by_city = {r.city: r for r in readings}
    lines = []
    for city in task.cities:
        record = by_city[city]
        units = f"{record.temperature_c:.1f}°C"
        if task.fahrenheit:
            units += f" / {record.temperature_f:.1f}°F"
        condition = record.condition
        if task.language == "zh-CN":
            condition = {"cloudy": "多云", "light rain": "小雨"}.get(condition, condition)
        lines.append(f"{city}: {units}, {condition} [{record.source}; {record.snapshot}]")
    if len(readings) == 2:
        left, right = (by_city[city] for city in task.cities)
        difference = abs(left.temperature_c - right.temperature_c)
        if difference == 0:
            lines.append("两城温度相同。" if task.language == "zh-CN" else "The temperatures are equal.")
        else:
            warmer = left.city if left.temperature_c > right.temperature_c else right.city
            lines.append(
                f"{warmer} 更暖，温差 {difference:.1f}°C。" if task.language == "zh-CN"
                else f"{warmer} is warmer by {difference:.1f}°C."
            )
    lines.append("以上均为固定教学记录，不是实时天气。" if task.language == "zh-CN"
                 else "These are fixed teaching records, not live weather.")
    return "\n".join(lines)


def run_workflow(task: WeatherTask, service: WeatherService) -> str:
    task = WeatherTask.model_validate(task)
    readings = []
    for city in task.cities:
        reading = service.read(city)
        if task.fahrenheit:
            reading = convert_temperature(reading)
        readings.append(reading)
    return render_brief(task, tuple(readings))


def main() -> None:
    parser = argparse.ArgumentParser(description="A form-driven workflow; no LLM calls.")
    parser.add_argument("--cities", nargs="+", choices=("Tokyo", "Paris"), default=["Tokyo"])
    parser.add_argument("--fahrenheit", action="store_true")
    parser.add_argument("--language", choices=("zh-CN", "en"), default="zh-CN")
    args = parser.parse_args()
    task = WeatherTask(cities=tuple(args.cities), fahrenheit=args.fahrenheit, language=args.language)
    service = WeatherService()
    print(run_workflow(task, service))
    print("source calls:", service.calls)
    print("model calls: 0")


if __name__ == "__main__":
    main()
