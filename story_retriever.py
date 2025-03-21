"""Story retriever implementation."""

from typing import Dict, List, Optional, Any
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document


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

        self.embeddings = embeddings
        self.db_manager = db_manager
        self.k = k

    def retrieve_all(self, query: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve relevant storylines, acts, and emotions using vector similarity search
        """
        # 쿼리 임베딩 생성
        query_embedding = self.embeddings.embed_query(query)

        # 스토리라인 검색
        storyline_query = """
        CALL db.index.vector.queryNodes($index_name, $k, $embedding)
        YIELD node, score
        MATCH (node)-[:INCLUDES]->(script:StoryScript)
        WITH node, score, script.content as content
        RETURN node.storyline as text, score, 
        COLLECT(content) as scripts, node.id as id
        """
        storyline_docs = self.db_manager.vector_search(
            query_embedding=query_embedding,
            index_name="storyline_embeddings",
            k=self.k,
            retrieval_query=storyline_query,
        )

        # 행동 검색
        act_query = """
        CALL db.index.vector.queryNodes($index_name, $k, $embedding)
        YIELD node, score
        MATCH (script:StoryScript)-[:PERFORMS]->(node)
        WITH node, score, script.content as content
        RETURN node.act as text, score,
        COLLECT(content) as scripts, node.id as id
        """
        act_docs = self.db_manager.vector_search(
            query_embedding=query_embedding,
            index_name="act_embeddings",
            k=self.k,
            retrieval_query=act_query,
        )

        # 감정 검색
        emotion_query = """
        CALL db.index.vector.queryNodes($index_name, $k, $embedding)
        YIELD node, score
        MATCH (script:StoryScript)-[:FEELS]->(node)
        WITH node, score, script.content as content
        RETURN node.emotion as text, score,
        COLLECT(content) as scripts, node.id as id
        """
        emotion_docs = self.db_manager.vector_search(
            query_embedding=query_embedding,
            index_name="emotion_embeddings",
            k=self.k,
            retrieval_query=emotion_query,
        )

        # 결과를 적절한 형식으로 변환
        return {
            "storylines": [
                {
                    "text": doc.page_content,
                    "score": score,
                    "scripts": doc.metadata.get("scripts", []),
                    "unit_id": doc.metadata.get("id"),
                }
                for doc, score in storyline_docs
            ],
            "acts": [
                {
                    "text": doc.page_content,
                    "score": score,
                    "scripts": doc.metadata.get("scripts", []),
                    "act_id": doc.metadata.get("id"),
                }
                for doc, score in act_docs
            ],
            "emotions": [
                {
                    "text": doc.page_content,
                    "score": score,
                    "scripts": doc.metadata.get("scripts", []),
                    "emotion_id": doc.metadata.get("id"),
                }
                for doc, score in emotion_docs
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
