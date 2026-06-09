"""
AIGC 图片生成服务 — 调用 Qwen-Image-2.0 生成实际游戏美术资产
"""
import time
import base64
import structlog
from pathlib import Path
from typing import Optional
from openai import OpenAI

from src.config.settings import settings

logger = structlog.get_logger()
OUTPUT_DIR = Path(__file__).parent.parent.parent / "outputs" / "images"


class ImageGenService:
    """游戏美术资产生成器 — 调用 Qwen-Image-2.0"""

    _instance: Optional["ImageGenService"] = None

    def __new__(cls) -> "ImageGenService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                timeout=180.0,
                max_retries=2,
            )
        return cls._instance

    def generate(self, prompt: str, size: str = "1024x1024") -> Optional[dict]:
        """
        调用 Qwen-Image-2.0 生成图片
        返回: {"url": str, "local_path": str, "prompt": str, "size": str}
        """
        # 限制 Prompt 长度（Qwen-Image 有 1024 token 入参限制）
        if len(prompt) > 800:
            prompt = prompt[:800]

        try:
            resp = self._client.images.generate(
                model="Qwen-Image-2.0",
                prompt=prompt,
                n=1,
                size=size,
            )
            url = resp.data[0].url if resp.data else None
            if not url:
                logger.error("image_gen_no_url")
                return None

            logger.info("image_gen_done", url=url[:80])
            return {
                "url": url,
                "prompt": prompt,
                "size": size,
            }
        except Exception as e:
            logger.error("image_gen_failed", error=str(e)[:100])
            return None

    def generate_character(self, name: str, desc: str, art_style: str = "") -> Optional[dict]:
        """生成二次元角色立绘"""
        style_prefix = "anime character design, cel-shading, vibrant colors, clean linework, full body illustration"
        if art_style:
            style_prefix = art_style
        prompt = f"{style_prefix}, character named {name}, {desc}, game character design, high quality, 8K"
        return self.generate(prompt)

    def generate_environment(self, scene_desc: str, art_style: str = "") -> Optional[dict]:
        """生成游戏场景图"""
        style_prefix = "game environment concept art, anime style background"
        if art_style:
            style_prefix = art_style
        prompt = f"{style_prefix}, {scene_desc}, wide shot, cinematic lighting, 8K"
        return self.generate(prompt)

    def batch_generate(self, prompts: list[dict]) -> list[dict]:
        """
        批量生成图片
        prompts: [{"type": "character"|"environment"|"ui", "prompt": str, "name": str}, ...]
        """
        results = []
        for i, p in enumerate(prompts):
            logger.info("image_batch_gen", idx=i, total=len(prompts), name=p.get("name", ""))
            result = self.generate(p.get("prompt", ""))
            if result:
                result["name"] = p.get("name", f"asset_{i}")
                result["type"] = p.get("type", "general")
                result["index"] = i
                results.append(result)
            time.sleep(0.5)  # 避免请求过于密集
        return results


image_gen = ImageGenService()
