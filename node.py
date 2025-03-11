# node.py
from abc import ABC, abstractmethod
from states import PlayerState
from character import Character
from neo4j import GraphDatabase


class BaseNode(ABC):
    def __init__(self, **kwargs):
        self.name = kwargs.get("name", "BaseNode")
        self.verbose = kwargs.get("verbose", False)

    @abstractmethod
    def execute(self, state: PlayerState) -> PlayerState:
        pass


class InitializeNode(BaseNode):
    def execute(self, state: PlayerState) -> PlayerState:
        # 초기 상태를 설정 (예: 캐릭터, 맵 데이터 로드)
        if not state["player"]["name"]:
            state["player"]["name"] = "Unknown"
        return state


class AnalysisDirectionNode(BaseNode):
    def execute(self, state: PlayerState) -> PlayerState:
        # 사용자 입력을 분석하여 이동 방향 결정 (기본 예시)
        # 실제로는 LangChain 체인을 호출할 수 있음.
        direction = state.get("user_input", "not move")
        state["player"]["direction"] = direction
        return state


class MovePlayerNode(BaseNode):
    def execute(self, state: PlayerState) -> PlayerState:
        # 간단한 좌표 업데이트 (예: '왼쪽', '오른쪽' 등)
        mapping = {"왼쪽": (-1, 0), "오른쪽": (1, 0), "위": (0, -1), "아래": (0, 1)}
        direction = state["player"].get("direction", "not move")
        if direction in mapping:
            dx, dy = mapping[direction]
            pos = state["player"]["position"]
            pos["x"] += dx
            pos["y"] += dy
        return state


class AnalyseMapNode(BaseNode):
    def __init__(self, map_analyst, **kwargs):
        super().__init__(**kwargs)
        self.map_analyst = map_analyst

    def execute(self, state: PlayerState) -> PlayerState:
        # LangChain 지도 분석 체인을 호출하여 분석 결과를 저장
        analysis = self.map_analyst.invoke(
            {
                "current_map": state["map"],
                "player_position": state["player"]["position"],
                "history": state["history"],
            }
        )
        state["map_context"] = analysis
        return state


class MakeStoryNode(BaseNode):
    def __init__(self, story_chain, **kwargs):
        super().__init__(**kwargs)
        self.story_chain = story_chain

    def execute(self, state: PlayerState) -> PlayerState:
        # LangChain 이야기 생성 체인을 호출하여 이야기를 생성
        story = self.story_chain.invoke(
            {
                "map_context": state["map_context"],
                "history": state["history"],
                "name": state["player"].get("name", "모험가"),
            }
        )
        state["generation"] = story
        return state


class RouteMovingNode(BaseNode):
    def execute(self, state: PlayerState) -> str:
        # 이동 방향이 정상적으로 주어졌다면 'move_player'로, 그렇지 않으면 'not move'
        direction = state["player"].get("direction")
        if direction in ["왼쪽", "오른쪽", "위", "아래"]:
            return "move_player"
        return "map_analyst"  # modified : go to map_analyst if player not move.


class CreatePlayerAndCharacterNodes(BaseNode):
    def execute(self, state: PlayerState) -> PlayerState:
        driver = state.get("db_client")
        player_data = state.get("player")
        characters = state.get("characters", [])
        with driver.session() as session:
            session.write_transaction(self._create_player_node, player_data)
            for char in characters:
                session.write_transaction(self._create_character_node, char)
                # 처음엔 관계를 'FRIEND'로 설정 (추후 업데이트 가능)
                session.write_transaction(
                    self._create_relationship,
                    player_data["id"],
                    char["id"],
                    "FRIEND",
                    {"status": "initial"},
                )
        return state

    def _create_player_node(self, tx, player_data: dict):
        tx.run(
            """
            MERGE (p:Player {id: $id})
            SET p.name = $name, p.sex = $sex, p.stamina = $stamina, p.status = $status,
            """,
            id=player_data.get("id"),
            name=player_data.get("name"),
            sex=player_data.get("sex"),
            stamina=player_data.get("stamina"),
            status=player_data.get("status"),
        )

    def _create_character_node(self, tx, char_data: dict):
        tx.run(
            """
            MERGE (c:Character {id: $id})
            SET c.name = $name, c.type = $type
            """,
            id=char_data.get("id"),
            name=char_data.get("name"),
            type=char_data.get("type", "character"),
        )

    def _create_relationship(
        self, tx, player_id: str, char_id: str, rel_type: str, properties: dict
    ):
        query = f"""
        MATCH (p:Player {{id: $player_id}}), (c:Character {{id: $char_id}})
        MERGE (p)-[r:{rel_type}]->(c)
        SET r += $props
        """
        tx.run(query, player_id=player_id, char_id=char_id, props=properties)
