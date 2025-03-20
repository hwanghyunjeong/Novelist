"""Story retriever implementation."""

from typing import Dict, List, Optional, Any
from langchain_openai import OpenAIEmbeddings
from langchain.schema.embeddings import Embeddings
from langchain.schema.retriever import BaseRetriever
from langchain_core.documents import Document
import asyncio


class BaseVectorRetriever:
    """Base class for all vector retrievers."""

    def __init__(
        self,
        embedding_provider: Embeddings,
        db_manager,  # LangchainNeo4jDBManager 인스턴스
        index_name: str,
        node_label: str,
        embedding_property: str,
        text_property: str,
        k: int = 6,
    ):
        self.embeddings = embedding_provider
        self.db_manager = db_manager
        self.index_name = index_name
        self.node_label = node_label
        self.embedding_property = embedding_property
        self.text_property = text_property
        self.k = k

    def _get_retrieval_query(self) -> str:
        """Override this method to provide specific retrieval query."""
        raise NotImplementedError

    async def retrieve(self, query: str) -> List[Document]:
        """Retrieve similar documents."""
        # 쿼리 임베딩 생성
        query_embedding = self.embeddings.embed_query(query)

        # 검색 쿼리 실행
        results = self.db_manager.query(
            query=self._get_retrieval_query(),
            params={"embedding": query_embedding, "k": self.k},
        )

        # 결과를 Document 형식으로 변환
        documents = []
        for result in results:
            doc = Document(
                page_content=result[self.text_property],
                metadata={
                    "score": result.get("score", 0.0),
                    "scripts": result.get("scripts", []),
                    f"{self.node_label.lower()}_id": result.get("id"),
                },
            )
            documents.append(doc)

        return documents


class StorylineRetriever(BaseVectorRetriever):
    """Retriever for storyline vectors."""

    def _get_retrieval_query(self) -> str:
        return """
        CALL db.index.vector.queryNodes($index_name, $k, $embedding)
        YIELD node, score
        WITH node as unit, score
        MATCH (unit)-[:INCLUDES]->(script:StoryScript)
        WITH unit, score, COLLECT(script.content) as contents
        RETURN unit.storyline as storyline, score, 
        contents as scripts, unit.id as id
        """


class ActRetriever(BaseVectorRetriever):
    """Retriever for action vectors."""

    def _get_retrieval_query(self) -> str:
        return """
        CALL db.index.vector.queryNodes($index_name, $k, $embedding)
        YIELD node, score
        WITH node as act, score
        MATCH (script:StoryScript)-[:PERFORMS]->(act)
        WITH act, score, COLLECT(script.content) as contents
        RETURN act.act as act, score,
        contents as scripts, act.id as id
        """


class EmotionRetriever(BaseVectorRetriever):
    """Retriever for emotion vectors."""

    def _get_retrieval_query(self) -> str:
        return """
        CALL db.index.vector.queryNodes($index_name, $k, $embedding)
        YIELD node, score
        WITH node as emotion, score
        MATCH (script:StoryScript)-[:FEELS]->(emotion)
        WITH emotion, score, COLLECT(script.content) as contents
        RETURN emotion.emotion as emotion, score,
        contents as scripts, emotion.id as id
        """


class StoryRetriever:
    """통합 스토리 검색기"""

    def __init__(
        self,
        db_manager,  # LangchainNeo4jDBManager 인스턴스
        embeddings: Optional[OpenAIEmbeddings] = None,
        k: int = 6,
    ):
        """
        Args:
            db_manager: Neo4j 데이터베이스 매니저 인스턴스
            embeddings: 임베딩 제공자 (기본값: OpenAIEmbeddings)
            k: 각 검색에서 반환할 결과 수
        """
        if embeddings is None:
            embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

        self.storyline_retriever = StorylineRetriever(
            embedding_provider=embeddings,
            db_manager=db_manager,
            index_name="storylineVector",
            node_label="Unit",
            embedding_property="storylineEmbedding",
            text_property="storyline",
            k=k,
        )

        self.act_retriever = ActRetriever(
            embedding_provider=embeddings,
            db_manager=db_manager,
            index_name="actVector",
            node_label="Act",
            embedding_property="actEmbedding",
            text_property="act",
            k=k,
        )

        self.emotion_retriever = EmotionRetriever(
            embedding_provider=embeddings,
            db_manager=db_manager,
            index_name="emotionVector",
            node_label="Emotion",
            embedding_property="emotionEmbedding",
            text_property="emotion",
            k=k,
        )

    async def retrieve_all(self, query: str) -> Dict[str, List[Dict[str, Any]]]:
        """모든 벡터 인덱스에서 유사한 문서를 검색합니다."""
        # 모든 검색을 동시에 실행
        storylines_task = self.storyline_retriever.retrieve(query)
        acts_task = self.act_retriever.retrieve(query)
        emotions_task = self.emotion_retriever.retrieve(query)

        # 모든 결과 대기
        results = await asyncio.gather(storylines_task, acts_task, emotions_task)

        # 결과를 적절한 형식으로 변환
        return {
            "storylines": [
                {
                    "text": doc.page_content,
                    "score": doc.metadata.get("score", 0.0),
                    "scripts": doc.metadata.get("scripts", []),
                    "unit_id": doc.metadata.get("unit_id"),
                }
                for doc in results[0]
            ],
            "acts": [
                {
                    "text": doc.page_content,
                    "score": doc.metadata.get("score", 0.0),
                    "scripts": doc.metadata.get("scripts", []),
                    "act_id": doc.metadata.get("act_id"),
                }
                for doc in results[1]
            ],
            "emotions": [
                {
                    "text": doc.page_content,
                    "score": doc.metadata.get("score", 0.0),
                    "scripts": doc.metadata.get("scripts", []),
                    "emotion_id": doc.metadata.get("emotion_id"),
                }
                for doc in results[2]
            ],
        }

    def get_context_from_results(
        self, results: Dict[str, List[Dict[str, Any]]], k: int = 3
    ) -> str:
        """검색 결과에서 컨텍스트를 생성합니다."""
        context_parts = []

        # 스토리라인 컨텍스트
        if results["storylines"]:
            storylines = sorted(
                results["storylines"], key=lambda x: x["score"], reverse=True
            )[:k]
            context_parts.append("관련된 스토리라인:")
            for i, s in enumerate(storylines, 1):
                context_parts.append(f"{i}. {s['text']}")

        # 행동 컨텍스트
        if results["acts"]:
            acts = sorted(results["acts"], key=lambda x: x["score"], reverse=True)[:k]
            context_parts.append("\n관련된 행동:")
            for i, a in enumerate(acts, 1):
                context_parts.append(f"{i}. {a['text']}")

        # 감정 컨텍스트
        if results["emotions"]:
            emotions = sorted(
                results["emotions"], key=lambda x: x["score"], reverse=True
            )[:k]
            context_parts.append("\n관련된 감정:")
            for i, e in enumerate(emotions, 1):
                context_parts.append(f"{i}. {e['text']}")

        return "\n".join(context_parts)
