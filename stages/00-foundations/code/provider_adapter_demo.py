from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI


@dataclass(frozen=True)
class ModelRequest:
    """Provider-neutral request used by the tiny Runtime."""

    instructions: str
    input: str


@dataclass(frozen=True)
class ModelReply:
    """Small normalized reply returned to the Runtime."""

    text: str
    response_id: str
    model: str


class ModelAdapter(Protocol):
    """The Runtime depends on this interface, not on a provider SDK object."""

    provider_name: str

    def generate(self, request: ModelRequest) -> ModelReply:
        ...


@dataclass(frozen=True)
class ResponsesProviderConfig:
    provider_name: str
    api_key_env: str
    model: str
    base_url_env: str | None = None


class OpenAICompatibleResponsesAdapter:
    """Adapter for providers exposing an OpenAI-compatible Responses API.

    OpenAI itself and Alibaba Cloud Model Studio's Qwen Responses endpoint can
    both use the OpenAI Python SDK, but credentials, endpoints, model IDs, and
    supported provider features still remain provider-specific configuration.
    """

    def __init__(self, config: ResponsesProviderConfig) -> None:
        self.provider_name = config.provider_name
        self._model = config.model

        api_key = os.getenv(config.api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Missing {config.api_key_env}. Set the provider API key before running."
            )

        if config.base_url_env is None:
            self._client = OpenAI(api_key=api_key)
            return

        base_url = os.getenv(config.base_url_env)
        if not base_url:
            raise RuntimeError(
                f"Missing {config.base_url_env}. For Qwen, set it to the "
                "Alibaba Cloud Model Studio OpenAI-compatible base URL for "
                "the same region/workspace as DASHSCOPE_API_KEY."
            )

        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(self, request: ModelRequest) -> ModelReply:
        response = self._client.responses.create(
            model=self._model,
            instructions=request.instructions,
            input=request.input,
        )
        return ModelReply(
            text=response.output_text,
            response_id=response.id,
            model=response.model,
        )


def build_adapter(provider: str) -> ModelAdapter:
    if provider == "openai":
        return OpenAICompatibleResponsesAdapter(
            ResponsesProviderConfig(
                provider_name="OpenAI",
                api_key_env="OPENAI_API_KEY",
                model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
            )
        )

    if provider == "qwen":
        return OpenAICompatibleResponsesAdapter(
            ResponsesProviderConfig(
                provider_name="Qwen via Alibaba Cloud Model Studio",
                api_key_env="DASHSCOPE_API_KEY",
                base_url_env="DASHSCOPE_BASE_URL",
                model=os.getenv("QWEN_MODEL", "qwen3.8-max"),
            )
        )

    raise ValueError(f"Unsupported provider: {provider}")


def run_teacher_example(adapter: ModelAdapter) -> ModelReply:
    """Core application logic: deliberately contains no provider branch."""

    request = ModelRequest(
        instructions=(
            "You are a patient AI engineering teacher. "
            "Answer in concise, accurate Chinese."
        ),
        input=(
            "用两三句话解释：为什么 Agent Runtime 不应该直接依赖某一家模型"
            "提供商的 Response 对象？"
        ),
    )
    return adapter.generate(request)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider",
        choices=("openai", "qwen"),
        default="openai",
    )
    args = parser.parse_args()

    adapter = build_adapter(args.provider)
    reply = run_teacher_example(adapter)

    print(f"provider: {adapter.provider_name}")
    print(f"model: {reply.model}")
    print(f"response_id: {reply.response_id}")
    print("answer:")
    print(reply.text)


if __name__ == "__main__":
    main()
