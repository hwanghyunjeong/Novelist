import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Neo4jVector
from langchain_neo4j import Neo4jGraph
import config

# 환경 설정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FINAL_DATA_DIR = os.path.join(SCRIPT_DIR, "data", "final")


class RAGDBManager:
    """RAG를 위한 데이터베이스 관리 클래스"""

    def __init__(self):
        """초기화 및 Neo4j 연결 설정"""
        load_dotenv()
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        self.graph = Neo4jGraph(
            url=config.NEO4J_URI,
            username=config.NEO4J_USER,
            password=config.NEO4J_PASSWORD,
            database=config.NEO4J_DATABASE,
        )

        # 벡터 인덱스 초기화
        self._init_vector_indexes()

        # 임베딩 캐시 초기화
        self.act_embed_dict = {}
        self.emotion_embed_dict = {}

    def _init_vector_indexes(self):
        """벡터 인덱스 초기화"""
        # 스토리라인 벡터 인덱스
        create_storyline_index = """
        CREATE VECTOR INDEX storyline_embeddings IF NOT EXISTS
        FOR (n:Unit)
        ON (n.storylineEmbedding)
        OPTIONS {indexConfig: {
            `vector.dimensions`: 1536,
            `vector.similarity_function`: 'cosine'
        }}
        """

        # 행위 벡터 인덱스
        create_act_index = """
        CREATE VECTOR INDEX act_embeddings IF NOT EXISTS
        FOR (n:Act)
        ON (n.actEmbedding)
        OPTIONS {indexConfig: {
            `vector.dimensions`: 1536,
            `vector.similarity_function`: 'cosine'
        }}
        """

        # 감정 벡터 인덱스
        create_emotion_index = """
        CREATE VECTOR INDEX emotion_embeddings IF NOT EXISTS
        FOR (n:Emotion)
        ON (n.emotionEmbedding)
        OPTIONS {indexConfig: {
            `vector.dimensions`: 1536,
            `vector.similarity_function`: 'cosine'
        }}
        """

        try:
            self.graph.query(create_storyline_index)
            self.graph.query(create_act_index)
            self.graph.query(create_emotion_index)
        except Exception as e:
            print(f"인덱스 생성 중 예외 발생 (이미 존재할 수 있음): {str(e)}")

    def get_json_files(self) -> List[str]:
        """JSON 파일 목록 가져오기"""
        # 파일 목록 읽어오기
        items = os.listdir(FINAL_DATA_DIR)
        # 파일만 필터링
        files = [
            f
            for f in items
            if os.path.isfile(os.path.join(FINAL_DATA_DIR, f)) and f.endswith(".json")
        ]
        return files

    def create_work_node(self, data: Dict[str, Any], source: str) -> str:
        """작품 노드 생성"""
        work_id = f"work:{source}"
        query = """
        MERGE (w:Work {
            id: $id,
            theme: $theme,
            concept: $concept,
            motif: $motif,
            conflict: $conflict
        })
        """
        params = {
            "id": work_id,
            "theme": data.get("theme", ""),
            "concept": data.get("concept", ""),
            "motif": data.get("motif", ""),
            "conflict": data.get("conflict", ""),
        }
        self.graph.query(query, params=params)
        return work_id

    def create_unit_node(self, data: Dict[str, Any], work_id: str) -> str:
        """단위 노드 생성"""
        unit_id = f"unit:{work_id}:{data.get('id', '')}"

        # 스토리라인 임베딩 생성
        if "storyline" in data:
            storyline_embedding = self.embeddings.embed_query(data["storyline"])

            query = """
            MERGE (u:Unit {
                id: $id,
                storyline: $storyline,
                unit_motif: $unit_motif
            })
            WITH u
            CALL db.create.setNodeVectorProperty(u, 'storylineEmbedding', $embedding)
            WITH u
            MATCH (w:Work {id: $work_id})
            MERGE (w)-[:CONTAINS]->(u)
            MERGE (u)-[:PART_OF]->(w)
            """
            params = {
                "id": unit_id,
                "storyline": data.get("storyline", ""),
                "unit_motif": data.get("unit_motif", ""),
                "embedding": storyline_embedding,
                "work_id": work_id,
            }
            self.graph.query(query, params=params)

        return unit_id

    def create_story_script_node(self, data: Dict[str, Any], unit_id: str) -> str:
        """스토리 스크립트 노드 생성"""
        script_id = f"script:{unit_id}:{data.get('id', '')}"

        # 기본 스크립트 노드 생성 및 Unit과의 관계
        query = """
        MERGE (s:StoryScript {
            id: $id,
            content: $content,
            location: $location
        })
        WITH s
        MATCH (u:Unit {id: $unit_id})
        MERGE (u)-[:INCLUDES]->(s)
        """
        params = {
            "id": script_id,
            "content": data.get("content", ""),
            "location": data.get("location", ""),
            "unit_id": unit_id,
        }
        self.graph.query(query, params=params)

        # characters 관계 생성 (한 번의 쿼리로)
        if "characters" in data and data["characters"]:
            chars_query = """
            MATCH (s:StoryScript {id: $script_id})
            UNWIND $characters as char
            MERGE (c:Character {id: char})
            MERGE (c)-[:APPEARS_IN]->(s)
            """
            self.graph.query(
                chars_query,
                params={"script_id": script_id, "characters": data["characters"]},
            )

        return script_id

    def create_act_emotion_nodes(self, data: Dict[str, Any], script_id: str) -> None:
        """행위와 감정 노드 생성"""
        # 행위 노드 생성
        if "act" in data:
            act_list = data["act"].split("/")
            if act_list:
                act = act_list[0].strip()
                if act:
                    if act not in self.act_embed_dict:
                        self.act_embed_dict[act] = self.embeddings.embed_query(act)
                    act_embedding = self.act_embed_dict[act]

                    query = """
                    MERGE (a:Act {
                        id: $id,
                        act: $act
                    })
                    WITH a
                    CALL db.create.setNodeVectorProperty(a, 'actEmbedding', $act_embedding)
                    WITH a
                    MATCH (s:StoryScript {id: $script_id})
                    MERGE (s)-[:PERFORMS]->(a)
                    """
                    params = {
                        "id": f"act:{script_id}:{act}",
                        "act": act,
                        "act_embedding": act_embedding,
                        "script_id": script_id,
                    }
                    self.graph.query(query, params=params)

        # 감정 노드 생성
        if "emotion" in data:
            emotion_list = data["emotion"].split("/")
            if emotion_list:
                emotion = emotion_list[0].strip()
                if emotion:
                    if emotion not in self.emotion_embed_dict:
                        self.emotion_embed_dict[emotion] = self.embeddings.embed_query(
                            emotion
                        )
                    emotion_embedding = self.emotion_embed_dict[emotion]

                    query = """
                    MERGE (e:Emotion {
                        id: $id,
                        emotion: $emotion
                    })
                    WITH e
                    CALL db.create.setNodeVectorProperty(e, 'emotionEmbedding', $emotion_embedding)
                    WITH e
                    MATCH (s:StoryScript {id: $script_id})
                    MERGE (s)-[:FEELS]->(e)
                    """
                    params = {
                        "id": f"emotion:{script_id}:{emotion}",
                        "emotion": emotion,
                        "emotion_embedding": emotion_embedding,
                        "script_id": script_id,
                    }
                    self.graph.query(query, params=params)

    def process_json_file(self, file_path: str) -> None:
        """JSON 파일 처리"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            source = os.path.splitext(os.path.basename(file_path))[0]

            # Work 노드 생성
            work_id = self.create_work_node(data, source)

            # 단일 Unit 노드 생성 (storylines 기반)
            if "story_scripts" in data:
                # 첫 번째 스크립트의 storylines을 unit의 storyline으로 사용
                first_script = data["story_scripts"][0]
                unit_data = {
                    "id": f"unit:{source}",
                    "storyline": first_script.get("storylines", ""),
                    "unit_motif": first_script.get("unit_motif", ""),
                }
                unit_id = self.create_unit_node(unit_data, work_id)

                # StoryScript 노드들 생성
                for script_data in data.get("story_scripts", []):
                    script_id = self.create_story_script_node(script_data, unit_id)
                    self.create_act_emotion_nodes(script_data, script_id)

        except Exception as e:
            print(f"파일 처리 중 오류 발생 ({file_path}): {str(e)}")
            raise  # 디버깅을 위해 예외를 다시 발생시킵니다.


def main():
    """메인 실행 함수"""
    try:
        print("RAG 데이터베이스 구축 시작...")
        rag_manager = RAGDBManager()

        # 모든 JSON 파일 가져오기
        json_files = rag_manager.get_json_files()
        print(f"총 {len(json_files)}개의 JSON 파일을 처리합니다.")

        for idx, file_name in enumerate(json_files, 1):
            file_path = os.path.join(FINAL_DATA_DIR, file_name)
            print(f"[{idx}/{len(json_files)}] 처리 중: {file_name}")
            rag_manager.process_json_file(file_path)

        print("RAG 데이터베이스 구축 완료")

    except Exception as e:
        print(f"실행 중 오류 발생: {str(e)}")


if __name__ == "__main__":
    main()
