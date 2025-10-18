import json


class StreamHandler:
    def __init__(
        self,
        model_name,
        show_tool_results=False,
        show_token_usage=True
    ):
        self.show_tool_results = show_tool_results
        self.show_token_usage = show_token_usage

        self.last_iteration = 0
        self.pending_tool_calls = set()  # track pending tool calls

        with open("src/ui/api_pricing.json", "r") as f:
            model_to_pricing = json.loads(f.read())

        self.pricing = model_to_pricing.get(model_name)

    def _format_agent_tool_calls(self, message):

        def _extract_details(tool_call):
            tool_id = tool_call.get("id", "unknown")
            tool_name = tool_call.get("name", "unknown")
            tool_args = tool_call.get("args", {})
            return tool_id, tool_name, tool_args

        # only one tool call
        if len(message.tool_calls) == 1:
            tool_call = message.tool_calls[0]
            tool_id, tool_name, tool_args = _extract_details(tool_call)
            self.pending_tool_calls.add(tool_id)
            return (
                f"🔧 **Calling tool:** `{tool_name}` (ID: `{tool_id}`) "
                f"**Args**: `{tool_args}`\n\n"
            )

        # several simultaneous calls
        else:
            output = f"🔧 **Calling {len(message.tool_calls)} tools:**\n\n"

            for tool_call in message.tool_calls:
                tool_id, tool_name, tool_args = _extract_details(tool_call)
                self.pending_tool_calls.add(tool_id)
                output += (
                    f"  • `{tool_name}` (ID: `{tool_id}`) **Args**: `{tool_args}`\n\n"
                )
            return output

    def _format_token_usage(self, token_usage):
        input_tokens = token_usage["input_tokens"]
        output_tokens = token_usage["output_tokens"]
        total_tokens = token_usage["total_tokens"]

        if self.pricing:
            input_price = self.pricing["input"] * (input_tokens / 1e6)
            output_price = self.pricing["output"] * (output_tokens / 1e6)
            total_price = input_price + output_price
            
            return (
                f"\n<sub style='color: #888; font-style: italic;'>"
                f"This response: {input_tokens:,}↑ + {output_tokens:,}↓ "
                f"= {total_tokens:,} tokens • ${total_price:.4f}"
                f"</sub>\n"
            )
        else:
            return (
                f"\n<sub style='color: #888; font-style: italic;'>"
                f"This response: {input_tokens:,}↑ + {output_tokens:,}↓ "
                f"= {total_tokens:,} tokens"
                f"</sub>\n"
            )

    def _handle_agent_chunk(self, chunk):
        agent_data = chunk["agent"]
        iteration = agent_data["iteration_count"]
        messages = agent_data["messages"]
        token_usage = agent_data["token_usage"]

        if not messages:
            return ""

        self.last_iteration = iteration  # update tracking of the current iteration

        message = messages[0]

        if hasattr(message, "tool_calls") and message.tool_calls:
            return self._format_agent_tool_calls(message)

        elif hasattr(message, "content") and message.content:
            output = f"💡 **Final Answer:**\n\n{message.content}\n"
            if self.show_token_usage:
                output += self._format_token_usage(token_usage)
            return output

        else:
            raise RuntimeError(
                "Expected agent message to contain either tool_calls or content "
                f"attribute but got neither. Message: {message}"
            )

    def _format_tool_errors(self, errors):
        output = ""
        for error in errors:
            if isinstance(error, dict):
                error_msg = error.get("error", str(error))
                tool_name = error.get("tool", "unknown")
                tool_id = error.get("tool_call_id", "unknown")
                output += (
                    f"⚠️ **Issue with tool:** `{tool_name}` (ID: `{tool_id}`) :"
                    f"`{error_msg}`\n\n"
                )

                # remove from pending
                self.pending_tool_calls.discard(tool_id)
            else:
                output += f"❌ **Tool execution failed:** {error}\n\n"
        return output

    def _format_tool_messages(self, messages):
        # handle successful tool results
        output = ""
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

    def _handle_tools_chunk(self, chunk):
        messages = chunk["tools"].get("messages", [])
        errors = chunk["tools"].get("errors", [])

        if errors:
            return self._format_tool_errors(errors)

        if messages:
            return self._format_tool_messages(messages)

        raise RuntimeError(
            "Expected tools chunk to have errors or messages, but got neither. "
            f"Chunk: {chunk}"
        ) 

    def process_chunk(self, chunk):
        """
        Process a single chunk and return formatted output.
        Returns the text to append to the display.
        """
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
