from langchain_neo4j import Neo4jGraph
import os
import random  # 임의의 10개 파일을 가지고 테스트 하기 위함.
import json
from dotenv import load_dotenv
from uuid import uuid4

load_dotenv()


JSON_PATH = "./data/stored_data/"

# 파일 목록 읽어오기
items = os.listdir(JSON_PATH)

# 파일만 필터링
files = [f for f in items if os.path.isfile(os.path.join(JSON_PATH, f))]

# 10개 고르기 (테스트용)
files = random.sample(files, 10)  # 테스트가 아닐 경우 주석 처리.

# JSON 파일 읽어오기

json_list = []

for file in files:
    file_path = JSON_PATH + file
    with open(file_path, "r", encoding="utf-8") as f:
        json_list.append(json.load(f))

# Graph connector 만들기.
graph = Neo4jGraph(
    url=os.getenv("NEO4J_URI"),
    username=os.getenv("NEO4J_USER"),
    password=os.getenv("NEO4J_PASSWORD"),
)


# DB 만들기
def create_graph(graph, doc):
    def extract_unit_key(unit):
        unit_key = set(unit.keys()) - {"story_scripts", "characters"}
        query_key = ""
        unit_properties = {}
        for k in unit_key:
            query_key += f"{k}: ${k}, "
            unit_properties[k] = unit[k]
        return query_key[:-2], unit_properties

    def extract_script_key(script):
        script_key = set(script.keys()) - {"character"}
        query_str = ""
        properties = {}
        for k in script_key:
            query_str += f"{k}: ${k}, "
            properties[k] = script[k]
        return query_str[:-2], properties

    # Document 노드 생성
    doc_id = str(uuid4())
    graph.query("""MATCH (n) DETACH DELETE n""")
    doc_properties = {
        "title": doc["title"],
        "theme": doc["theme"],
        "concept": doc["concept"],
        "motif": doc["motif"],
        "conflict": doc["conflict"],
        "id": doc_id,
    }

    graph.query(
        """
        MERGE (d:Document {title: $title})
        SET 
        d.theme= $theme, 
        d.concept= $concept,
        d.motif= $motif, 
        d.conflict= $conflict
""",
        doc_properties,
    )

    # Genre 노드와 관계 생성
    for genre in doc["genre"]:
        graph.query(
            """
                    MERGE (g:Genre {name: $genre})
                    MERGE (d:Document {title: $title})
                    MERGE (d)-[:HAS_GENRE]->(g)""",
            {"genre": genre, "title": doc["title"]},
        )

    # Character 노드와 관계 생성
    for char in doc["characters"]:
        char_id = char + "_" + doc["title"]
        # tx.run("""
        #        MERGE (c:Character {id: $char_id, name:$char})
        #    MERGE (d:Document {title: $title})-[:HAS_CHARACTER]->(c)""", char_id=char_id, char=char, title=doc['title'])
        graph.query(
            """MERGE (c:Character {id:$char_id, name: $char})
            MERGE (d:Document {title: $title})
            MERGE (d)-[:HAS_CHARACTER]->(c)
            """,
            {"char_id": char_id, "char": char, "title": doc["title"]},
        )

    #     # Unit 및 StoryScript 노드와 관계 생성
    for unit in doc["units"]:
        query_0, u_pro = extract_unit_key(unit)
        u_pro["title"] = doc["title"]
        query = (
            "MERGE (u:Unit {"
            + query_0
            + "})\n"
            + "MERGE (d:Document {title: $title})\n"
            + "MERGE (d)-[:HAS_UNIT]->(u)"
        )
        graph.query(query, u_pro)

        for char in unit["characters"]:
            char_id = char + "_" + doc["title"]
            query_str = """MERGE (c:Character {id: $char_id, name: $char})
            MERGE (u:Unit {stage: $stage, storyline: $storyline})
            MERGE (u)-[:INVOLVES]->(c)"""
            graph.query(
                query_str,
                {
                    "char_id": char_id,
                    "char": char,
                    "stage": unit["stage"],
                    "storyline": unit["storyline"],
                },
            )

        for script in unit["story_scripts"]:
            query_0, properties = extract_script_key(script)
            query = (
                "MERGE (s:StoryScript {"
                + query_0
                + "})\n"
                + "MERGE (u: Unit {stage: $stage, storyline: $storyline})\n"
                + "MERGE (u)-[:HAS_SCRIPT]->(s)"
            )
            properties["stage"] = unit["stage"]
            properties["storyline"] = unit["storyline"]

            graph.query(query, properties)

            for char in script["character"]:
                char_id = char + "_" + doc["title"]
                graph.query(
                    """
                            MERGE (c:Character {id: $char_id})
                            MERGE (s:StoryScript {content: $content})
                            MERGE (s)-[:PERFORMED_BY]->(c)""",
                    {"char_id": char_id, "content": script["content"]},
                )
