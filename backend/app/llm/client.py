from collections.abc import Iterator
from typing import Protocol

from openai import OpenAI

ChatMessage = dict[str, str]  # {"role": ..., "content": ...}


class LLM(Protocol):
    def complete(self, messages: list[ChatMessage]) -> str: ...

    def stream(self, messages: list[ChatMessage]) -> Iterator[str]: ...


class OpenAIChat:
    def __init__(self, client: OpenAI, model: str):
        self._client = client
        self._model = model

    def complete(self, messages: list[ChatMessage]) -> str:
        response = self._client.chat.completions.create(model=self._model, messages=messages)
        return (response.choices[0].message.content or "").strip()

    def stream(self, messages: list[ChatMessage]) -> Iterator[str]:
        stream = self._client.chat.completions.create(model=self._model, messages=messages, stream=True)
        for event in stream:
            if event.choices and event.choices[0].delta.content:
                yield event.choices[0].delta.content
