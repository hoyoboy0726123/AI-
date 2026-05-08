"""Gemini 引擎 client（使用 Google GenAI 統一 SDK）。

注意：舊版 `google-generativeai` 已於 2025 年棄用；本檔使用新版
`google-genai`（匯入 `from google import genai`）。

若套件未安裝或 API key 未設定，所有方法皆優雅降級為空結果，
讓手動頁籤不受影響。
"""

import os

try:
    from google import genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None

from .base import LLMClient


class GeminiClient(LLMClient):
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
        self._client = None

    def _ensure_client(self):
        if not GEMINI_AVAILABLE or not self.api_key:
            return None
        if self._client is None:
            try:
                self._client = genai.Client(api_key=self.api_key)
            except Exception:
                self._client = None
        return self._client

    def is_available(self):
        return GEMINI_AVAILABLE and bool(self.api_key)

    def list_models(self):
        client = self._ensure_client()
        if client is None:
            return []
        try:
            names = []
            for m in client.models.list():
                actions = (
                    getattr(m, "supported_actions", None)
                    or getattr(m, "supported_generation_methods", None)
                    or []
                )
                if "generateContent" in actions:
                    raw = getattr(m, "name", "") or ""
                    names.append(raw.replace("models/", ""))
            return sorted(set(n for n in names if n))
        except Exception:
            return []

    def list_vision_models(self):
        # Gemini 1.5 / 2.x / 3.x 全系列為多模態
        return [m for m in self.list_models() if "gemini" in m.lower()]
