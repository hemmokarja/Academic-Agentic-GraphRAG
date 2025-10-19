import json
import time


class StreamHandler:
    def __init__(
        self,
        model_name,
        show_token_usage=True
    ):
        self.show_token_usage = show_token_usage

        self.last_iteration = 0
        self.pending_tool_calls = set()
        self.iteration_start_time = {}
        self.start_time = time.time()

        with open("src/ui/api_pricing.json", "r") as f:
            model_to_pricing = json.loads(f.read())

        self.pricing = model_to_pricing.get(model_name)

    def _format_json(self, data):
        """Format JSON with proper escaping for HTML display"""
        json_str = json.dumps(data, indent=2)
        json_str = json_str.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return f"<pre style='background-color: #f8f9fa; padding: 12px; border-radius: 4px; margin: 8px 0 0 0; overflow-x: auto; font-size: 13px; line-height: 1.5; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;'><code>{json_str}</code></pre>"

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
                f"<div style='padding: 16px 0;'>"
                f"<div style='font-size: 13px; color: #6b7280; margin-bottom: 8px;'>Tool Call</div>"
                f"<div style='font-size: 14px; color: #111827; margin-bottom: 4px;'><code style='background-color: #f3f4f6; padding: 3px 7px; border-radius: 4px; font-size: 13px;'>{tool_name}</code></div>"
                f"<div style='font-size: 12px; color: #9ca3af; margin-bottom: 8px;'>{tool_id}</div>"
                f"<div style='font-size: 13px; color: #6b7280; margin-bottom: 4px;'>Arguments</div>"
                f"{self._format_json(tool_args)}"
                f"</div>\n"
                f"<hr style='border: none; border-top: 1px solid #e5e7eb; margin: 0;'>\n\n"
            )

        # several simultaneous calls
        else:
            output = (
                f"<div style='padding: 16px 0;'>"
                f"<div style='font-size: 13px; color: #6b7280; margin-bottom: 12px;'>Calling {len(message.tool_calls)} Tools</div>"
            )

            for i, tool_call in enumerate(message.tool_calls):
                tool_id, tool_name, tool_args = _extract_details(tool_call)
                self.pending_tool_calls.add(tool_id)
                output += (
                    f"<div style='margin-bottom: {'16px' if i < len(message.tool_calls) - 1 else '0'};'>"
                    f"<div style='font-size: 14px; color: #111827; margin-bottom: 4px;'>{i+1}. <code style='background-color: #f3f4f6; padding: 3px 7px; border-radius: 4px; font-size: 13px;'>{tool_name}</code></div>"
                    f"<div style='font-size: 12px; color: #9ca3af; margin-bottom: 8px;'>{tool_id}</div>"
                    f"{self._format_json(tool_args)}"
                    f"</div>"
                )
            
            output += "</div>\n"
            output += "<hr style='border: none; border-top: 1px solid #e5e7eb; margin: 0;'>\n\n"
            return output

    def _format_token_usage(self, token_usage, elapsed):
        input_tokens = token_usage["input_tokens"]
        output_tokens = token_usage["output_tokens"]
        total_tokens = token_usage["total_tokens"]

        if self.pricing:
            input_price = self.pricing["input"] * (input_tokens / 1e6)
            output_price = self.pricing["output"] * (output_tokens / 1e6)
            total_price = input_price + output_price
            
            return (
                f"<div style='font-size: 12px; color: #9ca3af; margin-top: 12px;'>"
                f"This response: {input_tokens:,}↑ + {output_tokens:,}↓ "
                f"= {total_tokens:,} tokens • ${total_price:.4f} • {elapsed:.2f}s"
                f"</div>\n"
            )
        else:
            return (
                f"<div style='font-size: 12px; color: #9ca3af; margin-top: 12px;'>"
                f"This response: {input_tokens:,}↑ + {output_tokens:,}↓ "
                f"= {total_tokens:,} tokens • {elapsed:.2f}s"
                f"</div>\n"
            )

    def _handle_agent_chunk(self, chunk):
        agent_data = chunk["agent"]
        iteration = agent_data["iteration_count"]
        messages = agent_data["messages"]
        token_usage = agent_data["token_usage"]

        if not messages:
            return ""

        self.last_iteration = iteration

        message = messages[0]

        if hasattr(message, "tool_calls") and message.tool_calls:
            return self._format_agent_tool_calls(message)

        elif hasattr(message, "content") and message.content:
            # Calculate elapsed time
            elapsed = time.time() - self.start_time
            
            output = (
                f"<div style='padding: 16px 0;'>"
                f"<div style='font-size: 13px; color: #10b981; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px;'>Final Answer</div>"
                f"<div style='font-size: 15px; color: #111827; line-height: 1.6;'>{message.content}</div>"
                f"</div>\n"
            )
            
            if self.show_token_usage:
                output += self._format_token_usage(token_usage, elapsed)
            
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
                    f"<div style='padding: 16px 0;'>"
                    f"<div style='font-size: 13px; color: #dc2626; margin-bottom: 8px;'>Tool Error</div>"
                    f"<div style='font-size: 14px; color: #111827; margin-bottom: 4px;'><code style='background-color: #f3f4f6; padding: 3px 7px; border-radius: 4px; font-size: 13px;'>{tool_name}</code></div>"
                    f"<div style='font-size: 12px; color: #9ca3af; margin-bottom: 8px;'>{tool_id}</div>"
                    f"<div style='font-size: 13px; color: #dc2626;'>{error_msg}</div>"
                    f"</div>\n"
                    f"<hr style='border: none; border-top: 1px solid #e5e7eb; margin: 0;'>\n\n"
                )

                self.pending_tool_calls.discard(tool_id)
            else:
                output += (
                    f"<div style='padding: 16px 0;'>"
                    f"<div style='font-size: 13px; color: #dc2626; margin-bottom: 8px;'>Execution Failed</div>"
                    f"<div style='font-size: 13px; color: #dc2626;'>{error}</div>"
                    f"</div>\n"
                    f"<hr style='border: none; border-top: 1px solid #e5e7eb; margin: 0;'>\n\n"
                )
        return output

    def _format_tool_messages(self, messages):
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

            # Format result as JSON if possible, otherwise as text
            try:
                result_obj = json.loads(result) if isinstance(result, str) else result
                formatted_result = self._format_json(result_obj)
            except:
                # If not JSON, escape and display as text
                result_escaped = str(result).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                formatted_result = f"<pre style='background-color: #f8f9fa; padding: 12px; border-radius: 4px; margin: 8px 0 0 0; overflow-x: auto; font-size: 13px; line-height: 1.5; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; white-space: pre-wrap; word-wrap: break-word;'><code>{result_escaped}</code></pre>"

            output += (
                f"<div style='padding: 16px 0;'>"
                f"<div style='font-size: 13px; color: #6b7280; margin-bottom: 8px;'>Tool Result</div>"
                f"<div style='font-size: 14px; color: #111827; margin-bottom: 4px;'><code style='background-color: #f3f4f6; padding: 3px 7px; border-radius: 4px; font-size: 13px;'>{tool_name}</code></div>"
                f"<div style='font-size: 12px; color: #9ca3af; margin-bottom: 12px;'>{tool_id}</div>"
                f"<details style='cursor: pointer;'>"
                f"<summary style='font-size: 13px; color: #6b7280; cursor: pointer; user-select: none;'>View result</summary>"
                f"{formatted_result}"
                f"</details>"
                f"</div>\n"
                f"<hr style='border: none; border-top: 1px solid #e5e7eb; margin: 0;'>\n\n"
            )

            self.pending_tool_calls.discard(tool_id)

        # after all tool executions complete, show next thinking message
        if not self.pending_tool_calls:
            next_iteration = self.last_iteration + 1
            output += self.get_thinking_message(next_iteration)

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
        # Record start time for this iteration
        self.iteration_start_time[iteration] = time.time()
        
        return (
            f"<div style='padding: 16px 0;'>"
            f"<div style='font-size: 13px; color: #d97706;'>Agent Thinking (Iteration {iteration})</div>"
            f"</div>\n"
            f"<hr style='border: none; border-top: 1px solid #e5e7eb; margin: 0;'>\n\n"
        )
    