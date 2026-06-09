"""
游戏 AI Agent 系统配置
"""
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    """全局配置"""

    # LLM
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://www.aiping.cn/api/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "DeepSeek-V3.2")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-v1")

    # Vector RAG — Milvus Lite
    VECTOR_RAG_ENABLED: bool = True
    MILVUS_DB_DIR: str = "milvus_data"
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "game_dev_knowledge")
    VECTOR_TOP_K: int = int(os.getenv("VECTOR_TOP_K", "5"))
    VECTOR_CACHE_TTL_SECONDS: int = int(os.getenv("VECTOR_CACHE_TTL_SECONDS", "120"))
    EMBEDDING_DIM: int = 1536  # text-embedding-v1 输出维度

    # 知识库 PDF 目录
    KNOWLEDGE_PDF_DIR: str = str(PROJECT_ROOT / "data" / "knowledge_pdfs")

    # Application
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Pipeline limits
    MAX_LOOPBACKS: int = 3

    @property
    def llm_kwargs(self) -> dict:
        return {
            "model": self.OPENAI_MODEL,
            "api_key": self.OPENAI_API_KEY,
            "base_url": self.OPENAI_BASE_URL,
        }


settings = Settings()
