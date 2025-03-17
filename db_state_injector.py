from typing import Dict, Any
from db_interface import DBInterface
from db_manager import LangchainNeo4jDBManager
from db_base import LegacyDBManager


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
        """상태 객체에 데이터베이스 클라이언트 주입

        Args:
            state: 상태 객체

        Returns:
            데이터베이스 클라이언트가 주입된 상태 객체
        """
        if isinstance(self.db_manager, LangchainNeo4jDBManager):
            state["db_client"] = self.db_manager.neo4j_graph
        elif isinstance(self.db_manager, LegacyDBManager):
            state["db_client"] = self.db_manager.driver
        else:
            raise ValueError("Unsupported DBManager type")
        return state
