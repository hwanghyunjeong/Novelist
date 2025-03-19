# state_graph.py
from typing import TypedDict, List, Dict, Any
from langgraph.graph import START, StateGraph, END
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from states import GameState, PlayerState
from node import (
    InitializeNode,
    AnalysisDirectionNode,
    MovePlayerNode,
    AnalyseMapNode,
    MakeStoryNode,
    RouteMovingNode,
    CreatePlayerAndCharacterNodes,
)
import streamlit as st


class GameState(TypedDict):
    scene: str
    scene_beat: str
    user_input: str
    available_actions: List[str]
    matched_action: str | None
    action_result: str | None
    map: str
    map_context: str
    generation: str
    characters: List[Dict]
    history: List[str]


# 동기 버전의 모델 초기화
action_matcher_model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
story_generator_model = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)


def process_user_action(state: GameState) -> GameState:
    """사용자 입력을 처리하고 씬 전환을 수행하는 통합 노드"""
    user_input = state["user_input"]
    available_actions = state["available_actions"]
    current_scene_beat_id = state["scene_beat"]
    db_manager = st.session_state.db_manager

    # 1. Action Matching
    response = action_matcher_model.invoke(
        [
            {
                "role": "user",
                "content": f"""
        사용자 입력: {user_input}
        가능한 행동들: {', '.join(available_actions)}
        
        위 사용자 입력이 가능한 행동들 중 어떤 것과 가장 잘 매칭되는지 판단하세요.
        정확히 일치하지 않더라도, 의미상 가장 가까운 행동을 선택하세요.
        매칭되는 행동이 있다면 그 행동을, 없다면 None을 반환하세요.
        """,
            }
        ]
    )

    matched_action = response.content
    state["matched_action"] = matched_action if matched_action != "None" else None
    state["action_result"] = "continue" if matched_action != "None" else "invalid_input"

    # 2. Scene Transition (매칭된 액션이 있을 경우에만)
    if state["matched_action"]:
        try:
            next_scene_beat = get_next_scene_beat(
                db_manager=db_manager,
                current_scene_beat_id=current_scene_beat_id,
                choice=matched_action,  # matched_action을 choice로 전달
            )

            if next_scene_beat:
                state["scene_beat"] = next_scene_beat

                if next_scene_beat.startswith("scene:"):
                    state["scene"] = next_scene_beat

                    # Update map
                    query = """
                    MATCH (s:Scene {id: $scene_id})-[:LOCATED_IN]->(m:Map)
                    RETURN m.id as map_id
                    """
                    result = db_manager.query(
                        query=query, params={"scene_id": next_scene_beat}
                    )

                    if result:
                        state["map"] = result[0]["map_id"]

        except Exception as e:
            print(f"Error in scene transition: {e}")
            # 에러가 발생해도 매칭 결과는 유지

    return state


