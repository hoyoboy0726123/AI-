"""Ollama 本地引擎 client。

使用 stdlib urllib 直打 REST API，避免額外依賴。
P3 若需要更穩的 tool calling 再考慮加入官方 ollama Python lib。
"""

import json
import os
import urllib.request

from .base import LLMClient


class OllamaClient(LLMClient):
    VISION_KEYWORDS = (
        "llava",
        "bakllava",
        "moondream",
        "minicpm-v",
        "qwen2-vl",
        "qwen2.5-vl",
        "llama3.2-vision",
        "llama4-vision",
        "vision",
    )

    def __init__(self, endpoint=None, timeout=5):
        self.endpoint = (
            endpoint
            or os.environ.get("OLLAMA_ENDPOINT")
            or "http://localhost:11434"
        ).rstrip("/")
        self.timeout = timeout

    def _get(self, path):
        with urllib.request.urlopen(f"{self.endpoint}{path}", timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def is_available(self):
        try:
            self._get("/api/tags")
            return True
        except Exception:
            return False

    def list_models(self):
        try:
            data = self._get("/api/tags")
        except Exception:
            return []
        return sorted(
            m.get("name", "")
            for m in data.get("models", [])
            if m.get("name")
        )

    def list_vision_models(self):
        return [
            m
            for m in self.list_models()
            if any(k in m.lower() for k in self.VISION_KEYWORDS)
        ]
