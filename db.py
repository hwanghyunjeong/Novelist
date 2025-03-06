# db.py
from neo4j import GraphDatabase
import os
from typing import Dict


class DBManager:
    """Neo4j 데이터베이스 연결 및 게임 상태 저장 관리 클래스"""

    def __init__(self):
        """
        DBManager 객체 초기화.
        환경 변수 또는 제공된 인자를 사용하여 Neo4j 데이터베이스에 연결합니다.
        """
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "11111111")
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
        """데이터베이스 연결 종료"""
        if self.driver:
            self.driver.close()
            print("Neo4j 연결이 종료되었습니다.")

    def save_state(self, game_state: dict):
        """
        현재 게임 상태를 Neo4j에 저장합니다.

        Args:
            game_state (dict): 저장할 게임 상태 딕셔너리.
        """
        try:
            with self.driver.session() as session:
                session.execute_write(self._save_game_state_tx, game_state)
            print("Game state saved to DB.")
        except Exception as e:
            print(f"게임 상태 저장 중 오류 발생: {e}")
            raise

    @staticmethod
    def _save_game_state_tx(tx, game_state: dict):
        """
        트랜잭션 내에서 게임 상태를 Neo4j에 저장하거나 업데이트합니다.

        Args:
            tx: Neo4j 트랜잭션 객체.
            game_state (dict): 저장할 게임 상태 딕셔너리.
        """
        try:
            tx.run(
                "MERGE (gs:GameState {id: $game_state_id}) " "SET gs = $game_state",
                game_state_id=game_state.get("session_id"),
                game_state=game_state,
            )
        except Exception as e:
            print(f"게임 상태 트랜잭션 중 오류 발생: {e}")
            raise

    def save_scene(self, scene_data: dict):
        """씬 데이터를 Neo4j에 저장합니다."""
        try:
            with self.driver.session() as session:
                session.execute_write(self._save_scene_tx, scene_data)
            print("Scene 데이터가 DB에 저장되었습니다.")
        except Exception as e:
            print(f"씬 데이터 저장 중 오류 발생: {e}")
            raise

    @staticmethod
    def _save_scene_tx(tx, scene_data: dict):
        """트랜잭션 내에서 씬 데이터를 저장합니다."""
        try:
            tx.run(
                """
                MERGE (s:Scene {id: $scene_id})
                SET s.label = $label,
                    s.map = $map,
                    s.scene = $scene_name,
                    s.genre = $genre,
                    s.theme = $theme,
                    s.concept = $concept,
                    s.motif = $motif,
                    s.main_character = $main_character,
                    s.conflict = $conflict,
                    s.characters = $characters
                """,
                scene_id=scene_data.get("id"),
                label=scene_data.get("label", "Scene"),
                map=scene_data.get("map"),
                scene_name=scene_data.get("scene"),
                genre=scene_data.get("genre", []),
                theme=scene_data.get("theme", []),
                concept=scene_data.get("concept"),
                motif=scene_data.get("motif"),
                main_character=scene_data.get("main_character"),
                conflict=scene_data.get("conflict"),
                characters=scene_data.get("characters", []),
            )
            for char_ref in scene_data.get("characters", []):
                char_id = char_ref
                tx.run(
                    """
                    MERGE (c:Character {id: $char_id})
                    MERGE (s:Scene {id: $scene_id})
                    MERGE (s)-[:INVOLVES]->(c)
                    """,
                    char_id=char_id,
                    scene_id=scene_data.get("id"),
                )
        except Exception as e:
            print(f"씬 데이터 트랜잭션 중 오류 발생: {e}")
            raise
