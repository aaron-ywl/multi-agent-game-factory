"""
生产级 Vector RAG 服务 — Milvus Lite + BM25 + Query Rewrite + Rerank
==============================================================
Chunk: 固定窗口 + Overlap + 语义边界感知
召回: 向量检索(Milvus) + BM25 关键词检索 双路混合
Rerank: bge-reranker-v2-m3 精排
过滤: similarity < 0.3 丢弃
"""
import hashlib
import time
import re
import math
import structlog
from collections import defaultdict
from pathlib import Path
from typing import Optional

from pymilvus import MilvusClient
from pymilvus.milvus_client import IndexParams

from src.config.settings import settings
from src.services.llm_client import llm_client

logger = structlog.get_logger()

MILVUS_DB = str(Path(__file__).parent.parent.parent / "milvus_data" / "game_kb.db")
COLLECTION_NAME = "game_dev_knowledge"
DIM = settings.EMBEDDING_DIM  # text-embedding-v1 = 1536
CHUNK_SIZE = 500      # 每块约 500 字符（≈125 中文 tokens）
CHUNK_OVERLAP = 125   # 相邻块重叠 125 字符（25%）
BM25_k1 = 1.5         # BM25 参数
BM25_b = 0.75

_cache: dict[str, tuple[list[dict], float]] = {}

# ========================================================
# 1. Chunk 切分: Overlap Sliding Window + 语义边界
# ========================================================

def _segment_by_boundary(text: str, max_chars: int, overlap: int) -> list[str]:
    """
    按语义边界切分文本为重叠滑动窗口
    优先级: 章节标题 > 段落 > 句子 > 字符切割
    每块不超过 max_chars，相邻块重叠 overlap 字符
    """
    # Step 1: 先按段落分割（保留语义完整性）
    paragraphs = re.split(r'\n\s*\n', text)

    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # 如果单个段落就超过限制，按句子切
        if len(para) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            # 按句号/分号切长段落
            sentences = re.split(r'(?<=[。！？；])', para)
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                if len(current) + len(sent) <= max_chars:
                    current += sent
                else:
                    if current.strip():
                        chunks.append(current.strip())
                    # 保留上一块的末尾作为 overlap
                    overlap_text = current[-overlap:] if len(current) > overlap else current
                    current = overlap_text + sent if overlap_text.strip() else sent
            continue

        # 正常段落：能放就放，不能放就开新块
        if len(current) + len(para) + 1 <= max_chars:
            current += "\n" + para if current else para
        else:
            if current.strip():
                chunks.append(current.strip())
            # overlap: 上一块的末尾作为新块的开头
            overlap_text = current[-overlap:] if len(current) > overlap else (current if current else "")
            current = (overlap_text + "\n" + para) if overlap_text.strip() else para

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _extract_metadata(text: str, source: str) -> dict:
    """提取元数据：章节、标题、关键词密度"""
    meta = {"source": source, "section": "", "keywords": []}
    # 提取章节标题
    title_match = re.match(r'^([^\n]{2,60})\n', text)
    if title_match:
        meta["section"] = title_match.group(1)[:100]
    # 提取高频游戏术语作为关键词
    game_terms = re.findall(r'(TTK|HP|DPS|RPG|MOBA|FPS|PVP|PVE|NPC|AI|ECS|ATB|Elo|'
                           r'伤害|攻击|防御|技能|冷却|波次|僵尸|植物|阳光|塔防|'
                           r'卡牌|回合|抽卡|心流|关卡|平衡|数值|架构)', text)
    if game_terms:
        meta["keywords"] = list(set(game_terms))[:5]
    return meta


# ========================================================
# 2. BM25 检索器 (内存级)
# ========================================================

