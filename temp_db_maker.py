# Retriever를 만들기 위한 임시 DB Maker.
# 주의: 실행하면 기존 그래프DB에 있는 파일 모두 삭제. #

from uuid import uuid4
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_neo4j import Neo4jGraph
import os
import random  # 임의의 10개 파일을 가지고 테스트 하기 위함.
import json
from dotenv import load_dotenv

load_dotenv()

# 데이터 경로에 맞게 수정.
JSON_PATH = "./data/stored_data/"

# 파일 목록 읽어오기
items = os.listdir(JSON_PATH)

# 파일만 필터링
files = [f for f in items if os.path.isfile(os.path.join(JSON_PATH, f))]

# 10개 고르기
files = random.sample(files, 10)

# JSON 파일 읽어오기

json_list = []

for file in files:
    file_path = JSON_PATH + file
    with open(file_path, "r", encoding="utf-8") as f:
        json_list.append(json.load(f))


graph = Neo4jGraph(
    url=os.getenv("NEO4J_URI"),
    username=os.getenv("NEO4J_USER"),
    password=os.getenv("NEO4J_PASSWORD"),
)

embedding_provider = OpenAIEmbeddings(model="text-embedding-3-small")


def create_work_node(graph, work):
    # (Work)-[:CONTAINS]-(Unit)
    # (Unit)-[:INCLUDES]-(StoryScript)
    # (StoryScript)-[:PERFORMS]-(Act)
    # (StoryScript)-[:FEELS]-(Emotion)

    # 자주 쓰는 변수 생성.
    title = work["title"]
    # Work label 노드 생성 및 속성: title
    work_id = str(uuid4())
    graph.query("""MERGE (w:Work {title: $title})""", {"title": title})

    # @ 장르, 속성 genre
    # @ Motif 속성, motif
    # @ theme , 속성: theme

    # Unit 노드와 관계 생성 , 속성: storyline, storyline_embedding!!
    unit_num = 0
    for unit in work["units"]:
        unit_num += 1
        unit_id = f"u{unit_num}.{title}"
        storyline = unit["storyline"]
        # Embed the storyline
        storyline_embedding = embedding_provider.embed_query(storyline)
        query = (
            "MERGE (w:Work {title: $title})\n"
            + "MERGE (u: Unit {id: $unit_id})\n"
            + "SET u.storyline= $storyline\n"
            + "MERGE (w)-[:CONTAINS]->(u)\n"
            + "MERGE (u)-[:PART_OF]->(w)\n"
            + "WITH u\n"
            + "CALL db.create.setNodeVectorProperty(u, 'storylineEmbedding', $embedding)"
        )
        graph.query(
            query,
            {
                "title": title,
                "unit_id": unit_id,
                "storyline": storyline,
                "embedding": storyline_embedding,
            },
        )

        # StoryScript 노드, 속성: content
        ss_num = 0
        for script in unit["story_scripts"]:
            ss_num += 1
            ss_id = f"u{unit_num}.ss{ss_num}.{title}"
            query = """
            MERGE (s:StoryScript {id: $ss_id, content: $content})
            MERGE (u:Unit {id: $unit_id})
            MERGE (u)-[:INCLUDES]->(s)"""
            graph.query(
                query,
                {"ss_id": ss_id, "content": script["content"], "unit_id": unit_id},
            )

            # Act 노드 (있으면), 관계 생성
            if "act" in script.keys():
                act_list = script["act"].split("/")
                for act in act_list:
                    act_query = """
                    MERGE (a:Act {act: $act})
                    MERGE (s:StoryScript {id: $ss_id})
                    MERGE (s)-[:PERFORMS]->(a)
                    """
                    graph.query(act_query, {"act": act, "ss_id": ss_id})
            # emotion 노드 (있으면), 관계 생성
            if "emotion" in script.keys():
                emo_list = script["emotion"].split("/")
                for em in emo_list:
                    em_query = """
                    MERGE (e:Emotion {emotion: $emotion})
                    MERGE (s:StoryScript {id: $ss_id})
                    MERGE (s)-[:FEELS]->(e)"""
                    graph.query(em_query, {"emotion": em, "ss_id": ss_id})


def make_db(files=json_list, graph=graph):
    # DB에 있던 파일 모두 삭제.
    graph.query("MATCH (n) DETACH DELETE n")

    for work in json_list:
        create_work_node(graph, work)

    # index 만들기
    index_query = """
CREATE VECTOR INDEX storylineVector
IF NOT EXISTS
FOR (u:Unit) ON (u.storylineEmbedding)
OPTIONS {indexConfig: {
    `vector.dimensions`:1536,
    `vector.similarity_function`: 'cosine'
    }};"""
    graph.query(index_query)


if __name__ == "__main__":
    execute = input("그래프DB의 데이터를 모두 삭제하고 다시 만듭니다.(y/n)> ")
    if execute.lower() == "y":
        make_db()
