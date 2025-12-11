"""
向量嵌入服务：将文本转换为向量。

支持：
- OpenAI embeddings（可选）
- 本地模型（sentence-transformers，优先）
- 向量相似度计算
"""

import logging
from typing import List, Optional
import numpy as np

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers 未安装，将使用简单的文本相似度")

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class EmbeddingService:
    """
    向量嵌入服务：将文本转换为向量。
    
    优先使用本地模型（sentence-transformers），如果没有则降级到关键词匹配。
    """
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        use_openai: bool = False,
        openai_api_key: Optional[str] = None,
    ):
        """
        初始化向量嵌入服务。
        
        Args:
            model_name: 本地模型名称（如 'paraphrase-multilingual-MiniLM-L12-v2'）
            use_openai: 是否使用 OpenAI embeddings
            openai_api_key: OpenAI API key（如果使用 OpenAI）
        """
        self.use_openai = use_openai and OPENAI_AVAILABLE
        self.openai_api_key = openai_api_key
        self.model = None
        self.embedding_dim = 384  # 默认维度
        
        # 初始化本地模型
        if not self.use_openai and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                model_name = model_name or "paraphrase-multilingual-MiniLM-L12-v2"
                logger.info(f"正在加载本地嵌入模型: {model_name}")
                self.model = SentenceTransformer(model_name)
                # 获取模型维度
                test_embedding = self.model.encode("test")
                self.embedding_dim = len(test_embedding)
                logger.info(f"✅ 本地嵌入模型加载成功，维度: {self.embedding_dim}")
            except Exception as e:
                logger.warning(f"加载本地嵌入模型失败: {e}，将使用简单相似度")
                self.model = None
        
        # 初始化 OpenAI（如果需要）
        if self.use_openai and OPENAI_AVAILABLE:
            if openai_api_key:
                openai.api_key = openai_api_key
            else:
                import os
                openai.api_key = os.getenv("OPENAI_API_KEY")
            
            if not openai.api_key:
                logger.warning("OpenAI API key 未设置，降级到本地模型")
                self.use_openai = False
        
        if not self.model and not self.use_openai:
            logger.warning("没有可用的嵌入模型，将使用简单相似度计算")
    
    async def embed(self, text: str) -> List[float]:
        """
        生成文本的向量嵌入。
        
        Args:
            text: 输入文本
            
        Returns:
            向量嵌入列表
        """
        if not text or not text.strip():
            return [0.0] * self.embedding_dim
        
        # 使用本地模型
        if self.model:
            try:
                embedding = self.model.encode(text, normalize_embeddings=True)
                return embedding.tolist()
            except Exception as e:
                logger.error(f"本地模型编码失败: {e}")
                return self._fallback_embedding(text)
        
        # 使用 OpenAI（如果配置）
        if self.use_openai:
            try:
                import asyncio
                response = await asyncio.to_thread(
                    openai.Embedding.create,
                    input=text,
                    model="text-embedding-ada-002",
                )
                return response['data'][0]['embedding']
            except Exception as e:
                logger.error(f"OpenAI 编码失败: {e}")
                return self._fallback_embedding(text)
        
        # 降级：返回简单的哈希向量
        return self._fallback_embedding(text)
    
    def _fallback_embedding(self, text: str) -> List[float]:
        """
        降级方案：生成简单的向量（基于词频）。
        
        这不是真正的向量嵌入，但可以用于基本的相似度计算。
        """
        # 简单的词频向量（固定维度）
        words = text.lower().split()
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # 生成固定维度的向量（使用哈希）
        embedding = [0.0] * self.embedding_dim
        for word, freq in word_freq.items():
            # 使用哈希将词映射到维度
            idx = hash(word) % self.embedding_dim
            embedding[idx] += freq * 0.1  # 归一化
        
        # 简单的归一化
        norm = sum(x * x for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        return embedding
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        计算两个向量的余弦相似度。
        
        Args:
            vec1: 向量1
            vec2: 向量2
            
        Returns:
            相似度 0.0 - 1.0
        """
        if len(vec1) != len(vec2):
            logger.warning(f"向量维度不匹配: {len(vec1)} vs {len(vec2)}")
            return 0.0
        
        try:
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            norm1 = sum(a * a for a in vec1) ** 0.5
            norm2 = sum(b * b for b in vec2) ** 0.5
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return dot_product / (norm1 * norm2)
        except Exception as e:
            logger.error(f"计算余弦相似度失败: {e}")
            return 0.0
    
    def batch_embed(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成向量嵌入（更高效）。
        
        Args:
            texts: 文本列表
            
        Returns:
            向量嵌入列表
        """
        if not texts:
            return []
        
        # 使用本地模型批量编码
        if self.model:
            try:
                embeddings = self.model.encode(
                    texts,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                return embeddings.tolist()
            except Exception as e:
                logger.error(f"批量编码失败: {e}，回退到单条编码")
                return [await self.embed(text) for text in texts]
        
        # 降级：单条编码
        return [await self.embed(text) for text in texts]









