from neo4j import GraphDatabase
from states import player_state_to_dict
from typing import Dict, Any, List, Optional
import config
import json
from db_interface import DBInterface
from db_state_injector import DBStateInjector
from db_legacy import LegacyDBManager
from db_manager import LangchainNeo4jDBManager
from langchain_neo4j import GraphCypherQAChain
from langchain_openai import ChatOpenAI
from db_factory import get_db_manager


# 단계적 테스트 구현 (마이그레이션 단계별 테스트코드)
def test_neo4j_graph_connection():
    db_manager = LegacyDBManager(TEST_URI, TEST_USER, TEST_PASSWORD)
    result = db_manager.query("RETURN 1 as test", {})
    assert result[0]["test"] == 1


def test_save_and_load_state():
    db_manager = LegacyDBManager(TEST_URI, TEST_USER, TEST_PASSWORD)
    test_state = {"id": "test_session", "player_name": "테스트플레이어"}
    db_manager.save_state(test_state)
    loaded_state = db_manager.load_state("test_session")
    assert loaded_state["player_name"] == "테스트플레이어"


# 스키마 정보 활용
schema = db_manager.neo4j_graph.get_schema
print(f"데이터베이스 스키마: {schema}")

# LLM 기반 Cypher 자동 생성 (필요한 경우)
llm = ChatOpenAI()
qa_chain = GraphCypherQAChain.from_llm(
    llm=llm, graph=db_manager.neo4j_graph, verbose=True
)

# 기존 코드에서 필요한 것들만 export
__all__ = [
    "LegacyDBManager",
    "LangchainNeo4jDBManager",
    "DBStateInjector",
    "get_db_manager",
]
