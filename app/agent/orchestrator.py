"""Agent planner loop。

P2 範圍：read-only 工具 + tool calling 對話流。
P3+ 會擴充寫入類工具、ask_user、retry escalation 等。
"""

import json
import threading
from typing import Iterator, Optional

from app.agent.llm.base import LLMClient, Message
from app.agent.registry import ToolRegistry


SYSTEM_BASE = """你是辦公自動化助理，協助使用者操作 Excel/Word 與批次產報告。

行為準則：
- 優先使用工具取得真實資訊，而不要靠猜。
- 缺少必要資訊時，先請使用者補充（簡短發問），不要任意填入預設值。
- 工具呼叫遇到錯誤訊息（response 中含 "error"）時，先告知使用者並停止。
- 回答完成且無待辦時，最後以「DONE」結尾。
"""


class AgentOrchestrator:
    """單回合 = 一次 user 訊息進，跑完所有 tool call 直到 LLM 給最終文字。"""

    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        model: str,
        context: Optional[dict] = None,
        max_iters: int = 8,
    ):
        self.llm = llm
        self.registry = registry
        self.model = model
        self.context = context or {}
        self.max_iters = max_iters
        self._cancel = threading.Event()
        self.messages = [Message(role="system", text=self._build_system_prompt())]

    # ---- public ----

    def reset(self):
        self._cancel.clear()
        self.messages = [Message(role="system", text=self._build_system_prompt())]

    def cancel(self):
        self._cancel.set()

    def add_user_message(self, text: str):
        self._cancel.clear()
        self.messages.append(Message(role="user", text=text))

    def step(self) -> Iterator[Message]:
        """處理已加入的 user 訊息：呼叫 LLM、執行工具、再呼叫 LLM…直到拿到最終文字。"""
        for _ in range(self.max_iters):
            if self._cancel.is_set():
                yield Message(role="assistant", text="[已中止]")
                return

            try:
                resp = self.llm.chat(
                    self.messages,
                    model=self.model,
                    tools=self.registry.schemas(),
                )
            except Exception as e:
                err = Message(role="assistant", text=f"[LLM 錯誤] {e}")
                self.messages.append(err)
                yield err
                return

            self.messages.append(resp)
            yield resp

            if not resp.tool_calls:
                return  # 最終文字回覆

            for tc in resp.tool_calls:
                if self._cancel.is_set():
                    yield Message(role="assistant", text="[已中止]")
                    return
                result = self.registry.run(tc.name, tc.arguments)
                tool_msg = Message(
                    role="tool",
                    text=json.dumps(result, ensure_ascii=False, default=str),
                    tool_name=tc.name,
                )
                self.messages.append(tool_msg)
                yield tool_msg

        yield Message(role="assistant", text=f"[已達迴圈上限 {self.max_iters}]")

    # ---- internal ----

    def _build_system_prompt(self):
        prompt = SYSTEM_BASE
        if self.context:
            prompt += "\n當前 UI 已選設定（你可直接使用，不需再問使用者）："
            for key, value in self.context.items():
                if value not in (None, "", 0):
                    prompt += f"\n- {key}: {value}"
        return prompt
