from neo4j import GraphDatabase
import json
from typing import Dict, Any
from db_interface import DBInterface
from states import player_state_to_dict


class LegacyDBManager(DBInterface):
    def __init__(self, uri: str, user: str, password: str):
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

    def save_state(self, game_state: Dict[str, Any]) -> None:
        try:
            self.driver.session().execute_write(self._save_game_state_tx, game_state)
            print("Game state saved to DB.")
        except Exception as e:
            print(f"게임 상태 저장 중 오류 발생: {e}")
            raise

    @staticmethod
    def _save_game_state_tx(tx, game_state: Dict[str, Any]) -> None:
        sanitized_state = {}
        for k, v in game_state.items():
            if k == "db_client":
                continue
            if isinstance(v, (dict, list)):
                sanitized_state[k] = json.dumps(v, ensure_ascii=False)
            else:
                sanitized_state[k] = v
        session_id = sanitized_state.get("session_id")
        if not session_id:
            raise ValueError("session_id가 올바르게 설정되지 않았습니다.")
        query = "MERGE (gs:GameState {id: $game_state_id}) SET gs += $game_state"
        tx.run(query, game_state_id=session_id, game_state=sanitized_state)

    def load_state(self, session_id: str) -> Dict[str, Any]:
        query = "MATCH (gs:GameState {id: $session_id}) RETURN gs"
        result = self.driver.session().execute_read(
            self._load_game_state_tx, query, {"session_id": session_id}
        )
        return result if result else {}

    @staticmethod
    def _load_game_state_tx(tx, query: str, params: Dict[str, Any]) -> Dict[str, Any]:
        result = tx.run(query, **params)
        record = result.single()
        if record:
            game_state = dict(record["gs"])
            for k, v in game_state.items():
                if isinstance(v, str):
                    try:
                        game_state[k] = json.loads(v)
                    except json.JSONDecodeError:
                        pass
            return game_state
        return {}

    def query(self, query: str, params: Dict[str, Any] = None) -> Any:
        if params is None:
            params = {}
        with self.driver.session() as session:
            return session.run(query, params)

    def close(self) -> None:
        if self.driver:
            self.driver.close()
            print("Neo4j 연결이 종료되었습니다.")


class DBStateInjector:
    """dbclient 의존성 주입 클래스"""

    def __init__(self, db_manager: DBInterface):
        self.db_manager = db_manager

    def inject(self, state: dict) -> dict:
        """
        현재 세션의 DBManager에서 driver나 neo4j_graph를 추출하여
        state에 'db_client' 키로 주입합니다.
        """
        # 타입에 따라 다른 객체 주입
        if hasattr(self.db_manager, "neo4j_graph"):
            state["db_client"] = self.db_manager.neo4j_graph
        else:
            state["db_client"] = self.db_manager.driver
        return state

    def invoke_workflow(self, state: dict, workflow_app) -> dict:
        """
        상태에 db_client를 주입한 후, 주어진 workflow_app (예: app)를 실행합니다.
        """
        updated_state = self.inject(state)
        return workflow_app.invoke(player_state_to_dict(updated_state))
