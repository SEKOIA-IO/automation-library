try:
    from mokn.domain.attempts import (
        AttemptCursor,
        AttemptDetail,
        AttemptSummary,
        NormalizedAttack,
        NormalizedAttempt,
    )
    from mokn.domain.configuration import (
        AttemptQuery,
        MoknThreatLevel,
    )
except ModuleNotFoundError:
    from .attempts import (
        AttemptCursor,
        AttemptDetail,
        AttemptSummary,
        NormalizedAttack,
        NormalizedAttempt,
    )
    from .configuration import (
        AttemptQuery,
        MoknThreatLevel,
    )

__all__ = [
    "AttemptCursor",
    "AttemptDetail",
    "AttemptQuery",
    "AttemptSummary",
    "MoknThreatLevel",
    "NormalizedAttack",
    "NormalizedAttempt",
]
