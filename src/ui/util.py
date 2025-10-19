import os 
import logging

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


def _is_openai(model_name):
    return model_name.startswith("gpt")


def _is_anthropic(model_name):
    return model_name.startswith("claude")


def _get_default_model(model_name):
    if _is_openai(model_name):
        return "gpt-4.1"
    if _is_anthropic(model_name):
        return "claude-sonnet-4-5"
    else:
        raise RuntimeError(f"Unknown model {model_name}")


def get_system_message(model_name):
    path = f"config/system_prompts/{model_name}.md"
    if not os.path.isfile(path):
        original_path = path
        default = _get_default_model(model_name)
        path = f"config/system_prompts/{default}.md"
        logger.warning(
            f"Could not locate system message for model {model_name} from "
            f"{original_path}, defauling to {path}"
        )
    with open(path, "r") as f:
        system_message = f.read()
    return system_message


def _validate_env_variable(env_var_name):
    value = os.getenv(env_var_name)
    if not value:
        raise EnvironmentError(f"Environment variable '{env_var_name}' is not set.")


def get_llm(model_name):
    if _is_openai(model_name):
        _validate_env_variable("OPENAI_API_KEY")
        return ChatOpenAI(model=model_name)
    elif _is_anthropic(model_name):
        _validate_env_variable("ANTHROPIC_API_KEY")
        return ChatAnthropic(model=model_name)
    else:
        raise RuntimeError(f"Unknown model {model_name}")
