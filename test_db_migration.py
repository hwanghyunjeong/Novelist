import pytest
from db_interface import DBInterface
from langchain_db import LangchainNeo4jDBManager
import config
import json
from typing import Dict


@pytest.fixture
def db_manager():
    """테스트용 데이터베이스 매니저 픽스처"""
    return LangchainNeo4jDBManager(
        uri=config.NEO4J_URI,
        user=config.NEO4J_USER,
        password=config.NEO4J_PASSWORD,
        database=config.NEO4J_DATABASE,
    )


def test_connection(db_manager):
    """연결 테스트"""
    result = db_manager.query(query="RETURN 1 AS test", params={})
    assert result[0]["test"] == 1


def test_save_and_load_state(db_manager):
    """상태 저장 및 불러오기 테스트"""
    test_state = {
        "id": "test_session_id",
        "player_name": "테스트플레이어",
        "current_scene": "scene_001",
    }

    # 상태 저장
    db_manager.save_state(test_state)

    # 상태 불러오기
    loaded_state = db_manager.load_state("test_session_id")

    # 검증
    assert loaded_state["player_name"] == "테스트플레이어"
    assert loaded_state["current_scene"] == "scene_001"


def _sanitize_state(game_state: Dict) -> Dict:
    sanitized_state = {}
    for k, v in game_state.items():
        if k == "db_client":
            continue
        if isinstance(v, (dict, list)):
            sanitized_state[k] = json.dumps(v, ensure_ascii=False)
        else:
            sanitized_state[k] = v
    return sanitized_state


def test_json_serialization():
    """JSON 직렬화/역직렬화 테스트"""
    test_state = {
        "id": "test_session",
        "complex_data": {"key": "value"},
        "list_data": [1, 2, 3],
    }
    # 테스트 로직...
    # 상태 직렬화
    sanitized_state = _sanitize_state(test_state)

    # 직렬화된 데이터 검증
    assert isinstance(sanitized_state["complex_data"], str)
    assert isinstance(sanitized_state["list_data"], str)

    # JSON 문자열이 올바르게 파싱되는지 확인
    parsed_complex = json.loads(sanitized_state["complex_data"])
    parsed_list = json.loads(sanitized_state["list_data"])

    # 원본 데이터와 비교
    assert parsed_complex == test_state["complex_data"]
    assert parsed_list == test_state["list_data"]

    # ID는 직렬화되지 않고 그대로 유지되는지 확인
    assert sanitized_state["id"] == test_state["id"]
    assert isinstance(sanitized_state["id"], str)
