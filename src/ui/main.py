import atexit
import os
import logging

from rag import driver
from rag.agent import AgentConfig, ReActAgent
from rag.tools import (
    author_tools, citation_tools, method_tools, search_tools
)
from ui import chat, util

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
atexit.register(driver.close_neo4j_driver)


def main():
    model_name = os.getenv("MODEL_NAME", "gpt-4.1")
    system_message = util.get_system_message(model_name)
    llm = util.get_llm(model_name)
    tools = [
        search_tools.search_nodes,
        author_tools.author_papers,
        author_tools.paper_authors,
        author_tools.author_coauthors,
        citation_tools.paper_citations_out,
        citation_tools.paper_citations_in,
        citation_tools.paper_citation_chain,
        method_tools.method_papers,
        method_tools.paper_methods,
        method_tools.task_papers,
        method_tools.paper_tasks,
        method_tools.category_papers,
        method_tools.category_methods,
        method_tools.method_categories,
    ]
    config = AgentConfig(
        max_iterations=20,
        max_execution_time=1200.0,  # 20 min
        tool_execution_timeout=60.0,
        max_tool_retries=2,
        system_message=system_message,
        langgraph_recursion_limit=100,
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
