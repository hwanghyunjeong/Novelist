"""Story retriever implementation."""

from typing import Dict, List, Optional, Any
from langchain_openai import OpenAIEmbeddings


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
        """스토리라인, 행동, 감정에 대한 벡터 검색을 수행합니다."""
        # 쿼리 임베딩 생성
        query_embedding = self.embeddings.embed_query(query)

        # 결과 컨테이너 초기화
        results = {"storylines": [], "acts": [], "emotions": []}

        try:
            # 스토리라인 검색
            storyline_query = """
            CALL db.index.vector.queryNodes($index_name, $k, $embedding) 
            YIELD node, score
            WITH node, score
            OPTIONAL MATCH (node)-[:INCLUDES]->(script:StoryScript)
            WITH node, score, collect(script.content) as scripts
            RETURN node.storyline as text, score, node.id as id, scripts
            """

            storyline_results = self.db_manager.query(
                query=storyline_query,
                params={
                    "index_name": "storyline_embeddings",
                    "k": self.k,
                    "embedding": query_embedding,
                },
            )

            for result in storyline_results:
                results["storylines"].append(
                    {
                        "text": result.get("text", ""),
                        "score": result.get("score", 0.0),
                        "scripts": result.get("scripts", []),
                        "unit_id": result.get("id", ""),
                    }
                )

            # 행동 검색
            act_query = """
            CALL db.index.vector.queryNodes($index_name, $k, $embedding) 
            YIELD node, score
            WITH node, score
            OPTIONAL MATCH (script:StoryScript)-[:PERFORMS]->(node)
            WITH node, score, collect(script.content) as scripts
            RETURN node.act as text, score, node.id as id, scripts
            """

            act_results = self.db_manager.query(
                query=act_query,
                params={
                    "index_name": "act_embeddings",
                    "k": self.k,
                    "embedding": query_embedding,
                },
            )

            for result in act_results:
                results["acts"].append(
                    {
                        "text": result.get("text", ""),
                        "score": result.get("score", 0.0),
                        "scripts": result.get("scripts", []),
                        "act_id": result.get("id", ""),
                    }
                )

            # 감정 검색
            emotion_query = """
            CALL db.index.vector.queryNodes($index_name, $k, $embedding) 
            YIELD node, score
            WITH node, score
            OPTIONAL MATCH (script:StoryScript)-[:FEELS]->(node)
            WITH node, score, collect(script.content) as scripts
            RETURN node.emotion as text, score, node.id as id, scripts
            """

            emotion_results = self.db_manager.query(
                query=emotion_query,
                params={
                    "index_name": "emotion_embeddings",
                    "k": self.k,
                    "embedding": query_embedding,
                },
            )

            for result in emotion_results:
                results["emotions"].append(
                    {
                        "text": result.get("text", ""),
                        "score": result.get("score", 0.0),
                        "scripts": result.get("scripts", []),
                        "emotion_id": result.get("id", ""),
                    }
                )

        except Exception as e:
            print(f"벡터 검색 중 오류 발생: {e}")

        return results

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
