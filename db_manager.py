from langchain_neo4j import Neo4jGraph
from typing import Dict, Any, List, Optional, Tuple
from db_interface import DBInterface
from langchain_core.documents import Document
import json


class LangchainNeo4jDBManager(DBInterface):
    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
        refresh_schema: bool = True,
    ):
        """Langchain Neo4j 데이터베이스 관리자 초기화

        Args:
            uri: Neo4j 데이터베이스 URI
            user: Neo4j 사용자 이름
            password: Neo4j 비밀번호
            database: 사용할 데이터베이스 이름
            refresh_schema: 스키마 자동 갱신 여부
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.neo4j_graph = Neo4jGraph(
            url=uri,
            username=user,
            password=password,
            database=database,
            refresh_schema=refresh_schema,
        )

    def _sanitize_state(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """게임 상태를 저장 가능한 형태로 변환"""
        sanitized_state = {}
        for k, v in game_state.items():
            if k == "db_client":
                continue
            if isinstance(v, (dict, list)):
                sanitized_state[k] = json.dumps(v, ensure_ascii=False)
            else:
                sanitized_state[k] = v
        return sanitized_state

    def save_state(self, game_state: Dict[str, Any]) -> None:
        """게임 상태를 데이터베이스에 저장

        Args:
            game_state: 저장할 게임 상태 데이터
        """
        sanitized_state = self._sanitize_state(game_state)
        query = """
        MERGE (gs:GameState {id: $game_state_id})
        SET gs += $game_state
        """
        self.neo4j_graph.query(
            query, {"game_state_id": game_state["id"], "game_state": sanitized_state}
        )

    def load_state(self, session_id: str) -> Dict[str, Any]:
        """주어진 세션 ID에 해당하는 게임 상태 불러오기

        Args:
            session_id: 게임 세션 ID

        Returns:
            불러온 게임 상태 데이터
        """
        query = """
        MATCH (gs:GameState {id: $session_id})
        RETURN gs
        """
        result = self.neo4j_graph.query(query, {"session_id": session_id})

        if not result:
            return {}

        game_state = dict(result[0]["gs"])
        # JSON 역직렬화
        for k, v in game_state.items():
            if isinstance(v, str):
                try:
                    game_state[k] = json.loads(v)
                except json.JSONDecodeError:
                    pass
        return game_state

    def query(self, query: str, params: Dict[str, Any]) -> Any:
        """Cypher 쿼리 실행

        Args:
            query: 실행할 Cypher 쿼리 문자열
            params: 쿼리에 사용할 파라미터

        Returns:
            쿼리 실행 결과
        """
        return self.neo4j_graph.query(query, params)

    def close(self) -> None:
        """데이터베이스 연결 종료

        Neo4jGraph에서는 명시적인 close 메서드가 없지만,
        인터페이스 일관성을 위해 구현합니다.
        """
        # Neo4jGraph에는 명시적인 close 메서드가 없음
        pass

    def get_schema(self) -> str:
        """데이터베이스 스키마 정보 반환

        Returns:
            데이터베이스 스키마 정보
        """
        return self.neo4j_graph.get_schema

    def vector_search(
        self,
        query_embedding: List[float],
        index_name: str,
        k: int = 6,
        retrieval_query: Optional[str] = None,
    ) -> List[Tuple[Document, float]]:
        """벡터 검색을 수행합니다.

        Args:
            query_embedding: 쿼리 임베딩
            index_name: 검색할 벡터 인덱스 이름
            k: 반환할 결과 수
            retrieval_query: 추가적인 검색 쿼리 (선택사항)

        Returns:
            Document 객체와 유사도 점수의 튜플 리스트
        """
        if not retrieval_query:
            # 기본 검색 쿼리
            retrieval_query = """
            CALL db.index.vector.queryNodes($index_name, $k, $embedding)
            YIELD node, score
            RETURN node, score
            """

        results = self.neo4j_graph.query(
            retrieval_query,
            {
                "index_name": index_name,
                "k": k,
                "embedding": query_embedding,
            },
        )

        docs_with_scores = []
        for result in results:
            # node의 모든 속성을 metadata로 사용
            node_data = dict(result["node"])

            # text 필드 결정 (storyline, act, emotion 중 하나)
            text = (
                node_data.get("storyline")
                or node_data.get("act")
                or node_data.get("emotion", "")
            )

            doc = Document(page_content=text, metadata=node_data)
            docs_with_scores.append((doc, result["score"]))

        return docs_with_scores

    def get_vector_index_info(self, index_name: str) -> Dict[str, Any]:
        """벡터 인덱스 정보를 조회합니다.

        Args:
            index_name: 조회할 인덱스 이름

        Returns:
            인덱스 정보를 담은 딕셔너리
        """
        query = """
        SHOW INDEX INFO FOR $index_name
        """
        results = self.neo4j_graph.query(query, {"index_name": index_name})
        return results[0] if results else None
