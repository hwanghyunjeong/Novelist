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
        """모든 벡터 인덱스에서 유사한 문서를 검색합니다."""
        # 쿼리 임베딩 생성
        query_embedding = self.embeddings.embed_query(query)

        # 스토리라인 검색
        storyline_query = """
        CALL db.index.vector.queryNodes($index_name, $k, $embedding)
        YIELD node, score
        WITH node as unit, score
        MATCH (unit)-[:INCLUDES]->(script:StoryScript)
        WITH unit, score, COLLECT(script.content) as contents
        RETURN unit.storyline as storyline, score, 
        contents as scripts, unit.id as id
        """
        storylines = self.db_manager.query(
            query=storyline_query,
            params={
                "index_name": "storylineVector",
                "k": self.k,
                "embedding": query_embedding,
            },
        )

        # 행동 검색
        act_query = """
        CALL db.index.vector.queryNodes($index_name, $k, $embedding)
        YIELD node, score
        WITH node as act, score
        MATCH (script:StoryScript)-[:PERFORMS]->(act)
        WITH act, score, COLLECT(script.content) as contents
        RETURN act.act as act, score,
        contents as scripts, act.id as id
        """
        acts = self.db_manager.query(
            query=act_query,
            params={
                "index_name": "actVector",
                "k": self.k,
                "embedding": query_embedding,
            },
        )

        # 감정 검색
        emotion_query = """
        CALL db.index.vector.queryNodes($index_name, $k, $embedding)
        YIELD node, score
        WITH node as emotion, score
        MATCH (script:StoryScript)-[:FEELS]->(emotion)
        WITH emotion, score, COLLECT(script.content) as contents
        RETURN emotion.emotion as emotion, score,
        contents as scripts, emotion.id as id
        """
        emotions = self.db_manager.query(
            query=emotion_query,
            params={
                "index_name": "emotionVector",
                "k": self.k,
                "embedding": query_embedding,
            },
        )

        # 결과를 적절한 형식으로 변환
        return {
            "storylines": [
                {
                    "text": result["storyline"],
                    "score": result["score"],
                    "scripts": result["scripts"],
                    "unit_id": result["id"],
                }
                for result in storylines
            ],
            "acts": [
                {
                    "text": result["act"],
                    "score": result["score"],
                    "scripts": result["scripts"],
                    "act_id": result["id"],
                }
                for result in acts
            ],
            "emotions": [
                {
                    "text": result["emotion"],
                    "score": result["score"],
                    "scripts": result["scripts"],
                    "emotion_id": result["id"],
                }
                for result in emotions
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
