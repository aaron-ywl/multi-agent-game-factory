#!/usr/bin/env python3
"""
Milvus 知识库索引脚本
"""
import sys, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.vector_rag_service import vector_rag
from src.config.settings import settings

async def main():
    print(f"📚 PDF 目录: {settings.KNOWLEDGE_PDF_DIR}")
    print(f"📦 Milvus DB: milvus_data/game_kb.db")
    print(f"🔪 Chunk: {500}字 + {125}字 overlap")

    vector_rag.reindex()
    total = vector_rag.index_pdf_directory(settings.KNOWLEDGE_PDF_DIR)

    print(f"\n✅ 索引完成! {total} 个切块 (overlap sliding window)")
    print(f"📊 文档总数: {vector_rag.document_count}")

    if total > 0:
        results = await vector_rag.retrieve("游戏设计核心循环与战斗平衡公式", top_k=3)
        print(f"\n🔍 Query: '游戏设计核心循环与战斗平衡公式'")
        for i, r in enumerate(results):
            method = r.get('retrieval_method', '?')
            print(f"  [{i+1}] {r['score']:.4f} [{method}] 来源:{r['metadata']['source']}")
            print(f"       内容:{r['content'][:100]}...")

asyncio.run(main())
