import pytest
import os
from dotenv import load_dotenv
from db_factory import get_db_manager
from db_interface import DBInterface

# 테스트 시작 전에 환경변수 로드
load_dotenv()


@pytest.fixture(scope="session")
def db_manager():
    """테스트용 데이터베이스 매니저를 생성하는 fixture"""
    manager = get_db_manager(
        manager_type="langchain",
        uri=os.getenv("NEO4J_URI"),
        user=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD"),
        database=os.getenv("NEO4J_DATABASE"),
    )
    yield manager
    # 테스트 후 정리
    cleanup_query = """
    MATCH (n:TestNode)
    DELETE n
    """
    manager.query(cleanup_query, {})


def test_neo4j_graph_connection(db_manager):
    """Neo4jGraph 연결 테스트

    데이터베이스 연결이 정상적으로 수립되는지 확인합니다.
    """
    result = db_manager.query(query="RETURN 1 as test", params={})
    assert result[0]["test"] == 1


def test_save_and_load_state(db_manager):
    """상태 저장 및 로드 테스트

    게임 상태가 정상적으로 저장되고 로드되는지 확인합니다.
    """
    test_state = {
        "id": "test_session",
        "player_name": "테스트플레이어",
        "complex_data": {"key": "value"},
        "list_data": [1, 2, 3],
    }

    # 상태 저장
    db_manager.save_state(test_state)

    # 상태 로드
    loaded_state = db_manager.load_state("test_session")

    # 검증
    assert loaded_state["player_name"] == "테스트플레이어"
    assert loaded_state["complex_data"]["key"] == "value"
    assert loaded_state["list_data"] == [1, 2, 3]


def test_query_execution(db_manager):
    """쿼리 실행 테스트

    Cypher 쿼리가 정상적으로 실행되는지 확인합니다.
    """
    # 노드 생성
    create_query = """
    CREATE (n:TestNode {name: $name})
    RETURN n
    """
    result = db_manager.query(query=create_query, params={"name": "test"})
    assert result[0]["n"]["name"] == "test"

    # 노드 조회
    read_query = """
    MATCH (n:TestNode {name: $name})
    RETURN n
    """
    result = db_manager.query(query=read_query, params={"name": "test"})
    assert result[0]["n"]["name"] == "test"

    # 테스트 데이터 정리
    cleanup_query = """
    MATCH (n:TestNode {name: $name})
    DELETE n
    """
    db_manager.query(query=cleanup_query, params={"name": "test"})
