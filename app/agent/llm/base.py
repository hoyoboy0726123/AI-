"""LLM provider 抽象介面。

所有 client 實作應盡量寬容：依賴未安裝、API key 未設、endpoint 不可達時，
list_models 回空 list、is_available 回 False，不應 raise，避免拖垮 UI。
"""

from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        """是否可用（依賴已安裝、有 API key 或 endpoint 可達）。"""

    @abstractmethod
    def list_models(self) -> list:
        """列出支援文字生成的模型名稱。"""

    @abstractmethod
    def list_vision_models(self) -> list:
        """列出支援多模態（vision）的模型名稱（reviewer 使用）。"""
