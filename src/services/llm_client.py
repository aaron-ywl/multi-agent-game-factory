"""
LLM 客户端 - OpenAI 兼容接口
支持同步 + 异步调用，思考模式模型，streaming
"""
import json
import structlog
from typing import Optional, Any
from openai import OpenAI, AsyncOpenAI

from src.config.settings import settings

logger = structlog.get_logger()


class LLMClient:
    """OpenAI-compatible LLM 客户端（单例）"""

    _instance: Optional["LLMClient"] = None
    _async_client: Optional[AsyncOpenAI] = None

    def __new__(cls) -> "LLMClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                timeout=60.0,
                max_retries=2,
            )
        return cls._instance

    @property
    def async_client(self) -> AsyncOpenAI:
        if self._async_client is None:
            self._async_client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                timeout=180.0,
                max_retries=2,
            )
        return self._async_client

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[dict] = None,
    ) -> str:
        """同步对话"""
        kwargs = {
            "model": settings.OPENAI_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        resp = self._client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content or ""

        # 收集 reasoning_content（Qwen 思考模式）
        reasoning = getattr(resp.choices[0].message, "reasoning_content", None)
        if reasoning:
            logger.debug("llm_reasoning", length=len(reasoning))

        return self._strip_think_tags(content)

    async def achat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[dict] = None,
    ) -> str:
        """异步对话"""
        kwargs = {
            "model": settings.OPENAI_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        resp = await self.async_client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content or ""

        reasoning = getattr(resp.choices[0].message, "reasoning_content", None)
        if reasoning:
            logger.debug("llm_reasoning_async", length=len(reasoning))

        return self._strip_think_tags(content)

    def chat_json(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 4096) -> dict:
        """同步对话并解析 JSON 输出"""
        text = self.chat(messages, temperature=temperature, max_tokens=max_tokens,
                         response_format={"type": "json_object"})
        return json.loads(self._extract_json(text))

    async def achat_json(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 4096) -> dict:
        """异步对话并解析 JSON 输出"""
        text = await self.achat(messages, temperature=temperature, max_tokens=max_tokens,
                                response_format={"type": "json_object"})
        return json.loads(self._extract_json(text))

    def embed(self, texts: list[str]) -> list[list[float]]:
        """文本向量化（带超时和重试）"""
        import time
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                resp = self._client.embeddings.create(
                    model=settings.EMBEDDING_MODEL,
                    input=texts,
                )
                return [d.embedding for d in resp.data]
            except Exception as e:
                logger.warning("embed_failed", attempt=attempt, error=str(e))
                if attempt < max_retries:
                    time.sleep(1.0 * (attempt + 1))
                else:
                    raise

    @staticmethod
    def _strip_think_tags(text: str) -> str:
        """去除 Qwen 思考模式的 <think> 标签"""
        import re
        if not text:
            return text
        text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
        return text

    @staticmethod
    def _extract_json(text: str) -> str:
        """从文本中提取 JSON（容错）"""
        text = text.strip()
        # 尝试找 ```json ... ``` 包裹
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            return text[start:end].strip()
        if "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            return text[start:end].strip()
        return text


llm_client = LLMClient()
