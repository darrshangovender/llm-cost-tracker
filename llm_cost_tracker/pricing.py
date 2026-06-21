"""Per-million-token USD pricing for the LLM models I touch day-to-day.

Update this quarterly or override at runtime with set_price().
Numbers are list price; bulk / enterprise discounts not modeled.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input: float   # USD per 1M input (prompt) tokens
    output: float  # USD per 1M output (completion) tokens


# Built-in price table — current as of Q2 2026.
# These are deliberately mutable so callers can update them in long-running services.
PRICES: dict[str, Price] = {
    # Anthropic Claude
    "claude-sonnet-4-5":      Price(input=3.00, output=15.00),
    "claude-sonnet-4-6":      Price(input=3.00, output=15.00),
    "claude-sonnet-4-7":      Price(input=3.00, output=15.00),
    "claude-haiku-4-5":       Price(input=0.80, output=4.00),
    "claude-opus-4-7":        Price(input=15.00, output=75.00),
    "claude-opus-4-8":        Price(input=15.00, output=75.00),
    "claude-fable-5":         Price(input=8.00, output=40.00),

    # OpenAI
    "gpt-4o":                 Price(input=2.50, output=10.00),
    "gpt-4o-mini":            Price(input=0.15, output=0.60),
    "o1":                     Price(input=15.00, output=60.00),
    "o1-mini":                Price(input=3.00, output=12.00),
    "text-embedding-3-small": Price(input=0.02, output=0.0),
    "text-embedding-3-large": Price(input=0.13, output=0.0),
}


def price_for(model: str) -> Price | None:
    """Lookup price for a model. Returns None if unknown.

    We deliberately do NOT fall back to a default — silently mispricing an
    unknown model leads to silent under-reporting of cost. Caller should
    register the model via set_price() or accept None.
    """
    return PRICES.get(model)


def set_price(model: str, *, input: float, output: float) -> None:
    """Register or override a price entry. USD per 1M tokens."""
    PRICES[model] = Price(input=input, output=output)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Compute USD cost for one call. None if model is unknown."""
    p = price_for(model)
    if p is None:
        return None
    return (input_tokens / 1_000_000) * p.input + (output_tokens / 1_000_000) * p.output