class BM25Index:
    """轻量 BM25 关键词检索索引"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: list[str] = []
        self.doc_metadata: list[dict] = []
        self.term_freq: list[dict] = []     # 每篇文档的词频
        self.doc_len: list[int] = []        # 每篇文档长度
        self.avg_doc_len: float = 0
        self.idf: dict[str, float] = {}     # 逆文档频率
        self.total_docs = 0

    def _tokenize(self, text: str) -> list[str]:
        """中文分词 + 英文分词混合"""
        # 提取中文字符（2-4字词组）和英文单词
        tokens = []
        # 英文单词
        eng_words = re.findall(r'[a-zA-Z]{2,}', text)
        tokens.extend(w.lower() for w in eng_words)
        # 中文 bigram + trigram
        chinese = re.sub(r'[^一-鿿]', '', text)
        for i in range(len(chinese) - 1):
            tokens.append(chinese[i:i+2])
        for i in range(len(chinese) - 2):
            tokens.append(chinese[i:i+3])
        # 保留数字+单位组合
        num_units = re.findall(r'\d+[秒%个级波次回合]?', text)
        tokens.extend(num_units)
        return tokens

    def index(self, documents: list[str], metadatas: list[dict] = None):
        """构建 BM25 索引"""
        self.documents = documents
        self.doc_metadata = metadatas or [{}] * len(documents)
        self.total_docs = len(documents)
        doc_freq = defaultdict(int)  # 出现该词的文档数

        for doc in documents:
            tokens = self._tokenize(doc)
            tf = defaultdict(int)
            for t in tokens:
                tf[t] += 1
            self.term_freq.append(dict(tf))
            self.doc_len.append(len(tokens))
            for t in set(tokens):
                doc_freq[t] += 1

        self.avg_doc_len = sum(self.doc_len) / max(1, self.total_docs)

        # 计算 IDF
        for term, df in doc_freq.items():
            self.idf[term] = math.log((self.total_docs - df + 0.5) / (df + 0.5) + 1)

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """BM25 检索"""
        if not self.documents:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores = []
        for i in range(self.total_docs):
            score = 0
            for token in query_tokens:
                if token not in self.idf:
                    continue
                tf = self.term_freq[i].get(token, 0)
                if tf == 0:
                    continue
                doc_len_norm = self.doc_len[i] / self.avg_doc_len
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len_norm)
                score += self.idf[token] * numerator / denominator

            if score > 0:
                scores.append({
                    "index": i,
                    "content": self.documents[i][:800],
                    "metadata": self.doc_metadata[i],
                    "score": score,
                    "source": "bm25",
                })

        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_k]


# ========================================================
# 3. Rerank 服务
# ========================================================

async def _rerank(query: str, documents: list[str], top_n: int = 5) -> list[dict]:
    """调用 bge-reranker-v2-m3 精排"""
    if not documents:
        return []

    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.OPENAI_BASE_URL}/rerank",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={
                    "model": "bge-reranker-v2-m3",
                    "query": query,
                    "documents": documents,
                    "top_n": min(top_n, len(documents)),
                },
            )
            if resp.status_code != 200:
                logger.warning("rerank_api_failed", status=resp.status_code)
                return []

            data = resp.json()
            results = []
            for r in data.get("results", []):
                results.append({
                    "index": r["index"],
                    "relevance_score": r["relevance_score"],
                })
            return results
    except Exception as e:
        logger.warning("rerank_error", error=str(e)[:80])
        return []


# ========================================================
# 4. Query Rewrite
# ========================================================

async def _rewrite_query(query: str) -> list[str]:
    """
    LLM 改写查询为 3 个变体，覆盖不同角度
    原始: "塔防数值怎么设"
    → ["游戏塔防 数值平衡公式 伤害计算",
       "Tower Defense 植物僵尸 HP/ATK/DPS 设计",
       "波次难度曲线 数值递增公式"]
    """
    prompt = f"""你是游戏设计专家。将用户查询改写为3个搜索变体，覆盖不同角度。

原始查询: {query}

