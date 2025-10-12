import atexit
import logging

from langchain_openai import ChatOpenAI

from rag import driver
from rag.agent import AgentConfig, ReActAgent
from rag.tools import search
from ui import chat

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
atexit.register(driver.close_neo4j_driver)


def main():

    with open("src/rag/system_messages/react_graph_rag.txt", "r") as f:
        system_message = f.read()

    llm = ChatOpenAI(model="gpt-4.1")
    tools = [search.search_nodes]
    config = AgentConfig(
        max_iterations=10,
        max_execution_time=120.0,
        tool_execution_timeout=60.0,
        max_tool_retries=2,
        system_message=system_message
    )
    agent = ReActAgent(llm=llm, tools=tools, config=config)

    chat.chat(agent)


if __name__ == "__main__":
    main()
