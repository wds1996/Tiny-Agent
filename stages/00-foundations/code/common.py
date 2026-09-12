"""Request text and small I/O checks shared by the three Stage 00 examples."""
from __future__ import annotations

import argparse
import os
from typing import Any


CITIES = ("Tokyo", "Paris")
LANGUAGES = ("zh-CN", "en")


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} before running this example.")
    return value


def create_client() -> Any:
    api_key = required_env("DEEPSEEK_API_KEY")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Install the chapter dependencies first:\n"
            "python -m pip install -r stages/00-foundations/code/requirements.txt"
        ) from exc
    return OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
        timeout=30.0,
        max_retries=0,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read a fixed teaching weather record.")
    parser.add_argument("--city", choices=CITIES, default="Tokyo")
    parser.add_argument("--language", choices=LANGUAGES, default="zh-CN")
    return parser.parse_args()


def request_for(city: str, language: str) -> str:
    if city not in CITIES or language not in LANGUAGES:
        raise ValueError("Unsupported city or language.")
    if language == "zh-CN":
        return f"请读取 {city} 的教学天气记录，告诉我摄氏温度和天气状况。这不是实时天气查询。"
    return (
        f"Read {city}'s teaching weather record and report its temperature in "
        "Celsius and condition. This is not a live weather query."
    )


def require_completed(response: Any) -> None:
    if response.status != "completed":
        raise RuntimeError(f"Response did not complete: {response.status}")


def require_text(response: Any) -> str:
    require_completed(response)
    if any(item.type == "function_call" for item in response.output):
        raise RuntimeError("Expected an answer, but received another tool request.")
    text = response.output_text
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Response completed without usable text.")
    return text.strip()
