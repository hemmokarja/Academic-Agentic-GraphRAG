class StreamHandler:
    def __init__(self, show_tool_results=False):
        self.last_iteration = 0
        self.show_tool_results = show_tool_results
        self.pending_tool_calls = set()  # track pending tool calls

    def _handle_agent_chunk(self, chunk):
        agent_data = chunk["agent"]
        iteration = agent_data.get("iteration_count", 0)
        messages = agent_data.get("messages", [])

        if not messages:
            return ""
        
        # update tracking of the current iteration
        self.last_iteration = iteration

        message = messages[0]
        output = ""
        # check if this is a tool call (or multiple tool calls)
        if hasattr(message, "tool_calls") and message.tool_calls:
            output += f"🔧 **Calling {len(message.tool_calls)} tool(s):**\n\n"

            for tool_call in message.tool_calls:
                tool_id = tool_call.get('id', 'unknown')
                tool_name = tool_call.get('name', 'unknown')
                tool_args = tool_call.get('args', {})

                # track this tool call as pending
                self.pending_tool_calls.add(tool_id)

                output += f"  • `{tool_name}` (ID: `{tool_id}`)\n"
                output += f"    **Args**: `{tool_args}`\n\n"

            return output

        # check if this is a final answer
        elif hasattr(message, "content") and message.content:
            output += f"💡 **Final Answer:**\n\n{message.content}\n"
            return output
        
        else:
            raise RuntimeError(
                "Expected agent message to contain either tool_calls or content "
                f"attribute but got neither. Message: {message}"
            )

    def _handle_tools_chunk(self, chunk):
        tools_data = chunk["tools"]
        messages = tools_data.get("messages", [])
        errors = tools_data.get("errors", [])

        output = ""

        # handle errors
        if errors:
            for error in errors:
                if isinstance(error, dict):
                    error_msg = error.get("error", str(error))
                    tool_name = error.get("tool", "unknown")
                    tool_id = error.get("tool_call_id", "unknown")
                    output += (
                        f"⚠️ **{tool_name}** (ID: `{tool_id}`) encountered an "
                        f"issue: `{error_msg}`\n\n"
                    )

                    # remove from pending
                    self.pending_tool_calls.discard(tool_id)
                else:
                    output += f"❌ **Tool execution failed:** {error}\n\n"

        # handle successful tool results
        if messages:
            for tool_message in messages:
                tool_id = (
                    tool_message.tool_call_id
                    if hasattr(tool_message, "tool_call_id")
                    else "unknown"
                )
                tool_name = (
                    tool_message.name if hasattr(tool_message, "name") else "unknown"
                )
                result = (
                    tool_message.content if hasattr(tool_message, "content") else ""
                )

                tool_result = f"✅ **Tool result:** `{tool_name}` (ID: `{tool_id}`) "

                if self.show_tool_results:
                    tool_result += f"→ `{result}`\n\n"
                else:
                    tool_result += "success!\n\n"

                output += tool_result

                # remove from pending
                self.pending_tool_calls.discard(tool_id)

            # after all tool executions complete, show next thinking message
            if not self.pending_tool_calls:  # All tools have returned
                next_iteration = self.last_iteration + 1
                output += "\n" + self.get_thinking_message(next_iteration)

        return output

    def process_chunk(self, chunk):
        """
        Process a single chunk and return formatted output.
        Returns the text to append to the display.
        """
        output = ""

        if "agent" in chunk:
            return self._handle_agent_chunk(chunk)

        elif "tools" in chunk:
            return self._handle_tools_chunk(chunk)

        raise RuntimeError(
            "Expected chunk to contain tools or agent attribute, but got neither. "
            f"Chunk: {chunk}"
        )

    def get_thinking_message(self, iteration):
        return f"🤔 **Agent thinking (iteration {iteration})...**\n\n"
