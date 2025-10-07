# Tools for performing simple arithmetic calculations for testing ReAct agent

import logging
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ArithmeticInput(BaseModel):
    a: float = Field(description="First number")
    b: float = Field(description="Second number")


@tool(args_schema=ArithmeticInput)
def add_numbers(a: float, b: float) -> float:
    """Return the sum of a and b."""
    try:
        result = a + b
        logger.info(f"Adding {a} + {b} = {result}")
        return result
    except Exception as e:
        logger.error(f"Addition failed: {e}")
        raise


@tool(args_schema=ArithmeticInput)
def subtract_numbers(a: float, b: float) -> float:
    """Return the difference a - b."""
    try:
        result = a - b
        logger.info(f"Subtracting {a} - {b} = {result}")
        return result
    except Exception as e:
        logger.error(f"Subtraction failed: {e}")
        raise


@tool(args_schema=ArithmeticInput)
def multiply_numbers(a: float, b: float) -> float:
    """Return the product of a and b."""
    try:
        result = a * b
        logger.info(f"Multiplying {a} * {b} = {result}")
        return result
    except Exception as e:
        logger.error(f"Multiplication failed: {e}")
        raise


@tool(args_schema=ArithmeticInput)
def divide_numbers(a: float, b: float) -> Optional[float]:
    """Return the division a / b. Returns None if division by zero."""
    try:
        if b == 0:
            logger.warning(f"Division by zero: {a} / {b}")
            return None
        result = a / b
        logger.info(f"Dividing {a} / {b} = {result}")
        return result
    except Exception as e:
        logger.error(f"Division failed: {e}")
        raise
