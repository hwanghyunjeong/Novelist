from neo4j import GraphDatabase
from states import player_state_to_dict
from typing import Dict
import config
import json


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
        sanitized_state = {}
        for k, v in game_state.items():
            if k == "db_client":
                continue
            # dict나 list는 JSON 문자열로 변환
            if isinstance(v, (dict, list)):
                sanitized_state[k] = json.dumps(
                    v, ensure_ascii=False
                )  # ensure_ascii : 한글 등 유니코드 문자 저장을 위해 False
            else:
                sanitized_state[k] = v
        session_id = sanitized_state.get("session_id")
        if not session_id:
            raise ValueError("session_id가 올바르게 설정되지 않았습니다.")
        query = "MERGE (gs:GameState {id: $game_state_id}) SET gs += $game_state"
        tx.run(query, game_state_id=session_id, game_state=sanitized_state)

    def load_state(self, session_id: str) -> Dict:
        """주어진 세션 ID에 해당하는 게임 상태를 로드합니다."""
        with self.driver.session() as session:
            result = session.execute_read(self._load_game_state_tx, session_id)
            return result

    @staticmethod
    def _load_game_state_tx(tx, session_id: str) -> Dict:
        query = "MATCH (gs:GameState {id: $session_id}) RETURN gs"
        result = tx.run(query, session_id=session_id)
        record = result.single()
        if record:
            game_state = record["gs"]
            for k, v in game_state.items():
                # JSON 문자열로 저장된 데이터는 다시 복원
                if isinstance(v, str):
                    try:
                        game_state[k] = json.loads(v)
                    except json.JSONDecodeError:
                        pass
            return game_state
        return {}  # session_id로 저장된 게임 상태가 없을 경우 빈 딕셔너리를 반환


class DBStateInjector:
    """dbclient 의존성 주입 클래스"""

    def __init__(self, db_manager):
        self.db_manager = db_manager

    def inject(self, state: dict) -> dict:
        """
        현재 세션의 DBManager에서 driver를 추출하여
        state에 'db_client' 키로 주입합니다.
        """
        state["db_client"] = self.db_manager.driver
        return state

    def invoke_workflow(self, state: dict, workflow_app) -> dict:
        """
        상태에 db_client를 주입한 후, 주어진 workflow_app (예: app)를 실행합니다.
        """
        updated_state = self.inject(state)
        return workflow_app.invoke(player_state_to_dict(updated_state))
