"""Safe expression evaluator — recursive descent parser.

Supports conditions like:
    "color == 'red' AND size_mm > 50"
    "defect_detected == true OR confidence < 0.3"
    "(color == 'blue' OR color == 'green') AND size_mm >= 30"

No eval(), no exec(). Only safe comparisons and boolean logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

class TokenType(Enum):
    IDENTIFIER = auto()
    STRING = auto()
    NUMBER = auto()
    BOOL = auto()
    AND = auto()
    OR = auto()
    EQ = auto()
    NEQ = auto()
    GT = auto()
    GTE = auto()
    LT = auto()
    LTE = auto()
    LPAREN = auto()
    RPAREN = auto()
    EOF = auto()


@dataclass
class Token:
    type: TokenType
    value: Any


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, TokenType | None]] = [
    (r"\s+", None),
    (r"AND\b", TokenType.AND),
    (r"OR\b", TokenType.OR),
    (r"true\b", TokenType.BOOL),
    (r"false\b", TokenType.BOOL),
    (r"!=", TokenType.NEQ),
    (r"==", TokenType.EQ),
    (r">=", TokenType.GTE),
    (r"<=", TokenType.LTE),
    (r">", TokenType.GT),
    (r"<", TokenType.LT),
    (r"\(", TokenType.LPAREN),
    (r"\)", TokenType.RPAREN),
    (r"'[^']*'", TokenType.STRING),
    (r'"[^"]*"', TokenType.STRING),
    (r"-?\d+(\.\d+)?", TokenType.NUMBER),
    (r"[a-zA-Z_]\w*", TokenType.IDENTIFIER),
]


def tokenize(expression: str) -> list[Token]:
    tokens: list[Token] = []
    pos = 0
    while pos < len(expression):
        matched = False
        for pattern, ttype in _PATTERNS:
            m = re.match(pattern, expression[pos:])
            if m:
                raw = m.group(0)
                if ttype is not None:
                    if ttype == TokenType.STRING:
                        tokens.append(Token(ttype, raw[1:-1]))
                    elif ttype == TokenType.NUMBER:
                        tokens.append(Token(ttype, float(raw)))
                    elif ttype == TokenType.BOOL:
                        tokens.append(Token(ttype, raw == "true"))
                    else:
                        tokens.append(Token(ttype, raw))
                pos += len(raw)
                matched = True
                break
        if not matched:
            raise SyntaxError(f"Unexpected character at position {pos}: '{expression[pos]}'")
    tokens.append(Token(TokenType.EOF, None))
    return tokens


# ---------------------------------------------------------------------------
# AST Nodes
# ---------------------------------------------------------------------------

@dataclass
class ASTNode:
    pass


@dataclass
class LiteralNode(ASTNode):
    value: Any


@dataclass
class IdentifierNode(ASTNode):
    name: str


@dataclass
class ComparisonNode(ASTNode):
    left: ASTNode
    op: TokenType
    right: ASTNode


@dataclass
class BinaryOpNode(ASTNode):
    left: ASTNode
    op: TokenType
    right: ASTNode


# ---------------------------------------------------------------------------
# Parser (recursive descent)
# ---------------------------------------------------------------------------

class Parser:
    def __init__(self, tokens: list[Token]):
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        t = self._tokens[self._pos]
        self._pos += 1
        return t

    def _expect(self, ttype: TokenType) -> Token:
        t = self._advance()
        if t.type != ttype:
            raise SyntaxError(f"Expected {ttype}, got {t.type}")
        return t

    def parse(self) -> ASTNode:
        node = self._or_expr()
        if self._peek().type != TokenType.EOF:
            raise SyntaxError(f"Unexpected token: {self._peek()}")
        return node

    def _or_expr(self) -> ASTNode:
        left = self._and_expr()
        while self._peek().type == TokenType.OR:
            self._advance()
            right = self._and_expr()
            left = BinaryOpNode(left, TokenType.OR, right)
        return left

    def _and_expr(self) -> ASTNode:
        left = self._comparison()
        while self._peek().type == TokenType.AND:
            self._advance()
            right = self._comparison()
            left = BinaryOpNode(left, TokenType.AND, right)
        return left

    def _comparison(self) -> ASTNode:
        if self._peek().type == TokenType.LPAREN:
            self._advance()
            node = self._or_expr()
            self._expect(TokenType.RPAREN)
            return node

        left = self._atom()
        if self._peek().type in (
            TokenType.EQ, TokenType.NEQ,
            TokenType.GT, TokenType.GTE,
            TokenType.LT, TokenType.LTE,
        ):
            op = self._advance().type
            right = self._atom()
            return ComparisonNode(left, op, right)
        return left

    def _atom(self) -> ASTNode:
        t = self._peek()
        if t.type == TokenType.IDENTIFIER:
            self._advance()
            return IdentifierNode(t.value)
        if t.type in (TokenType.STRING, TokenType.NUMBER, TokenType.BOOL):
            self._advance()
            return LiteralNode(t.value)
        if t.type == TokenType.LPAREN:
            self._advance()
            node = self._or_expr()
            self._expect(TokenType.RPAREN)
            return node
        raise SyntaxError(f"Unexpected token: {t}")


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

_CMP_OPS = {
    TokenType.EQ: lambda a, b: a == b,
    TokenType.NEQ: lambda a, b: a != b,
    TokenType.GT: lambda a, b: float(a) > float(b),
    TokenType.GTE: lambda a, b: float(a) >= float(b),
    TokenType.LT: lambda a, b: float(a) < float(b),
    TokenType.LTE: lambda a, b: float(a) <= float(b),
}


def evaluate(node: ASTNode, context: dict[str, Any]) -> Any:
    if isinstance(node, LiteralNode):
        return node.value
    if isinstance(node, IdentifierNode):
        return context.get(node.name)
    if isinstance(node, ComparisonNode):
        left = evaluate(node.left, context)
        right = evaluate(node.right, context)
        return _CMP_OPS[node.op](left, right)
    if isinstance(node, BinaryOpNode):
        left = evaluate(node.left, context)
        if node.op == TokenType.AND:
            return bool(left) and bool(evaluate(node.right, context))
        if node.op == TokenType.OR:
            return bool(left) or bool(evaluate(node.right, context))
    raise ValueError(f"Unknown node type: {type(node)}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_condition(condition: str, context: dict[str, Any]) -> bool:
    """Safely evaluate a policy condition string against a context dict."""
    tokens = tokenize(condition)
    ast = Parser(tokens).parse()
    return bool(evaluate(ast, context))
