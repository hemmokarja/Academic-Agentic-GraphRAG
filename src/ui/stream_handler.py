import ast
import json
import time


class StreamHandler:
    def __init__(self, model_name):
        self.last_iteration = 0
        self.pending_tool_calls = set()
        self.start_time = time.time()

        with open("src/ui/api_pricing.json", "r") as f:
            model_to_pricing = json.loads(f.read())

        self.pricing = model_to_pricing.get(model_name)

    def _format_agent_tool_calls(self, message):

        def _extract_details(tool_call):
            tool_id = tool_call.get("id", "unknown")
            tool_name = tool_call.get("name", "unknown")
            tool_args = tool_call.get("args", {})
            return tool_id, tool_name, tool_args

        # single tool call
        if len(message.tool_calls) == 1:
            tool_call = message.tool_calls[0]
            tool_id, tool_name, tool_args = _extract_details(tool_call)
            self.pending_tool_calls.add(tool_id)
            formatted_tool_args = self._format_json(tool_args)
            return (
                f"<div class='react-block'>"
                f"<div style='font-size: 13px; color: #6b7280;'>Tool Call</div>"
                f"<div style='font-size: 14px; color: #111827; margin-top: 6px;'>"
                f"<code>{tool_name}</code></div>"
                f"<div style='font-size: 12px; color: #9ca3af; margin: 4px 0 8px 0;'>{tool_id}</div>"
                f"<div style='font-size: 13px; color: #6b7280; margin-bottom: 4px;'>Arguments</div>"
                f"{formatted_tool_args}"
                f"</div><hr class='react-hr'>"
            )

        # multiple simultaneous calls
        output = (
            f"<div class='react-block'>"
            f"<div style='font-size: 13px; color: #6b7280; margin-bottom: 8px;'>"
            f"Calling {len(message.tool_calls)} Tools</div>"
        )
        for i, tool_call in enumerate(message.tool_calls):
            tool_id, tool_name, tool_args = _extract_details(tool_call)
            self.pending_tool_calls.add(tool_id)
            formatted_tool_args = self._format_json(tool_args)
            output += (
                f"<div style='margin-bottom: {'8px' if i < len(message.tool_calls) - 1 else '0'};'>"
                f"<div style='font-size: 14px; color: #111827;'>"
                f"{i+1}. <code>{tool_name}</code></div>"
                f"<div style='font-size: 12px; color: #9ca3af; margin: 4px 0 8px 0;'>{tool_id}</div>"
                f"{formatted_tool_args}"
                f"</div>"
            )
        output += "</div><hr class='react-hr'>"
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
                f"<div style='font-size: 13px; color: #9ca3af; font-style: italic;'>"
                f"This response: {input_tokens:,}↑ + {output_tokens:,}↓ = {total_tokens:,} tokens • "
                f"${total_price:.4f} • {elapsed:.2f}s"
                f"</div>"
            )
        return (
            f"<div style='font-size: 13px; color: #9ca3af; font-style: italic;'>"
            f"This response: {input_tokens:,}↑ + {output_tokens:,}↓ = {total_tokens:,} tokens • "
            f"{elapsed:.2f}s</div>"
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
            elapsed = time.time() - self.start_time
            output = (
                f"<div class='react-block'>"
                f"<div style='font-size: 16px; color: #6b7280; margin-bottom: 10px;'>💡 Final Answer</div>"
                f"<div style='font-size: 16px; color: #111827; line-height: 1.6;'>{message.content}</div>"
                f"</div>"
            )
            output += self._format_token_usage(token_usage, elapsed)
            return output

        raise RuntimeError("Agent message missing tool_calls and content")

    def _format_tool_errors(self, errors):
        output = ""
        for error in errors:
            if isinstance(error, dict):
                error_msg = error.get("error", str(error))
                tool_name = error.get("tool", "unknown")
                tool_id = error.get("tool_call_id", "unknown")
                output += (
                    f"<div class='react-block'>"
                    f"<div style='font-size: 13px; color: #dc2626;'>Tool Error</div>"
                    f"<div style='font-size: 14px; color: #111827; margin: 4px 0;'>"
                    f"<code>{tool_name}</code></div>"
                    f"<div style='font-size: 12px; color: #9ca3af; margin-bottom: 6px;'>{tool_id}</div>"
                    f"<div style='font-size: 13px; color: #dc2626;'>{error_msg}</div>"
                    f"</div><hr class='react-hr'>"
                )
                self.pending_tool_calls.discard(tool_id)
            else:
                output += (
                    f"<div class='react-block'>"
                    f"<div style='font-size: 13px; color: #dc2626;'>Execution Failed</div>"
                    f"<div style='font-size: 13px; color: #dc2626;'>{error}</div>"
                    f"</div><hr class='react-hr'>"
                )
        return output

    def _format_json(self, data):
        json_str = json.dumps(data, indent=2)
        json_str = (
            json_str
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return (
            "<pre style='background-color: #f8f9fa; padding: 12px; border-radius: 4px; "
            "margin: 8px 0 0 0; overflow-x: auto; font-size: 13px; line-height: 1.5; "
            "font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;'>"
            f"<code>{json_str}</code></pre>"
        )

    def _format_tool_result(self, result):
        # try formatting results to JSON, otherwise treat as string
        try:
            parsed_result = ast.literal_eval(result)
            return self._format_json(parsed_result)

        except (json.JSONDecodeError, TypeError):
            result_escaped = (
                str(result)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            return (
                "<pre style='background-color: #f8f9fa; padding: 12px; border-radius: 4px; "
                "margin: 8px 0 0 0; overflow-x: auto; font-size: 13px; line-height: 1.5; "
                "white-space: pre-wrap; word-wrap: break-word;'>"
                f"<code>{result_escaped}</code></pre>"
            )

    def _format_tool_messages(self, messages):
        output = ""
        for tool_message in messages:
            tool_id = getattr(tool_message, "tool_call_id", "unknown")
            tool_name = getattr(tool_message, "name", "unknown")
            result = getattr(tool_message, "content", "")

            formatted_result = self._format_tool_result(result)
            output += (
                f"<div class='react-block'>"
                f"<div style='font-size: 13px; color: #6b7280;'>Tool Result</div>"
                f"<div style='font-size: 14px; color: #111827; margin: 6px 0;'>"
                f"<code>{tool_name}</code></div>"
                f"<div style='font-size: 12px; color: #9ca3af; margin-bottom: 6px;'>{tool_id}</div>"
                f"<details>"
                f"<summary style='font-size: 13px; color: #6b7280;'>View result</summary>"
                f"{formatted_result}</details></div><hr class='react-hr'>"
            )

            self.pending_tool_calls.discard(tool_id)

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
        raise RuntimeError("Tools chunk missing errors and messages")

    def process_chunk(self, chunk):
        """
        Process a single chunk and return formatted output.
        Returns the text to append to the display.
        """
        if "agent" in chunk:
            return self._handle_agent_chunk(chunk)

        elif "tools" in chunk:
            return self._handle_tools_chunk(chunk)

        raise RuntimeError("Chunk missing agent or tools key")

    def get_thinking_message(self, iteration):
        return (
            f"<div class='react-block' style='padding-bottom: 0;'>"
            f"<div style='font-size: 15px; color: #6b7280;'>💭 Agent Thinking... (iteration {iteration})</div>"
            f"</div><hr class='react-hr'>"
        )