规则:
1. 变体1: 中文学术/专业表述（补充领域术语）
2. 变体2: 中英混合/英文表述（英文学术语境）
3. 变体3: 具体场景/公式表述（带上数值单位、公式关键词）
4. 每个变体不超过50字
5. 用 <REWRITE> 和 </REWRITE> 包裹每个变体

输出:
<REWRITE>变体1</REWRITE>
<REWRITE>变体2</REWRITE>
<REWRITE>变体3</REWRITE>"""

    try:
        resp = await llm_client.achat(
            [{"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=200
        )
        variants = re.findall(r'<REWRITE>(.*?)</REWRITE>', resp, re.DOTALL)
        variants = [v.strip() for v in variants if v.strip()]
        if not variants:
            return [query]
        logger.debug("query_rewrite", original=query[:40], variants=len(variants))
        return variants[:3]
    except Exception as e:
        logger.warning("query_rewrite_failed", error=str(e)[:80])
        return [query]


# ========================================================
# 5. 主服务: MilvusRAG (升级版)
# ========================================================

class MilvusRAGService:
    """生产级 RAG: Milvus + BM25 + Query Rewrite + Rerank + Score Filter"""

    _instance: Optional["MilvusRAGService"] = None

    def __new__(cls) -> "MilvusRAGService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        Path(MILVUS_DB).parent.mkdir(parents=True, exist_ok=True)
        # 清理可能残留的文件锁（上一个进程异常退出时可能遗留）
        lock_path = Path(MILVUS_DB) / "LOCK"
        if lock_path.exists():
            try:
                lock_path.unlink()
            except OSError:
                pass
        self._client = MilvusClient(MILVUS_DB)
        self._bm25 = BM25Index(k1=BM25_k1, b=BM25_b)
        self._all_docs: list[dict] = []  # 保存所有文档用于 BM25 + rerank

        if self._client.has_collection(COLLECTION_NAME):
            self._client.load_collection(COLLECTION_NAME)
            # 从 Milvus 恢复文档到 BM25
            self._rebuild_bm25_from_milvus()
            logger.info("milvus_loaded", name=COLLECTION_NAME, docs=len(self._all_docs))
        else:
            self._client.create_collection(
                collection_name=COLLECTION_NAME, dimension=DIM,
                metric_type="COSINE", auto_id=True, enable_dynamic_field=True,
            )
            self._client.load_collection(COLLECTION_NAME)
            logger.info("milvus_created", name=COLLECTION_NAME, dim=DIM)

        # 索引（milvus-lite 持久化后索引已存在，建前先查，避免重复创建报错）
        try:
            # list_indexes 返回已有索引名列表，index 已存在就跳过
            existing_indexes = self._client.list_indexes(collection_name=COLLECTION_NAME)
            if not existing_indexes:
                idx = IndexParams()
                idx.add_index(field_name="vector", index_type="IVF_FLAT", metric_type="COSINE", params={"nlist": 128})
                self._client.create_index(collection_name=COLLECTION_NAME, index_params=idx)
        except Exception:
            pass

    def _rebuild_bm25_from_milvus(self):
        """从 Milvus 恢复文档重建 BM25 索引"""
        try:
            # Milvus 不支持直接导出全部数据，用游标分页
            # 简化方案：查询时用零向量扫全表
            results = self._client.query(
                collection_name=COLLECTION_NAME,
                filter="type == 'game_dev_knowledge'",
                output_fields=["content", "source", "section", "type"],
                limit=10000,
            )
            if results:
                docs = [r.get("content", "") for r in results]
                metas = [{"source": r.get("source", ""), "section": r.get("section", ""), "type": r.get("type", "")} for r in results]
                self._all_docs = [{"content": d, "metadata": m} for d, m in zip(docs, metas)]
                self._bm25.index(docs, metas)
        except Exception as e:
            logger.warning("bm25_rebuild_failed", error=str(e)[:80])

    # ===== 检索: Vector + BM25 → Rerank → Score Filter =====

    async def retrieve(self, query: str, top_k: int = 5,
                       use_rewrite: bool = True, score_threshold: float = 0.3) -> list[dict]:
        """生产级 RAG 检索"""
        cache_key = hashlib.md5(f"{query}:{top_k}".encode()).hexdigest()
        if cache_key in _cache:
            results, ts = _cache[cache_key]
            if time.time() - ts < settings.VECTOR_CACHE_TTL_SECONDS:
                return results

        # Step 0: Query Rewrite — 生成 3 个搜索变体
        queries = [query]
        if use_rewrite:
            variants = await _rewrite_query(query)
            queries = variants if variants else [query]

        # Step 1: 多路召回 (每路 top_k * 2，为 rerank 留余量)
        all_candidates: dict[str, dict] = {}  # keyed by content hash for dedup

        for q in queries:
            # 1a. Vector 检索
            try:
                embedding = llm_client.embed([q])[0]
                vec_results = self._client.search(
                    collection_name=COLLECTION_NAME, data=[embedding],
                    limit=top_k * 2, anns_field="vector",
                    output_fields=["content", "source", "section", "type"],
                )
                if vec_results and vec_results[0]:
                    for hit in vec_results[0]:
                        entity = hit.get("entity", {})
                        content = entity.get("content", "")[:800]
                        content_hash = hashlib.md5(content.encode()).hexdigest()
                        dist = hit.get("distance", 0)
                        if dist < score_threshold:
                            continue
                        if content_hash not in all_candidates or dist > all_candidates[content_hash].get("score", 0):
                            all_candidates[content_hash] = {
                                "content": content,
                                "metadata": {
                                    "source": entity.get("source", ""),
                                    "section": entity.get("section", ""),
                                    "type": entity.get("type", ""),
                                },
                                "score": dist,
                                "source": "vector",
                            }
            except Exception as e:
                logger.warning("vector_search_failed", error=str(e)[:60])

            # 1b. BM25 关键词检索
            try:
                bm25_results = self._bm25.search(q, top_k=top_k * 2)
                for r in bm25_results:
                    content_hash = hashlib.md5(r["content"].encode()).hexdigest()
                    # BM25 score 归一化到 [0,1] 近似值
                    bm25_score = min(r["score"] / 10.0, 0.95)
                    if content_hash not in all_candidates or bm25_score > all_candidates[content_hash].get("score", 0):
                        all_candidates[content_hash] = {
                            "content": r["content"],
                            "metadata": r["metadata"],
                            "score": bm25_score,
                            "source": "bm25",
                        }
            except Exception as e:
                pass

        candidates = list(all_candidates.values())
        if not candidates:
            return []

        # Step 2: Rerank 精排
        candidate_docs = [c["content"] for c in candidates]
        rerank_results = await _rerank(query, candidate_docs, top_n=min(top_k + 3, len(candidates)))

        if rerank_results:
            # 用 rerank 结果重排序
            reranked = []
            for rr in rerank_results:
                idx = rr["index"]
                if idx < len(candidates):
                    c = candidates[idx].copy()
                    c["score"] = rr["relevance_score"]
                    c["source"] = f"{c['source']}+rerank"
                    reranked.append(c)
            candidates = reranked

        # Step 3: Score filter
        filtered = [c for c in candidates if c.get("score", 0) >= score_threshold]

        # Step 4: 排序取 top_k
        filtered.sort(key=lambda x: x.get("score", 0), reverse=True)
        top_results = filtered[:top_k]

        # 格式化输出
        docs = []
        for r in top_results:
            docs.append({
                "id": hashlib.md5(r["content"].encode()).hexdigest()[:16],
                "content": r["content"],
                "metadata": r["metadata"],
                "score": round(r.get("score", 0), 4),
                "retrieval_method": r.get("source", "unknown"),
            })

        _cache[cache_key] = (docs, time.time())
        logger.debug("rag_retrieve",
                     query=query[:50],
                     candidates=len(all_candidates),
                     after_rerank=len(docs),
                     scores=[round(d["score"], 3) for d in docs[:3]])
        return docs

    # ===== 索引: 改进的 Chunk 切割 =====

    def index_documents(self, documents: list[dict]) -> int:
        """批量入库文档（使用 overlap sliding window chunking）"""
        if not documents:
            return 0

        # Step 1: 用新算法切分所有文档
        all_chunks = []
        for doc in documents:
            raw_text = doc.get("content", "")
            source = doc.get("metadata", {}).get("source", "")
            chunks = _segment_by_boundary(raw_text, CHUNK_SIZE, CHUNK_OVERLAP)
            for i, chunk in enumerate(chunks):
                meta = _extract_metadata(chunk, source)
                meta["chunk_index"] = i
                meta["total_chunks"] = len(chunks)
                all_chunks.append({
                    "content": chunk,
                    "metadata": meta,
                })

        if not all_chunks:
            return 0

        # Step 2: Vector embedding + 入库 Milvus
        try:
            embeddings = llm_client.embed([c["content"] for c in all_chunks])
            data = []
            for i, chunk in enumerate(all_chunks):
                data.append({
                    "vector": embeddings[i],
                    "content": chunk["content"][:1500],
                    "source": chunk["metadata"].get("source", ""),
                    "section": chunk["metadata"].get("section", ""),
                    "type": chunk["metadata"].get("type", "game_dev_knowledge"),
                })
            self._client.insert(collection_name=COLLECTION_NAME, data=data)
        except Exception as e:
            logger.error("milvus_insert_failed", error=str(e)[:100])
            return 0

        # Step 3: 同时构建 BM25 索引
        self._all_docs.extend(all_chunks)
        bm25_docs = [c["content"] for c in self._all_docs]
        bm25_metas = [c["metadata"] for c in self._all_docs]
        self._bm25.index(bm25_docs, bm25_metas)

        logger.info("rag_indexed", chunks=len(all_chunks),
                     overlap=CHUNK_OVERLAP, size=CHUNK_SIZE,
                     total_bm25=self._all_docs.__len__())
        return len(all_chunks)

    def index_pdf(self, filepath: str) -> int:
        documents = _parse_pdf_text(filepath)
        return self.index_documents(documents) if documents else 0

    def index_pdf_directory(self, directory: str) -> int:
        total = 0
        pdf_dir = Path(directory)
        for pdf_file in sorted(pdf_dir.glob("*.pdf")):
            count = self.index_pdf(str(pdf_file))
            total += count
            logger.info("pdf_indexed", file=pdf_file.name, chunks=count)
        return total

    def reindex(self) -> int:
        try:
            if self._client.has_collection(COLLECTION_NAME):
                self._client.drop_collection(COLLECTION_NAME)
            self._all_docs.clear()
            self._bm25 = BM25Index(k1=BM25_k1, b=BM25_b)
            self._init()
            _cache.clear()
            return 0
        except Exception as e:
            logger.error("reindex_failed", error=str(e)[:80])
            return -1

    @property
    def document_count(self) -> int:
        try:
            stats = self._client.get_collection_stats(COLLECTION_NAME)
            return stats.get("row_count", len(self._all_docs))
        except Exception:
            return len(self._all_docs)


def _parse_pdf_text(filepath: str) -> list[dict]:
    """解析 PDF 文件为文档列表"""
    filename = Path(filepath).name
    try:
        import PyPDF2
        with open(filepath, "rb") as f:
            pdf = PyPDF2.PdfReader(f)
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
    except Exception:
        try:
            import pdfplumber
            with pdfplumber.open(filepath) as pdf:
                full_text = ""
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"
        except Exception as e:
            logger.error("pdf_parse_failed", file=filename, error=str(e)[:80])
            return []

    return [{"content": full_text, "metadata": {"source": filename, "type": "game_dev_knowledge"}}]


# 单例
vector_rag = MilvusRAGService()
