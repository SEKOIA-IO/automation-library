import re
from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from polyswarm_api.api import PolyswarmAPI
from pydantic import BaseModel, Field
from requests import RequestException

from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.client import build_client

SCAN_FAILURES: tuple[type[Exception], ...] = (
    ps_exceptions.PolyswarmException,
    RequestException,
)
MISSING_RESULT: tuple[type[Exception], ...] = (
    ps_exceptions.NoResultsException,
    ps_exceptions.NotFoundException,
)

# PolySwarm has no dedicated threat actor field on any client surface: neither
# the artifact instance, its metadata nor the tag link resource carries one.
# Actor attribution travels on the free form tag surface, so an actor is read
# from a tag that names itself as one and is left empty otherwise. Guessing an
# actor from an unprefixed tag would put a name in front of an analyst that
# PolySwarm never asserted.
ACTOR_TAG_PREFIXES = ("actor:", "threat_actor:", "threat-actor:", "apt:")


def _as_names(values: Any) -> list[str]:
    """Normalise a tag or family payload from the client into plain names.

    The tag link resource hands back whatever the endpoint sent, which is a
    list of names on the current API and a list of objects carrying a name on
    older deployments. Anything else is treated as no attribution at all.
    """
    if not isinstance(values, (list, tuple, set)):
        return []

    names: list[str] = []
    for value in values:
        if isinstance(value, dict):
            raw = value.get("name") or value.get("tag") or value.get("family") or ""
        elif isinstance(value, str):
            raw = value
        else:
            continue
        name = raw.strip()
        if name:
            names.append(name)
    return names


def _unique(values: list[str]) -> list[str]:
    """Deduplicate names case insensitively while keeping the first spelling."""
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(value)
    return unique


def _actor_from_tags(tags: list[str]) -> str:
    """Return the actor named by a tag, or an empty string when none names one."""
    for tag in tags:
        lowered = tag.casefold()
        for prefix in ACTOR_TAG_PREFIXES:
            if lowered.startswith(prefix):
                actor = tag[len(prefix) :].strip()
                if actor:
                    return actor
    return ""


_HASH_LENGTHS: dict[int, str] = {32: "MD5", 40: "SHA1", 64: "SHA256"}
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


def _hash_kind(value: str) -> str | None:
    """Return the hash type a value plausibly is, or None when it is neither.

    A wrong-length or non-hex string is rejected before it costs an API
    request: the server would refuse it anyway, and finding that out over the
    network is slower and burns quota for an answer that is knowable locally.
    """
    stripped = value.strip()
    if not _HEX_RE.match(stripped):
        return None
    return _HASH_LENGTHS.get(len(stripped))


class SearchHashArguments(BaseModel):
    query_hash: str = Field(
        ...,
        description=(
            "The hash (SHA256, SHA1, or MD5) to look up. Nothing is submitted to "
            "PolySwarm: this is a read-only search and spends no scan quota."
        ),
    )
    detect_threshold: int = Field(
        default=1,
        ge=1,
        description=(
            "How many malicious engine detections activate the detected branch. "
            "Default of 1 flags on any single detection."
        ),
    )


class SearchHashResponse(BaseModel):
    found: bool = True
    benign_detections: int = 0
    total_detections: int = 0
    families: list[str] = Field(default_factory=list)
    family: str = ""
    first_seen: str = ""
    malicious_detections: int = 0
    permalink: str = ""
    polyscore: float | None = None
    tags: list[str] = Field(default_factory=list)
    threat_actor: str = ""


class SearchHash(PolyswarmAction):
    """Action to look up a hash against what PolySwarm already knows.

    This is a read-only search: it submits nothing and spends no scan quota.
    The action activates one of three branches, which is the shape a Sekoia
    playbook expects from a reputation lookup: detected, not detected, or
    unknown when PolySwarm has never seen the artifact. An unseen hash is an
    ordinary outcome rather than an error, so the playbook can route it to a
    scan or a detonation step instead of stopping.
    """

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        args = SearchHashArguments(**arguments)

        if _hash_kind(args.query_hash) is None:
            self.error(
                f"'{args.query_hash}' is not a plausible MD5, SHA1 or SHA256 hash: "
                "expected 32, 40 or 64 hexadecimal characters"
            )
            return None

        api = build_client(self.module.configuration)

        try:
            results = list(api.search(args.query_hash))
        except MISSING_RESULT:
            # The client raises on 204 and 404 rather than returning an empty
            # list, and an unseen hash is the most common thing an analyst asks
            # about. Without this the playbook gets a Python traceback.
            results = []
        except ps_exceptions.InvalidValueException:
            self.error(f"{args.query_hash} is not a valid hash")
            return None
        except SCAN_FAILURES as exc:
            # Anything else, an authentication failure, a usage limit, a gateway
            # error, would otherwise escape and the SDK would hand the playbook a
            # Python traceback carrying container paths and the request URL.
            self.error(f"PolySwarm did not answer the hash lookup ({type(exc).__name__}).")
            return None

        if not results:
            self.set_output("unknown", True)
            return SearchHashResponse(found=False).model_dump()

        result = results[0]

        family: str = ""
        polyunite: dict[str, Any] | None = getattr(result.metadata, "json", {}).get("polyunite")
        if polyunite and isinstance(polyunite, dict):
            family = polyunite.get("malware_family", "")

        families, tags, threat_actor = self._attribution(api, result, family)

        # An engine that abstained answered None, which is neither malicious nor
        # benign. The client's benign_assertions counts those as benign.
        scored = [a for a in result.assertions if a.mask]

        malicious_detections = sum(1 for a in scored if a.verdict is True)
        self.set_output("detected" if malicious_detections >= args.detect_threshold else "not detected", True)

        response = SearchHashResponse(
            found=True,
            benign_detections=sum(1 for a in scored if a.verdict is False),
            total_detections=len(scored),
            families=families,
            first_seen=str(result.first_seen),
            family=family,
            malicious_detections=malicious_detections,
            permalink=result.permalink,
            polyscore=result.polyscore,
            tags=tags,
            threat_actor=threat_actor,
        )

        return response.model_dump()

    def _attribution(self, api: PolyswarmAPI, result: Any, family: str) -> tuple[list[str], list[str], str]:
        """Read the tag link surface for the families, tags and actor of an artifact.

        Attribution is additive to the verdict. A tag surface that is empty,
        unreachable or not entitled on the caller's plan leaves the attribution
        fields empty, and never turns a good verdict into a failed action, so
        every failure here is swallowed rather than raised.
        """
        families: list[str] = [family] if family else []

        try:
            sha256 = str(getattr(result, "sha256", "") or "")
            if not sha256:
                return families, [], ""

            tag_link = api.tag_link_get(sha256)
            link_families = _as_names(getattr(tag_link, "families", None))
            tags = _as_names(getattr(tag_link, "tags", None))
        except Exception as exc:
            self.log(
                f"PolySwarm returned no attribution for the hash ({type(exc).__name__}), "
                "reporting the verdict without it",
                level="info",
            )
            return families, [], ""

        return _unique(families + link_families), _unique(tags), _actor_from_tags(tags)
