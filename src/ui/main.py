import streamlit as st
from langchain_openai import ChatOpenAI

from rag.agent import AgentConfig, ReActAgent
from rag.tools.arithmetic import (
    add_numbers, divide_numbers, multiply_numbers, subtract_numbers
)
from ui import chat


def main():
    llm = ChatOpenAI(model="gpt-4.1")
    tools = [add_numbers, subtract_numbers, multiply_numbers, divide_numbers]
    config = AgentConfig(
        max_iterations=10,
        max_execution_time=120.0,
        tool_execution_timeout=60.0,
        max_tool_retries=2,
        system_message=(
            "You are a helpful assistant with access to tools enabling arithmetic computation. "
            "Always rely on the available tools to answer questions accurately. "
            "Do NOT make any arithmetic computations without the provided tools!"
        )
    )
    agent = ReActAgent(llm=llm, tools=tools, config=config)

    chat.chat(agent)


if __name__ == "__main__":
    main()
