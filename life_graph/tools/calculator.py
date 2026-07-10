"""Safe mathematical expression calculator.

Evaluates arithmetic expressions using AST parsing — no ``eval()`` or
``exec()`` is used anywhere. Only numeric literals and basic arithmetic
operators are permitted.
"""

from __future__ import annotations

import ast
import json
import logging
import operator
from typing import Any

from life_graph.tools.registry import tool

logger = logging.getLogger(__name__)

# ── Supported operators ────────────────────────────────────

_BINARY_OPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS: dict[type, Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


# ── Safe evaluator ─────────────────────────────────────────


def _safe_eval(node: ast.AST) -> int | float:
    """Recursively evaluate an AST node containing only safe operations.

    Supported node types:
        - ``Constant`` (numeric literals)
        - ``UnaryOp`` (``+``, ``-``)
        - ``BinOp`` (``+``, ``-``, ``*``, ``/``, ``//``, ``%``, ``**``)

    Args:
        node: An AST node to evaluate.

    Returns:
        The numeric result of the expression.

    Raises:
        ValueError: If the node contains unsupported operations.
    """
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(
            f"Unsupported constant type: {type(node.value).__name__}"
        )

    if isinstance(node, ast.UnaryOp):
        op_func = _UNARY_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(
                f"Unsupported unary operator: {type(node.op).__name__}"
            )
        return op_func(_safe_eval(node.operand))

    if isinstance(node, ast.BinOp):
        op_func = _BINARY_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(
                f"Unsupported binary operator: {type(node.op).__name__}"
            )
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)

        # Guard against excessively large exponents.
        if isinstance(node.op, ast.Pow):
            if isinstance(right, (int, float)) and abs(right) > 1000:
                raise ValueError(
                    "Exponent too large (max 1000). "
                    "This prevents memory exhaustion."
                )

        return op_func(left, right)

    raise ValueError(
        f"Unsupported expression element: {type(node).__name__}. "
        "Only numeric literals and arithmetic operators are allowed."
    )


# ── Tool registration ─────────────────────────────────────


@tool(
    name="calculator",
    description="Evaluate a mathematical expression safely",
    parameters_schema={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": (
                    "Mathematical expression to evaluate "
                    "(e.g. '2 + 3 * 4')"
                ),
            },
        },
        "required": ["expression"],
    },
)
async def calculator(expression: str) -> str:
    """Safely evaluate a mathematical expression.

    Uses AST parsing to only allow numeric literals and basic arithmetic.
    No ``eval()`` or ``exec()`` is used.

    Args:
        expression: A mathematical expression string.

    Returns:
        JSON string with the expression, result, and result type.
    """
    logger.info("Evaluating expression: %s", expression)

    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        logger.warning("Invalid expression syntax: %s", expression)
        return json.dumps({
            "error": f"Invalid expression syntax: {exc.msg}",
            "expression": expression,
        })

    try:
        result = _safe_eval(tree)
    except ZeroDivisionError:
        logger.warning("Division by zero: %s", expression)
        return json.dumps({
            "error": "Division by zero",
            "expression": expression,
        })
    except ValueError as exc:
        logger.warning("Unsafe expression rejected: %s — %s", expression, exc)
        return json.dumps({
            "error": str(exc),
            "expression": expression,
        })
    except Exception as exc:
        logger.exception("Unexpected calculator error: %s", exc)
        return json.dumps({
            "error": f"Calculation failed: {type(exc).__name__}",
            "expression": expression,
        })

    result_type = "int" if isinstance(result, int) else "float"

    logger.info("Expression result: %s = %s", expression, result)
    return json.dumps({
        "expression": expression,
        "result": result,
        "type": result_type,
    })
