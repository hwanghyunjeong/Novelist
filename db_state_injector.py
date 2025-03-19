from typing import Dict, Any
from db_interface import DBInterface
from db_manager import LangchainNeo4jDBManager
from db_base import LegacyDBManager
import json


class DBStateInjector:
    """상태 객체에 데이터베이스 클라이언트를 주입하는 클래스"""

    def __init__(self, db_manager: DBInterface):
        """DBStateInjector 초기화

        Args:
            db_manager: 데이터베이스 관리자 객체
        """
        if not isinstance(db_manager, DBInterface):
            raise ValueError("db_manager must implement DBInterface")
        self.db_manager = db_manager

    def inject(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """상태를 주입하고 초기화합니다."""
        if not state.get("initialized"):
            # 초기 씬 데이터 로드
            query = "MATCH (s:Scene) WHERE s.id = 'scene:00_Pangyo_Station' RETURN s"
            initial_scene = self.db_manager.query(query=query, params={})

            if initial_scene:
                scene_data = initial_scene[0]["s"]
                # JSON 문자열로 저장된 속성 파싱
                parsed_scene = self._parse_node_data(scene_data)

                state.update(
                    {
                        "current_scene": parsed_scene,
                        "initialized": True,
                        "context": parsed_scene.get("context", ""),
                        "available_actions": parsed_scene.get("available_actions", []),
                    }
                )

        return state

    def _parse_node_data(self, node_data: Dict[str, Any]) -> Dict[str, Any]:
        """Neo4j 노드 데이터를 파싱합니다."""
        parsed_data = {}
        for key, value in node_data.items():
            if isinstance(value, str) and (
                value.startswith("{") or value.startswith("[")
            ):
                try:
                    parsed_data[key] = json.loads(value)
                except json.JSONDecodeError:
                    parsed_data[key] = value
            else:
                parsed_data[key] = value
        return parsed_data
