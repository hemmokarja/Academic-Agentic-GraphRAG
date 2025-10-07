import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import (
    Annotated, Any, Dict, Generator, List, Literal, Optional, Sequence, TypedDict
)

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
)
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AgentConfig(BaseModel):
    max_iterations: int = Field(
        default=15,
        description="Maximum number of reasoning iterations before forcing stop"
    )
    max_execution_time: float = Field(
        default=300.0,
        description="Maximum execution time in seconds"
    )
    tool_execution_timeout: float = Field(
        default=30.0,
        description="Timeout for individual tool executions"
    )
    max_tool_retries: int = Field(
        default=2,
        description="Maximum retries for failed tool executions"
    )
    system_message: Optional[str] = Field(
        default=None,
        description="System message to prepend to conversations"
    )
    max_workers: int = Field(
        default=4,
        description="Maximum number of worker threads for tool execution"
    )


class TimeoutError(Exception):
    """Raised when tool execution times out."""
    pass


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    iteration_count: int
    start_time: float
    errors: List[Dict[str, Any]]


class ReActAgent:
    def __init__(
        self,
        llm: BaseChatModel,
        tools: List[BaseTool],
        config: AgentConfig = AgentConfig(),
        checkpointer: Optional[Any] = None
    ):
        self.llm = llm
        self.tools = tools
        self.config = config
        self.checkpointer = checkpointer or MemorySaver()

        self.llm_with_tools = self.llm.bind_tools(tools)
        self.tools_by_name = {t.name: t for t in tools}

        # thread pool for tool execution with proper timeout support
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_workers)

        self.graph = self._build_graph()

        logger.info(f"ReAct agent initialized with {len(tools)} tools")
    
    def __del__(self):
        # cleanup thread pool on deletion
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=False)

    def _build_graph(self) -> Any:
        workflow = StateGraph(AgentState)

        workflow.add_node("agent", self._agent_node)
        workflow.add_node("tools", self._tools_node)

        workflow.add_edge(START, "agent")
        workflow.add_edge("tools", "agent")

        workflow.add_conditional_edges(
            "agent",
            self._route_after_agent,
            {
                "tools": "tools",
                "end": END
            }
        )
        
        return workflow.compile(checkpointer=self.checkpointer)

    def _generate_summary(self, messages: List[BaseMessage]) -> str:
        """Generate a summary of the conversation so far."""
        prompt = HumanMessage(
            content=(
                "Summarize the conversation. Focus on the main facts, any "
                "uncertainties, and recommend one next step. Do not repeat raw tool "
                "outputs verbatim; synthesize them. Aim at responding to the user's "
                "original question as well as the provided material allows."
                "State what you didn't manage to achieve."
            )
        )
        messages_with_prompt = messages + [prompt]
        try:
            resp = self.llm.invoke(messages_with_prompt)
            return resp.content.strip()
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
            return "I couldn't produce a summary due to an error."


    def _handle_agent_iter_overrun(self, messages, iteration):
        logger.warning(f"Max iterations ({self.config.max_iterations}) reached")
        summary = self._generate_summary(messages)
        message = AIMessage(
            content=(
                f"I've reached the maximum number of reasoning steps "
                f"({self.config.max_iterations}). Here's what I found:\n\n{summary}"
            )
        )
        return {
            "messages": [message],
            "iteration_count": iteration + 1
        }

    def _handle_agent_timeout(self, messages, iteration):
        logger.warning(
            f"Max execution time ({self.config.max_execution_time}s) exceeded"
        )
        summary = self._generate_summary(messages)
        message = AIMessage(
            content=(
                f"I've reached the time limit for this query. "
                f"Here's what I found:\n\n{summary}"
            )
        )
        return {
            "messages": [message],
            "iteration_count": iteration + 1
        }

    def _agent_node(self, state: AgentState) -> Dict[str, Any]:
        messages = list(state["messages"])
        iteration = state.get("iteration_count", 0)

        if iteration >= self.config.max_iterations:
            return self._handle_agent_iter_overrun(messages, iteration)

        elapsed = time.time() - state.get("start_time", time.time())
        if elapsed > self.config.max_execution_time:
            return self._handle_agent_timeout(messages, iteration)

        # add system message on first iteration if configured
        if self.config.system_message and iteration == 0:
            if not any(isinstance(msg, SystemMessage) for msg in messages):
                messages = (
                    [SystemMessage(content=self.config.system_message)] + messages
                )

        # invoke agent
        try:
            logger.info(f"Agent reasoning (iteration {iteration + 1})...")
            response = self.llm_with_tools.invoke(messages)

            if hasattr(response, "tool_calls") and response.tool_calls:
                logger.info(f"Agent planning to call {len(response.tool_calls)} tool(s)")
                for tc in response.tool_calls:
                    logger.debug(f"  - {tc['name']}({tc['args']})")

            return {
                "messages": [response],
                "iteration_count": iteration + 1
            }

        except Exception as e:
            logger.error(f"Agent node error: {e}", exc_info=True)

            error_record = {
                "node": "agent",
                "error": str(e),
                "error_type": type(e).__name__,
                "timestamp": time.time(),
                "iteration": iteration
            }

            return {
                "messages": [
                    AIMessage(
                        content=(
                            f"I encountered an error while processing your request: "
                            f"{str(e)}. Please try rephrasing your question or "
                            "breaking it into smaller parts."
                        )
                    )
                ],
                "iteration_count": iteration + 1,
                "errors": [error_record]
            }
    
    def _execute_tool_with_timeout(
        self, 
        tool: BaseTool, 
        tool_args: Dict[str, Any], 
        timeout_seconds: float
    ) -> Any:
        """
        Execute a tool with a timeout using ThreadPoolExecutor.
        This works in any thread context (main or worker threads).
        """
        if timeout_seconds is None or timeout_seconds <= 0:
            # No timeout, execute directly
            return tool.invoke(tool_args)

        # submit to thread pool and wait with timeout
        future = self.executor.submit(tool.invoke, tool_args)        
        try:
            result = future.result(timeout=timeout_seconds)
            return result
        except FuturesTimeoutError:
            # cancel the future (note: this doesn't kill the thread, but prevents waiting)
            future.cancel()
            raise TimeoutError(
                f"Tool execution timed out after {timeout_seconds} seconds"
            )
        except Exception as e:
            # re-raise any other exception from tool execution
            raise

    def _execute_single_tool_call(
        self, 
        tool_call: Dict[str, Any], 
        attempt_number: int
    ) -> tuple[ToolMessage, Optional[Dict[str, Any]]]:
        """
        Execute a single tool call attempt.

        Returns:
            tuple: (ToolMessage, error_record or None)
        """
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]
        
        try:
            if tool_name not in self.tools_by_name:
                raise ValueError(f"Unknown tool: {tool_name}")

            tool = self.tools_by_name[tool_name]

            start_time = time.time()
            result = self._execute_tool_with_timeout(
                tool, 
                tool_args, 
                self.config.tool_execution_timeout
            )
            elapsed = time.time() - start_time

            logger.info(
                f"Tool {tool_name} executed successfully in {elapsed:.2f}s"
            )

            return (
                ToolMessage(
                    content=str(result),
                    tool_call_id=tool_id,
                    name=tool_name
                ),
                None
            )

        except TimeoutError as te:
            logger.error(f"Tool {tool_name} timed out: {te}")

            error_msg = (
                f"Tool '{tool_name}' timed out after "
                f"{self.config.max_tool_retries + 1} attempts. "
                f"Each attempt exceeded {self.config.tool_execution_timeout}s timeout."
            )
            error_record = {
                "node": "tools",
                "tool": tool_name,
                "error": str(te),
                "error_type": "TimeoutError",
                "attempts": self.config.max_tool_retries + 1,
                "timestamp": time.time()
            }
            return (
                ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_id,
                    name=tool_name
                ),
                error_record
            )

        except Exception as e:
            logger.error(
                f"Tool {tool_name} failed (attempt "
                f"{attempt_number + 1}/{self.config.max_tool_retries + 1}): {e}"
            )

            error_msg = (
                f"Tool '{tool_name}' failed after "
                f"{self.config.max_tool_retries + 1} attempts. "
                f"Error: {str(e)}. Please try a different approach or "
                "rephrase your query."
            )
            error_record = {
                "node": "tools",
                "tool": tool_name,
                "error": str(e),
                "error_type": type(e).__name__,
                "attempts": self.config.max_tool_retries + 1,
                "timestamp": time.time()
            }
            return (
                ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_id,
                    name=tool_name
                ),
                error_record
            )

    def _execute_tool_call_with_retries(
        self, 
        tool_call: Dict[str, Any]
    ) -> tuple[ToolMessage, Optional[Dict[str, Any]]]:
        """
        Execute a tool call with retry logic and exponential backoff.

        Returns:
            tuple: (ToolMessage, error_record or None)
        """
        tool_name = tool_call["name"]
        logger.info(f"Executing tool: {tool_name}")
        
        for attempt in range(self.config.max_tool_retries + 1):
            tool_message, error_record = self._execute_single_tool_call(
                tool_call, attempt
            )

            # success case, no error record
            if error_record is None:
                return (tool_message, None)

            # failure case, check if we should retry
            if attempt < self.config.max_tool_retries:
                wait_time = 0.5 * (2 ** attempt)
                logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                # final attempt failed, return error
                return (tool_message, error_record)

    def _tools_node(self, state: AgentState) -> Dict[str, Any]:
        """Execute all tool calls from the last agent message."""
        last_message = state["messages"][-1]

        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            logger.warning("Tools node called but no tool calls found")
            return {}

        tool_messages = []
        errors = []

        for tool_call in last_message.tool_calls:
            tool_message, error_record = self._execute_tool_call_with_retries(
                tool_call
            )
            tool_messages.append(tool_message)
            
            if error_record is not None:
                errors.append(error_record)
        
        return {
            "messages": tool_messages,
            "errors": errors if errors else []
        }

    def _route_after_agent(self, state: AgentState) -> Literal["tools", "end"]:
        last_message = state["messages"][-1]

        if not hasattr(last_message, "tool_calls"):
            return "end"
        
        if not last_message.tool_calls:
            return "end"

        return "tools"

    def invoke(
        self,
        input_message: str,
        config: Optional[RunnableConfig] = None
    ) -> Dict[str, Any]:
        """Execute the agent synchronously and return the final state."""
        logger.info("Starting agent execution...")

        initial_state = {
            "messages": [HumanMessage(content=input_message)],
            "iteration_count": 0,
            "start_time": time.time(),
            "errors": []
        }
        try:
            final_state = self.graph.invoke(initial_state, config=config)
            
            execution_time = time.time() - final_state["start_time"]
            logger.info(
                f"Agent execution completed: "
                f"iterations={final_state['iteration_count']}, "
                f"time={execution_time:.2f}s, "
                f"errors={len(final_state.get('errors', []))}"
            )

            return final_state
            
        except Exception as e:
            logger.error(f"Agent execution failed: {e}", exc_info=True)
            raise

    def stream(
        self,
        input_message: str,
        config: Optional[RunnableConfig] = None,
        stream_mode: Literal["messages", "updates"] = "messages"
    ) -> Generator[Any, Any, Any]:
        """Stream agent execution chunks in real-time."""
        logger.info("Starting agent streaming execution...")

        initial_state = {
            "messages": [HumanMessage(content=input_message)],
            "iteration_count": 0,
            "start_time": time.time(),
            "errors": []
        }
        try:
            for chunk in self.graph.stream(
                initial_state, config=config, stream_mode=stream_mode
            ):
                yield chunk

        except Exception as e:
            logger.exception("Agent execution failed!")
            err = {"error": str(e)}
            yield err if stream_mode != "messages" else (err, None)

        finally:
            duration = time.time() - initial_state["start_time"]
            logger.info(f"Agent execution finished in {duration:.2f}s")

    def shutdown(self):
        """Gracefully shutdown the thread pool executor."""
        logger.info("Shutting down agent thread pool...")
        self.executor.shutdown(wait=True)
