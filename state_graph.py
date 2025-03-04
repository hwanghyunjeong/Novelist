# state_graph.py
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from states import PlayerState 
from node import (
    InitializeNode,
    AnalysisDirectionNode,
    MovePlayerNode,
    AnalyseMapNode,
    MakeStoryNode,
    RouteMovingNode,
    CreatePlayerAndCharacterNodes,
)


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
