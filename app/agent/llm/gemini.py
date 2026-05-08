"""Gemini 引擎 client（使用 Google GenAI 統一 SDK）。

注意：舊版 `google-generativeai` 已於 2025 年棄用；本檔使用新版
`google-genai`（匯入 `from google import genai`）。
"""

import json
import os

try:
    from google import genai
    from google.genai import types as genai_types

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None
    genai_types = None

from .base import LLMClient, Message, ToolCall


class GeminiClient(LLMClient):
    def __init__(self, api_key=None):
        self.api_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or ""
        )
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

    # ---- chat ----

    def chat(self, messages, model=None, tools=None):
        client = self._ensure_client()
        if client is None:
            raise RuntimeError("Gemini client 不可用：套件未安裝或 API key 未設定。")

        contents, system_instruction = self._convert_messages(messages)

        gemini_tools = None
        if tools:
            decls = [
                genai_types.FunctionDeclaration(
                    name=t["name"],
                    description=t.get("description", ""),
                    parameters_json_schema=t.get("parameters", {"type": "object"}),
                )
                for t in tools
            ]
            gemini_tools = [genai_types.Tool(function_declarations=decls)]

        config = genai_types.GenerateContentConfig(
            tools=gemini_tools,
            system_instruction=system_instruction or None,
        )

        response = client.models.generate_content(
            model=model or "gemini-2.5-flash",
            contents=contents,
            config=config,
        )

        return self._parse_response(response)

    @staticmethod
    def _convert_messages(messages):
        """轉成 Gemini Content 列表 + system_instruction 字串。"""
        contents = []
        system_parts = []

        for msg in messages:
            if msg.role == "system":
                if msg.text:
                    system_parts.append(msg.text)
                continue

            if msg.role == "user":
                contents.append(
                    genai_types.Content(
                        role="user",
                        parts=[genai_types.Part(text=msg.text or "")],
                    )
                )
            elif msg.role == "assistant":
                parts = []
                if msg.text:
                    parts.append(genai_types.Part(text=msg.text))
                for tc in msg.tool_calls:
                    parts.append(
                        genai_types.Part(
                            function_call=genai_types.FunctionCall(
                                name=tc.name,
                                args=tc.arguments or {},
                            )
                        )
                    )
                if parts:
                    contents.append(genai_types.Content(role="model", parts=parts))
            elif msg.role == "tool":
                # 解析工具回傳結果為 dict（function_response 需要 dict）
                response_obj = GeminiClient._coerce_response(msg.text)
                contents.append(
                    genai_types.Content(
                        role="tool",
                        parts=[
                            genai_types.Part.from_function_response(
                                name=msg.tool_name,
                                response=response_obj,
                            )
                        ],
                    )
                )

        return contents, "\n\n".join(system_parts)

    @staticmethod
    def _coerce_response(text):
        if not text:
            return {"result": ""}
        try:
            value = json.loads(text)
            if isinstance(value, dict):
                return value
            return {"result": value}
        except (json.JSONDecodeError, TypeError):
            return {"result": text}

    @staticmethod
    def _parse_response(response):
        out = Message(role="assistant")

        # 便利存取：response.function_calls
        function_calls = getattr(response, "function_calls", None) or []
        for fc in function_calls:
            args = dict(fc.args) if getattr(fc, "args", None) else {}
            out.tool_calls.append(ToolCall(name=fc.name, arguments=args))

        # 文字部分
        text = getattr(response, "text", None)
        if text:
            out.text = text
            return out

        # 退而求其次：自行掃 candidates parts
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            content = getattr(candidates[0], "content", None)
            parts = getattr(content, "parts", None) or []
            collected_text = []
            for part in parts:
                if getattr(part, "function_call", None) and not function_calls:
                    fc = part.function_call
                    args = dict(fc.args) if getattr(fc, "args", None) else {}
                    out.tool_calls.append(ToolCall(name=fc.name, arguments=args))
                t = getattr(part, "text", None)
                if t:
                    collected_text.append(t)
            if collected_text:
                out.text = "".join(collected_text)

        return out
