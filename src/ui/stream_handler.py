class StreamHandler:
    def __init__(self):
        self.last_iteration = 0

    def process_chunk(self, chunk):
        """
        Process a single chunk and return formatted output.
        Returns the text to append to the display.
        """
        output = ""

        if "agent" in chunk:
            agent_data = chunk["agent"]
            iteration = agent_data.get("iteration_count", 0)
            messages = agent_data.get("messages", [])

            if not messages:
                return ""

            message = messages[0]

            # update tracking of the current iteration
            self.last_iteration = iteration
  
            # check if this is a tool call
            if hasattr(message, "tool_calls") and message.tool_calls:
                tool_call = message.tool_calls[0]
                output += f"🔧 **Calling tool:** `{tool_call['name']}` (**Args**: `{tool_call['args']}`)\n\n"
                return output

            # check if this is a final answer
            elif hasattr(message, "content") and message.content:
                output += f"💡 **Final Answer:**\n\n{message.content}\n"
                return output

        elif "tools" in chunk:
            tools_data = chunk["tools"]
            messages = tools_data.get("messages", [])
            errors = tools_data.get("errors", [])
            
            if errors:
                error = errors[0]
                if isinstance(error, dict):
                    error_msg = error.get("error", str(error))
                    tool_name = error.get("tool", "unknown")
                    output += f"⚠️ **{tool_name}** encountered an issue: `{error_msg}`\n\n"
                else:
                    output += f"❌ **Tool execution failed:** {error}\n\n"

            if messages:
                tool_message = messages[0]
                tool_name = tool_message.name if hasattr(tool_message, "name") else "unknown"
                result = tool_message.content if hasattr(tool_message, "content") else ""
                output += f"✅ **Tool result:** `{tool_name}` → `{result}`\n\n"

                # after a successful tool execution, show next thinking message
                next_iteration = self.last_iteration + 1
                output += ("\n" + self.get_thinking_message(next_iteration))

        return output
    
    def get_thinking_message(self, iteration):
        return f"🤔 **Agent thinking (iteration {iteration})...**\n\n"
