"""
Deep Check: Math Verifier
Deterministic mathematical verification using sympy.

Given a claim containing a mathematical statement,
extracts the expression, evaluates it, and compares
against the claimed result.

No LLM involved — fully deterministic, zero cost.
"""
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger("controlplane.math_verifier")

# Try to import sympy — graceful fallback if not installed
try:
    import sympy
    from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication
    SYMPY_AVAILABLE = True
except ImportError:
    SYMPY_AVAILABLE = False
    logger.warning("sympy not installed — math verification will use basic eval fallback")


# Patterns to extract "X = Y" or "X is Y" style math claims
MATH_PATTERNS = [
    # "17 × 29 = 493" or "17 * 29 = 493"
    r"([\d\s\+\-\*×÷/\(\)\.\^]+)\s*[=≈]\s*([\d\.,]+)",
    # "the answer is 493" preceded by math expression
    r"([\d\s\+\-\*×÷/\(\)\.\^]+)\s+(?:is|equals|gives|results?\s+in)\s+([\d\.,]+)",
    # "15% of 240 is 36"
    r"(\d+(?:\.\d+)?)\s*%\s*(?:of)\s*(\d+(?:\.\d+)?)\s*(?:is|=|equals)\s*([\d\.,]+)",
]


def verify_math_claim(claim: str) -> Dict[str, Any]:
    """
    Extract and verify a mathematical claim.

    Returns:
        {
            status: "SUPPORTED" | "CONTRADICTED" | "NOT_VERIFIABLE",
            claimed_result: str | None,
            computed_result: str | None,
            expression: str | None,
            method: "sympy" | "basic_eval" | "none",
            confidence: float,
        }
    """
    # Try percentage pattern first (most specific)
    pct_match = re.search(MATH_PATTERNS[2], claim)
    if pct_match:
        pct = float(pct_match.group(1))
        base = float(pct_match.group(2))
        claimed = _clean_number(pct_match.group(3))
        computed = (pct / 100) * base

        matches = abs(computed - claimed) < 0.01
        status = "SUPPORTED" if matches else "CONTRADICTED"

        logger.info(
            f"Math verify (percentage): {pct}% of {base} = {computed} "
            f"(claimed: {claimed}) → {status}"
        )

        return {
            "status": status,
            "claimed_result": str(claimed),
            "computed_result": str(computed),
            "expression": f"{pct}% of {base}",
            "method": "basic_eval",
            "confidence": 0.99,
        }

    # Try general "expression = result" patterns
    for pattern in MATH_PATTERNS[:2]:
        match = re.search(pattern, claim)
        if match:
            expr_str = match.group(1).strip()
            claimed_str = match.group(2).strip()

            # Normalize math symbols
            expr_normalized = _normalize_expression(expr_str)
            claimed = _clean_number(claimed_str)

            if claimed is None:
                continue

            # Evaluate
            computed = _evaluate(expr_normalized)
            if computed is None:
                continue

            matches = abs(computed - claimed) < 0.01
            status = "SUPPORTED" if matches else "CONTRADICTED"

            logger.info(
                f"Math verify: {expr_str} = {computed} "
                f"(claimed: {claimed}) → {status}"
            )

            return {
                "status": status,
                "claimed_result": str(claimed),
                "computed_result": str(computed),
                "expression": expr_str,
                "method": "sympy" if SYMPY_AVAILABLE else "basic_eval",
                "confidence": 0.99,
            }

    # Could not extract a verifiable math expression
    return {
        "status": "NOT_VERIFIABLE",
        "claimed_result": None,
        "computed_result": None,
        "expression": None,
        "method": "none",
        "confidence": 0.0,
    }


def _normalize_expression(expr: str) -> str:
    """Normalize unicode math symbols to Python operators."""
    expr = expr.replace("×", "*").replace("÷", "/")
    expr = expr.replace("^", "**")
    expr = re.sub(r"\s+", " ", expr).strip()
    # Remove trailing operators
    expr = re.sub(r"[\+\-\*/ ]+$", "", expr)
    return expr


def _clean_number(s: str) -> Optional[float]:
    """Parse a number string, handling commas and whitespace."""
    try:
        cleaned = s.replace(",", "").replace(" ", "").strip()
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


def _evaluate(expr: str) -> Optional[float]:
    """Evaluate a math expression safely."""
    if SYMPY_AVAILABLE:
        return _eval_sympy(expr)
    return _eval_basic(expr)


def _eval_sympy(expr: str) -> Optional[float]:
    """Evaluate using sympy (safe, handles complex expressions)."""
    try:
        transformations = standard_transformations + (implicit_multiplication,)
        result = parse_expr(expr, transformations=transformations)
        return float(result.evalf())
    except Exception as e:
        logger.debug(f"sympy eval failed for '{expr}': {e}")
        return _eval_basic(expr)


def _eval_basic(expr: str) -> Optional[float]:
    """
    Basic eval fallback — restricted to safe math operations.
    Only allows digits, operators, parentheses, and whitespace.
    """
    # Strict allowlist: only math characters
    if not re.match(r'^[\d\s\+\-\*/\.\(\)]+$', expr):
        logger.debug(f"Basic eval rejected unsafe expression: '{expr}'")
        return None

    try:
        result = eval(expr, {"__builtins__": {}}, {})
        return float(result)
    except Exception as e:
        logger.debug(f"Basic eval failed for '{expr}': {e}")
        return None
