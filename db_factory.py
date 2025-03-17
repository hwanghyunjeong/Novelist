import os
from typing import Dict, Any
import config
from db_interface import DBInterface
from db_base import LegacyDBManager
from db_manager import LangchainNeo4jDBManager


def get_db_manager(manager_type: str = "langchain", **kwargs) -> DBInterface:
    """데이터베이스 매니저 인스턴스를 생성합니다.

    Args:
        manager_type: 사용할 매니저 타입 ("langchain" 또는 "legacy")
        **kwargs: 데이터베이스 연결 설정

    Returns:
        DBInterface를 구현한 데이터베이스 매니저 인스턴스
    """
    # 환경변수에서 설정 가져오기
    uri = kwargs.get("uri") or config.NEO4J_URI
    user = kwargs.get("user") or config.NEO4J_USER
    password = kwargs.get("password") or config.NEO4J_PASSWORD
    database = kwargs.get("database") or config.NEO4J_DATABASE

    print(f"Connecting to Neo4j database at {uri} with user {user}")  # 디버깅용

    try:
        if manager_type == "langchain":
            refresh_schema = kwargs.get("refresh_schema", True)
            return LangchainNeo4jDBManager(
                uri=uri,
                user=user,
                password=password,
                database=database,
                refresh_schema=refresh_schema,
            )
        elif manager_type == "legacy":
            return LegacyDBManager(uri=uri, user=user, password=password)
        else:
            raise ValueError(f"Unsupported manager type: {manager_type}")
    except Exception as e:
        print(f"Failed to create DB manager: {str(e)}")  # 디버깅용
        raise
