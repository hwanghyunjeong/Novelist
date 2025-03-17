from abc import ABC, abstractmethod
from typing import Dict, Any


class DBInterface(ABC):
    @abstractmethod
    def save_state(self, game_state: Dict[str, Any]) -> None:
        """게임 상태를 저장합니다.

        Args:
            game_state: 저장할 게임 상태 데이터
        """
        pass

    @abstractmethod
    def load_state(self, session_id: str) -> Dict[str, Any]:
        """세션 ID로 게임 상태를 불러옵니다.

        Args:
            session_id: 불러올 게임 상태의 세션 ID

        Returns:
            불러온 게임 상태 데이터
        """
        pass

    @abstractmethod
    def query(self, query: str, params: Dict[str, Any]) -> Any:
        """Neo4j 데이터베이스에 쿼리를 실행합니다.

        Args:
            query: 실행할 Cypher 쿼리 문자열
            params: 쿼리에 사용할 매개변수

        Returns:
            쿼리 실행 결과
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """데이터베이스 연결을 종료합니다."""
        pass
