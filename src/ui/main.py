import atexit
import logging

from langchain_openai import ChatOpenAI

from rag import driver
from rag.agent import AgentConfig, ReActAgent
from rag.tools import (
    author_tools, citation_tools, method_tools, paper_tools, search_tools
)
from ui import chat

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
atexit.register(driver.close_neo4j_driver)


def main():

    with open("config/prompts/system.md", "r") as f:
        system_message = f.read()

    llm = ChatOpenAI(model="gpt-4.1")
    tools = [
        search_tools.search_nodes,
        author_tools.author_papers,
        author_tools.author_coauthors,
        citation_tools.paper_citations_out,
        citation_tools.paper_citations_in,
        citation_tools.paper_citation_chain,
        method_tools.method_papers,
        method_tools.category_papers,
        method_tools.paper_methods,
        method_tools.category_methods,
        method_tools.method_categories,
        method_tools.task_papers,
        method_tools.paper_tasks,
        paper_tools.paper_authors,
    ]
    config = AgentConfig(
        max_iterations=10,
        max_execution_time=120.0,
        tool_execution_timeout=60.0,
        max_tool_retries=2,
        system_message=system_message
    )
    agent = ReActAgent(llm=llm, tools=tools, config=config)

    chat.chat(
        agent,
        page_title="🤖 Research Assistant Chat",
        page_subtitle=(
            "Ask me about ML papers, research trends, authors, or methods—I'll help "
            "you explore!"
        )
    )


if __name__ == "__main__":
    main()
