# 패키지 불러오기.
import os
from dotenv import load_dotenv

load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_neo4j import Neo4jGraph, Neo4jVector

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

embedding_provider = OpenAIEmbeddings(model="text-embedding-3-small")

graph = Neo4jGraph(
    url=os.getenv("NEO4J_URI"),
    username=os.getenv("NEO4J_USER"),
    password=os.getenv("NEO4J_PASSWORD"),
)

storyline_vector = Neo4jVector.from_existing_index(
    embedding_provider,
    graph=graph,
    index_name="storylineVector",
    node_label="Unit",
    embedding_node_property="storylineEmbedding",
    text_node_property="storyline",
    # 아래를 수정해서, retriever한 Document의 요소를 정할 수 있음.
    retrieval_query="""
//
RETURN node.storyline as text, score,
{ 
    content: [(node)-[:INCLUDES]->(script) | script.content]
} as metadata

// 
""",
)

# Create Retriever, 상위6개 검색.
retriever = storyline_vector.as_retriever(search_kwargs={"k": 6})


def execute_retriever(retriever=retriever):
    while (q := input("> ")) != "exit":
        print(retriever.invoke(q)[0:3])


if __name__ == "__main__":
    execute_retriever()