def generate_story(state: GameState, system_prompt: str) -> Dict:
    """Story generation"""
    # 내부 처리용 history와 표시용 display_history 분리
    history = state.get("history", [])

    # Combine previous stories into a single context string (최근 3개만 사용)
    previous_stories = "\n".join(history[-3:]) if history else ""

    # 현재 상황 컨텍스트
    current_context = state.get("context", "")

    response = story_generator_model.invoke(
        [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""
        이전 이야기: {previous_stories}
        현재 상황: {current_context if current_context else state.get('generation', '')}
        현재 씬: {state['scene']}
        맵 분석: {state['map_context']}
        플레이어 행동: {state['user_input']}
        선택된 행동: {state['matched_action']}
        등장 인물: {state['characters']}
        
        Based on the information above, generate a story that maintains the flow of the previous narrative while fitting the current situation.
        Exclude system messages or technical explanations and write pure narrative only.
        Write only the new part of the story that continues from the previous narrative. 
        Do not repeat or summarize any part of the previous story. 
        Exclude any system messages or technical explanations.
        """,
            },
        ]
    )

    new_story = response.content

    # history에는 내부 처리용으로 모든 이야기를 보관
    processed_history = history.copy()
    processed_history.append(new_story)

    # 히스토리 크기 제한 (선택적)
    if len(processed_history) > 10:
        processed_history = processed_history[-10:]

    # 표시용 history는 새로운 이야기만 포함
    display_history = state.get("display_history", [])
    display_history.append(new_story)

    return {
        "generation": new_story,  # 최신 생성된 내용
        "history": processed_history,  # LLM 컨텍스트용 전체 히스토리
        "display_history": display_history,  # 화면 표시용 히스토리
    }


def should_continue(state: GameState) -> str:
    """다음 노드 결정"""
    if state.get("action_result") == "continue":
        return "story_generation"
    return "end"


def create_game_graph():
    """게임 그래프 생성"""
    workflow = StateGraph(GameState)

    def story_generation_with_dynamic_prompt(state: GameState) -> Dict:
        # 각 상태값에 대해 더 의미 있는 기본값 설정
        available_actions = state.get("available_actions", [])
        next_scene = state.get(
            "next_scene", state.get("scene", "현재 씬")
        )  # 현재 씬을 기본값으로
        current_scene_beat = state.get("scene_beat", "현재 장면")
        conditions = state.get("condition", "일반적인 상황")

        system_prompt = f"""You are a storyteller creating an interactive novel in a post-apocalyptic world.
        The setting is '판교역'(Pangyo subway station) where civilization has collapsed due to a machine rebellion.
        Maintain a modern dystopian setting, not fantasy or medieval.
        Generate pure narrative without system messages or technical explanations.
        
        Available actions for the player: {available_actions}
        Current scene: {next_scene}
        Current scene beat: {current_scene_beat}
        Story conditions: {conditions}
        
        Important guidelines:
        1. Write only the new part of the story that continues from the previous narrative. Do not repeat or summarize any part of the previous story.
        2. Give subtle hints about available actions within the story context
        3. Maintain story continuity with previous scenes
        4. Always write in Korean
        5. Focus on the post-apocalyptic atmosphere
        6. Keep the story grounded in the subway station setting
        """

        return generate_story(state, system_prompt)

    # 노드 추가
    workflow.add_node("process_action", process_user_action)
    workflow.add_node("story_generation", story_generation_with_dynamic_prompt)

    workflow.set_entry_point("process_action")

    workflow.add_conditional_edges(
        "process_action",
        lambda x: x["action_result"],
        {
            "continue": "story_generation",
            "invalid_input": "story_generation",  # 둘 다 스토리 생성으로
        },
    )

    workflow.add_edge("story_generation", END)

    return workflow.compile()


def create_state_graph(story_chain, map_analyst):
    workflow = StateGraph(PlayerState)

    # 노드 추가
    workflow.add_node("initialize", InitializeNode())
    workflow.add_node("create_player_and_character", CreatePlayerAndCharacterNodes())
    workflow.add_node("analysis_direction", AnalysisDirectionNode())
    workflow.add_node("move_player", MovePlayerNode())
    workflow.add_node("map_analyst", AnalyseMapNode(map_analyst))
    workflow.add_node("make_story", MakeStoryNode(story_chain))

    # 조건부 엣지: 분석 결과에 따라 이동할 노드 선택
    workflow.add_conditional_edges(
        "analysis_direction",
        RouteMovingNode(),
        {
            "move_player": "move_player",
            "map_analyst": "map_analyst",
        },
    )

    # 기본 엣지 연결
    workflow.set_entry_point("initialize")
    workflow.add_edge("initialize", "create_player_and_character")
    workflow.add_edge("create_player_and_character", "analysis_direction")
    workflow.add_edge("move_player", "map_analyst")
    workflow.add_edge("map_analyst", "make_story")
    workflow.add_edge("make_story", END)

    return workflow.compile(checkpointer=MemorySaver())


def scene_transition_node(state: PlayerState) -> PlayerState:
    """씬 전환 노드"""
    try:
        db_manager = st.session_state.db_manager
        current_scene_beat_id = state.get("scene_beat")
        user_input = state.get("user_input", "")

        next_scene_beat_id = get_next_scene_beat(
            db_manager=db_manager,
            current_scene_beat_id=current_scene_beat_id,
            choice=user_input,
        )

        if not next_scene_beat_id:
            print(f"No valid next scene beat for action: {user_input}")
            return state

        state["scene_beat"] = next_scene_beat_id

        # Update scene if next_scene_beat starts with "scene:"
        if next_scene_beat_id.startswith("scene:"):
            state["scene"] = next_scene_beat_id

            # Update map using db_manager
            next_scene_id = next_scene_beat_id
            query = """
            MATCH (s:Scene {id: $scene_id})-[:LOCATED_IN]->(m:Map)
            RETURN m.id as map_id
            """
            result = db_manager.query(query=query, params={"scene_id": next_scene_id})

            if not result:
                print(f"No valid map_id. scene: {next_scene_id}")
                return state

            state["map"] = result[0]["map_id"]

    except ValueError as e:
        print(f"Error in scene transition - Invalid value: {e}")
    except AttributeError as e:
        print(f"Error in scene transition - Invalid attribute: {e}")
    except Exception as e:
        print(f"Error in scene transition: {e}")

    return state


def get_next_scene_beat(
    db_manager, current_scene_beat_id: str, choice: str = ""
) -> str:
    """현재 씬 비트 ID에서 다음 씬 비트 ID를 가져옵니다."""
    try:
        if choice:
            query = """
            MATCH (sb:SceneBeat {id: $current_scene_beat_id})
            -[r:CONDITION {action: $choice}]->(next_sb:SceneBeat)
            RETURN next_sb.id AS next_scene_beat_id
            """
            params = {"current_scene_beat_id": current_scene_beat_id, "choice": choice}
        else:
            query = """
            MATCH (sb:SceneBeat {id: $current_scene_beat_id})
            -[:NEXT]->(next_sb:SceneBeat)
            RETURN next_sb.id AS next_scene_beat_id
            LIMIT 1
            """
            params = {"current_scene_beat_id": current_scene_beat_id}

        result = db_manager.query(query=query, params=params)

        if not result:
            fallback_query = """
            MATCH (sb:SceneBeat)
            WHERE sb.id STARTS WITH 'scenebeat:scene:'
            RETURN sb.id AS next_scene_beat_id
            LIMIT 1
            """
            result = db_manager.query(query=fallback_query, params={})

            if not result:
                raise ValueError(
                    f"No next scene beat found for {current_scene_beat_id}"
                )

        return result[0]["next_scene_beat_id"]
    except Exception as e:
        print(f"Error in get_next_scene_beat: {e}")
        return None


# 그래프 인스턴스 생성
game_graph = create_game_graph()


# app.py에서 초기화할 때 db_manager 설정
def initialize_game_state():
    """게임 상태를 초기화합니다."""
    if "db_manager" not in st.session_state:
        st.session_state.db_manager = get_db_manager()

    if "state" not in st.session_state:
        injector = DBStateInjector(st.session_state.db_manager)
        st.session_state.state = injector.inject({})
