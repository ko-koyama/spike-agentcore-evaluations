# src/telemetry.py
"""OTELのsession.id baggageをスパンに伝播させるヘルパー。"""

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import baggage, context


@contextmanager
def session_scope(session_id: str) -> Iterator[None]:
    """このスコープ内で生成されるスパンにsession.idを付与する。"""
    token = context.attach(baggage.set_baggage("session.id", session_id))
    try:
        yield
    finally:
        context.detach(token)
