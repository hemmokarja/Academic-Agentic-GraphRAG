import ast
import json
import time


def _escape_string(string):
    return (
        string
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _extract_tool_details(tool_call):
    tool_id = tool_call.get("id", "unknown")
    tool_name = tool_call.get("name", "unknown")
    tool_args = tool_call.get("args", {})
    return tool_id, tool_name, tool_args


def _extract_text_from_content(content):
    """
    Extract text content from message.content (handles both string and list formats).
    """
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get('text', ''))
            elif isinstance(block, str):
                text_parts.append(block)
        return " ".join(text_parts).strip()

    return ""


class StreamHandler:
    def __init__(self, model_name):
        self.last_iteration = 0
        self.pending_tool_calls = set()
        self.start_time = time.time()

        with open("src/ui/api_pricing.json", "r") as f:
            model_to_pricing = json.loads(f.read())

        self.pricing = model_to_pricing.get(model_name)

    def _format_json(self, data, wrap=False):
        if isinstance(data, (dict, list)):
            json_str = json.dumps(data, indent=2)
        else:
            json_str = str(data)

        json_str = _escape_string(json_str)
        wrap_class = "wrap" if wrap else ""
        return (
            f"<pre class='code-block {wrap_class} font-mono font-sm my-3'>"
            f"<code>{json_str}</code></pre>"
        )

    def _format_reasoning(self, reasoning_text):
        escaped_text = _escape_string(reasoning_text)
        return (
            f"<div class='react-block'>"
            f"<div class='font-sm text-secondary'>Reasoning</div>"
            f"<div class='font-md text-secondary mt-2' style='line-height: 1.6;'>{escaped_text}</div>"
            f"</div><hr class='react-hr'>"
        )

    def _format_single_tool_call(self, message):
        # Extract any reasoning text from content
        reasoning_text = _extract_text_from_content(message.content)
        if reasoning_text:
            reasoning_output = self._format_reasoning(reasoning_text)
        else:
            reasoning_output = ""

        tool_call = message.tool_calls[0]
        tool_id, tool_name, tool_args = _extract_tool_details(tool_call)
        self.pending_tool_calls.add(tool_id)
        formatted_tool_args = self._format_json(tool_args)
        return (
            f"{reasoning_output}"
            f"<div class='react-block'>"
            f"<div class='font-sm text-secondary'>Tool Call</div>"
            f"<div class='font-md text-primary mt-2'><code>{tool_name}</code></div>"
            f"<div class='font-xs text-muted my-3'>{tool_id}</div>"
            f"<div class='font-sm text-secondary mb-1'>Arguments</div>"
            f"{formatted_tool_args}"
            f"</div><hr class='react-hr'>"
        )

    def _format_multiple_tool_calls(self, message):
        # Extract any reasoning text from content
        reasoning_text = _extract_text_from_content(message.content)
        reasoning_output = self._format_reasoning(reasoning_text)

        output = (
            f"{reasoning_output}"
            f"<div class='react-block'>"
            f"<div class='font-sm text-secondary mb-3'>"
            f"Calling {len(message.tool_calls)} Tools</div>"
        )
        for i, tool_call in enumerate(message.tool_calls):
            tool_id, tool_name, tool_args = _extract_tool_details(tool_call)
            self.pending_tool_calls.add(tool_id)
            formatted_tool_args = self._format_json(tool_args)
            margin_class = "mb-3" if i < len(message.tool_calls) - 1 else ""
            output += (
                f"<div class='{margin_class}'>"
                f"<div class='font-md text-primary'>{i+1}. <code>{tool_name}</code></div>"
                f"<div class='font-xs text-muted my-3'>{tool_id}</div>"
                f"{formatted_tool_args}</div>"
            )
        output += "</div><hr class='react-hr'>"
        return output

    def _format_agent_tool_calls(self, message):
        if len(message.tool_calls) == 1:
            return self._format_single_tool_call(message)
        return self._format_multiple_tool_calls(message)

    def _format_token_usage(self, token_usage, elapsed):
        input_tokens = token_usage["input_tokens"]
        output_tokens = token_usage["output_tokens"]
        total_tokens = token_usage["total_tokens"]

        if self.pricing:
            input_price = self.pricing["input"] * (input_tokens / 1e6)
            output_price = self.pricing["output"] * (output_tokens / 1e6)
            total_price = input_price + output_price
            return (
                f"<div class='font-sm text-muted italic'>"
                f"This response: {input_tokens:,}↑ + {output_tokens:,}↓ = {total_tokens:,} tokens • "
                f"${total_price:.4f} • {elapsed:.2f}s"
                f"</div>"
            )
        return (
            f"<div class='font-sm text-muted italic'>"
            f"This response: {input_tokens:,}↑ + {output_tokens:,}↓ = {total_tokens:,} tokens • "
            f"{elapsed:.2f}s</div>"
        )

    def _format_final_answer(self, message, token_usage):
        elapsed = time.time() - self.start_time
        content_text = _extract_text_from_content(message.content)
        escaped_content = _escape_string(content_text)

        output = (
            f"<div class='react-block'>"
            f"<div class='font-lg text-secondary mb-3'>💡 Final Answer</div>"
            f"<div class='font-lg text-primary' style='line-height: 1.6;'>{escaped_content}</div>"
            f"</div>"
        )

        # in error situations may not exist
        if token_usage:
            output += self._format_token_usage(token_usage, elapsed)

        return output

    def _handle_agent_chunk(self, chunk):
        agent_data = chunk["agent"]
        messages = agent_data["messages"]

        if not messages:
            return ""

        self.last_iteration = agent_data["iteration_count"]
        message = messages[0]

        if hasattr(message, "tool_calls") and message.tool_calls:
            return self._format_agent_tool_calls(message)

        elif hasattr(message, "content") and message.content:
            return self._format_final_answer(message, agent_data.get("token_usage"))

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
                    f"<div class='font-sm text-error'>Tool Error</div>"
                    f"<div class='font-md text-primary my-1'><code>{tool_name}</code></div>"
                    f"<div class='font-xs text-muted mb-2'>{tool_id}</div>"
                    f"<div class='font-sm text-error'>{error_msg}</div>"
                    f"</div><hr class='react-hr'>"
                )
                self.pending_tool_calls.discard(tool_id)
            else:
                output += (
                    f"<div class='react-block'>"
                    f"<div class='font-sm text-error'>Execution Failed</div>"
                    f"<div class='font-sm text-error'>{error}</div>"
                    f"</div><hr class='react-hr'>"
                )
        return output

    def _format_tool_result(self, result):
        try:
            parsed_result = ast.literal_eval(result)
            return self._format_json(parsed_result)
        except (ValueError, TypeError, SyntaxError):
            return self._format_json(result, wrap=True)

    def _format_tool_messages(self, messages):
        output = ""
        for tool_message in messages:
            tool_id = tool_message.tool_call_id
            tool_name = tool_message.name
            result = tool_message.content

            formatted_result = self._format_tool_result(result)
            output += (
                f"<div class='react-block'>"
                f"<div class='font-sm text-secondary'>Tool Result</div>"
                f"<div class='font-md text-primary my-2'><code>{tool_name}</code></div>"
                f"<div class='font-xs text-muted mb-2'>{tool_id}</div>"
                f"<details>"
                f"<summary class='font-sm text-secondary'>View result</summary>"
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
            f"<div class='font-lg text-secondary'>💭 Agent Thinking... (iteration {iteration})</div>"
            f"</div><hr class='react-hr'>"
        )
