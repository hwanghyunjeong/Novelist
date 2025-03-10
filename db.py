from neo4j import GraphDatabase
from typing import Dict
import config


class DBManager:
    """Neo4j 데이터베이스 연결 및 게임 상태 저장 관리 클래스"""

    def __init__(self, uri, user, password):
        self.uri = uri
        self.user = user
        self.password = password
        if not all([self.uri, self.user, self.password]):
            raise ValueError("Neo4j URI, user, and password must be provided.")
        try:
            self.driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
            self.driver.verify_connectivity()
            print("Neo4j와 연결되었습니다.")
        except Exception as e:
            print(f"Neo4j 연결 실패: {e}")
            raise

    def close(self):
        if self.driver:
            self.driver.close()
            print("Neo4j 연결이 종료되었습니다.")

    def save_state(self, game_state: Dict):
        """게임 상태를 Neo4j에 저장합니다."""
        try:
            with self.driver.session() as session:
                session.execute_write(self._save_game_state_tx, game_state)
            print("Game state saved to DB.")
        except Exception as e:
            print(f"게임 상태 저장 중 오류 발생: {e}")
            raise

    @staticmethod
    def _save_game_state_tx(tx, game_state: Dict):
        sanitized_state = {k: v for k, v in game_state.items() if k != "db_client"}
        session_id = sanitized_state.get("session_id")
        if not session_id:
            raise ValueError("session_id가 올바르게 설정되지 않았습니다.")
        query = "MERGE (gs:GameState {id: $game_state_id}) SET gs += $game_state"
        tx.run(query, game_state_id=session_id, game_state=sanitized_state)
