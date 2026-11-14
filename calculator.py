#!/usr/bin/env python3
"""A small, safe arithmetic calculator.

Evaluates arithmetic expressions with a whitelist AST walk instead of eval(),
so arbitrary code cannot run. Supports + - * / // % ** parentheses, unary
signs, the constants pi/e/tau, and a handful of math functions.

Usage:
    calculator.py "2 + 3 * 4"      # one-shot evaluation
    calculator.py                  # interactive REPL (quit/exit to leave)
"""

from __future__ import annotations

import ast
import math
import operator
import sys

# Python 3.11+ caps int -> str conversion at 4300 digits by default. MAX_BITS
# already bounds how large a result can grow, so lift the cap and let
# format_result() render big integers.
if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)

# Longest allowed nesting, so a pathological input can't blow the C stack.
MAX_DEPTH = 50

# Largest integer result we are willing to materialise, in bits (~125 KB).
MAX_BITS = 1_000_000

BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

FUNCTIONS = {
    "abs": abs,
    "round": round,
    "sqrt": math.sqrt,
    "exp": math.exp,
    "log": math.log,
    "log10": math.log10,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "degrees": math.degrees,
    "radians": math.radians,
    "floor": math.floor,
    "ceil": math.ceil,
}

CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}


class CalcError(Exception):
    """A user-facing evaluation error."""


def _eval(node: ast.AST, depth: int = 0):
    if depth > MAX_DEPTH:
        raise CalcError("expression is nested too deeply")

    if isinstance(node, ast.Expression):
        return _eval(node.body, depth + 1)

    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CalcError(f"unsupported literal: {value!r}")
        return value

    if isinstance(node, ast.BinOp):
        op = BIN_OPS.get(type(node.op))
        if op is None:
            raise CalcError(f"unsupported operator: {type(node.op).__name__}")
        left = _eval(node.left, depth + 1)
        right = _eval(node.right, depth + 1)
        if isinstance(node.op, ast.Pow):
            _check_pow_size(left, right)
        try:
            return op(left, right)
        except ZeroDivisionError:
            raise CalcError("division by zero") from None
        except OverflowError:
            raise CalcError("result is too large") from None
        except ValueError as exc:
            raise CalcError(str(exc)) from None

    if isinstance(node, ast.UnaryOp):
        op = UNARY_OPS.get(type(node.op))
        if op is None:
            raise CalcError(f"unsupported operator: {type(node.op).__name__}")
        return op(_eval(node.operand, depth + 1))

    if isinstance(node, ast.Name):
        if node.id in CONSTANTS:
            return CONSTANTS[node.id]
        raise CalcError(f"unknown name: {node.id}")

    if isinstance(node, ast.Call):
        if node.keywords:
            raise CalcError("keyword arguments are not supported")
        if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
            raise CalcError("only the built-in math functions are supported")
        func = FUNCTIONS[node.func.id]
        args = [_eval(arg, depth + 1) for arg in node.args]
        try:
            return func(*args)
        except TypeError:
            raise CalcError(
                f"wrong number of arguments for {node.func.id}()"
            ) from None
        except ZeroDivisionError:
            raise CalcError("division by zero") from None
        except OverflowError:
            raise CalcError("result is too large") from None
        except ValueError as exc:
            raise CalcError(str(exc)) from None

    raise CalcError(f"unsupported syntax: {type(node).__name__}")


def _check_pow_size(base, exponent) -> None:
    """Refuse integer powers whose result cannot be materialised.

    ``10 ** 10 ** 10`` parses as ``10 ** (10 ** 10)``: the inner power is
    cheap, but the outer one would try to build a 10-billion-digit integer.
    Checking the operands before calling ``pow`` keeps that from happening.
    """
    if isinstance(base, int) and isinstance(exponent, int) and exponent > 0:
        if base in (0, 1, -1):
            return
        bits = exponent * base.bit_length()
        if bits > MAX_BITS:
            raise CalcError(
                f"result is too large (about {bits:,} bits); limit is {MAX_BITS:,}"
            )


def evaluate(expression: str) -> int | float:
    """Evaluate an arithmetic expression and return a number."""
    text = expression.strip()
    if not text:
        raise CalcError("empty expression")

    # Calculator convention: ^ means exponent, not bitwise XOR.
    text = text.replace("^", "**")

    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise CalcError(f"syntax error: {exc.msg}") from None

    return _eval(tree)


def format_result(value) -> str:
    """Render a result without a trailing .0 on whole numbers."""
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer() and abs(value) < 1e16:
            return str(int(value))
        return repr(value)
    return str(value)


HELP = """commands: quit | exit | help
operators: + - * / // % ** (or ^)   functions: abs round sqrt exp log log10
          sin cos tan asin acos atan sinh cosh tanh degrees radians floor ceil
constants: pi e tau
example:  (2 + 3) * 4 - sqrt(16)"""


def repl(stream=None) -> int:
    stream = stream or sys.stdin
    print("MiniCalc — type 'help' for syntax, 'quit' to exit.")
    while True:
        try:
            line = input("calc> ")
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            continue
        word = line.strip().lower()
        if word in ("quit", "exit", "q"):
            return 0
        if word == "help":
            print(HELP)
            continue
        if not word:
            continue
        try:
            print(format_result(evaluate(line)))
        except CalcError as exc:
            print(f"error: {exc}")


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        try:
            print(format_result(evaluate(" ".join(argv[1:]))))
            return 0
        except CalcError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    return repl()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
