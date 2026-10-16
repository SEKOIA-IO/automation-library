"""How a scan or search result is reduced to the assertions an analyst sees.

Six actions answer with the same per engine detail and the same counts, so the
rule for which assertions count lives here once. Each action still builds its
own response model, because the fields around these differ.
"""

from typing import Any, NamedTuple

from pydantic import BaseModel


class AssertionResult(BaseModel):
    engine_name: str
    author_name: str
    verdict: bool | None


class AssertionTally(NamedTuple):
    malicious_count: int
    benign_count: int
    total_count: int
    assertions: list[AssertionResult]


def tally_assertions(result: Any) -> AssertionTally:
    """Count the answers engines gave on a result, and list who gave them."""
    # Only assertions inside the bloom mask are real answers from an engine.
    # An engine that abstained answers None, and it is neither malicious nor
    # benign: counting abstentions as benign inflates the clean side of any
    # ratio a customer writes a detection rule against.
    scored = [a for a in result.assertions if a.mask]

    return AssertionTally(
        malicious_count=sum(1 for a in scored if a.verdict is True),
        benign_count=sum(1 for a in scored if a.verdict is False),
        total_count=len(scored),
        assertions=[
            AssertionResult(
                engine_name=a.engine_name,
                author_name=a.author_name,
                verdict=a.verdict,
            )
            for a in scored
        ],
    )
