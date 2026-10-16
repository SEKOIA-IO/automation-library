"""Indicator extraction from free text, with no call to the PolySwarm API.

An analyst pastes a report, an email body or an alert payload into a playbook,
and this action turns it into typed lists a later step can act on. Nothing here
contacts PolySwarm, so it costs no quota and works without network access.

Defanged text is handled first. Reports and phishing mail are routinely written
with hxxp, [.], (.), {.}, [:], [at] and (at) so the reader cannot click them,
and an extractor that does not refang those forms silently returns nothing for
the documents analysts share most often.

Suppression is deliberate and narrow. A domain is only reported when its final
label is a real top level domain and is not a common file extension, so
report.docx does not read as a host. A domain that only appears as part of a
URL or an email address is not reported a second time on its own, because the
longest match at a position wins; the same domain written on its own elsewhere
in the text still reports as a domain. Private, loopback, link local and other
reserved addresses are never dropped in silence: they are returned in their own
list so a playbook can decide whether internal infrastructure matters to it.
"""

import ipaddress
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.validators import non_public

# Every pattern is compiled with these flags. The ASCII flag keeps \w, \d and
# \b at their ASCII meanings, so accented text cannot widen a word boundary or
# turn a lookalike character into a matching letter.
_FLAGS = re.IGNORECASE | re.ASCII

# Upper bound on the text this action will scan in one run. A playbook that
# hands over a multi gigabyte capture would otherwise hold a worker open for
# the length of the regular expression pass.
MAX_INPUT_BYTES = 5 * 1024 * 1024

# A curated top level domain list, not a public suffix list. It deliberately
# leaves out labels that collide with common file extensions, such as zip, mov
# and sh, so a filename in a report does not read as a host.
ALLOWED_TLDS = (
    # generic
    "com",
    "net",
    "org",
    "info",
    "biz",
    "pro",
    "name",
    "mobi",
    "asia",
    # infrastructure and newer generic labels that abuse tends to concentrate in
    "io",
    "co",
    "app",
    "dev",
    "cloud",
    "tech",
    "online",
    "site",
    "store",
    "shop",
    "club",
    "live",
    "icu",
    "vip",
    "top",
    "xyz",
    "link",
    "click",
    "download",
    "stream",
    "work",
    "space",
    "fun",
    "monster",
    "cyou",
    "rest",
    # restricted
    "gov",
    "edu",
    "mil",
    "int",
    # country codes seen most often in threat reporting
    "us",
    "uk",
    "ca",
    "eu",
    "de",
    "fr",
    "nl",
    "it",
    "es",
    "pl",
    "se",
    "no",
    "fi",
    "dk",
    "ch",
    "at",
    "be",
    "cz",
    "ru",
    "su",
    "cn",
    "jp",
    "kr",
    "in",
    "br",
    "au",
    "za",
    "tr",
    "ua",
    "ir",
    "mx",
    "ar",
    "cc",
    "tv",
    "me",
    "ws",
    "pw",
    "tk",
    "ml",
    "ga",
    "cf",
    "gq",
)

# Final labels that make a bare domain candidate a filename rather than a host.
# Nothing here may also appear in ALLOWED_TLDS.
FILE_EXTENSIONS = (
    "exe",
    "dll",
    "sys",
    "bat",
    "cmd",
    "ps1",
    "vbs",
    "js",
    "jse",
    "wsf",
    "scr",
    "jar",
    "class",
    "apk",
    "dmg",
    "pkg",
    "deb",
    "rpm",
    "msi",
    "iso",
    "img",
    "bin",
    "dat",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "pdf",
    "rtf",
    "txt",
    "csv",
    "log",
    "html",
    "htm",
    "css",
    "php",
    "py",
    "rb",
    "sh",
    "zip",
    "rar",
    "7z",
    "gz",
    "tar",
    "mov",
    "mp4",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "svg",
    "ico",
    "lnk",
    "hta",
    "chm",
)

# Defang rewrites, applied in this order. The scheme rewrite runs before the
# separator rewrites, and the bracketed forms run before the word forms so that
# [dot] is not read as anything else on the way past.
_REFANG_SCHEME_RE = re.compile(r"h[x]{2}p", _FLAGS)
_REFANG_DOT_RE = re.compile(r"\[\.\]|\(\.\)|\{\.\}", re.ASCII)
_REFANG_DOT_WORD_RE = re.compile(r"\[dot\]|\(dot\)|\{dot\}", _FLAGS)
_REFANG_AT_RE = re.compile(r"\[@\]|\(@\)|\{@\}", re.ASCII)
_REFANG_AT_WORD_RE = re.compile(r"\[at\]|\(at\)|\{at\}", _FLAGS)

# One DNS label: 1 to 63 characters, alphanumeric with internal hyphens.
_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"

# Longest label first so that com wins over co at the same starting position.
_TLD_ALT = "|".join(sorted(ALLOWED_TLDS, key=len, reverse=True))

# A host name: one or more labels followed by an allowed top level domain.
_HOST = r"(?:" + _LABEL + r"\.)+(?:" + _TLD_ALT + r")"

# Characters that may follow the scheme separator in a URL. Trailing sentence
# punctuation is trimmed from the match afterwards rather than excluded here.
_URL_BODY = r"[A-Za-z0-9\-._~:/?#@!$&'()*+,;=%\[\]]"

_PATTERN_SHA256 = r"\b[a-f0-9]{64}\b"
_PATTERN_SHA1 = r"\b[a-f0-9]{40}\b"
_PATTERN_MD5 = r"\b[a-f0-9]{32}\b"
_PATTERN_URL = r"(?<![\w@.])https?://[A-Za-z0-9\[]" + _URL_BODY + r"*"
# The lookbehind must exclude every character the local part accepts, "%"
# included. With "%" allowed behind, each position after one rescanned to the
# end of the input, so a run of them cost quadratic time: 40 kB took 2.1 s and
# a 5 MB document would not finish in any useful time. The cost is that an
# address written straight after a percent sign is no longer extracted, which
# is the same rule already applied to a dot, a plus and a hyphen.
_PATTERN_EMAIL = r"(?<![\w.+%-])[a-z0-9][a-z0-9._%+-]*@" + _HOST + r"(?![\w])"
_PATTERN_DOMAIN = r"(?<![\w@.-])" + _HOST + r"(?![\w-])"

# The trailing guards reject a fifth octet and a glued letter, while leaving a
# sentence final period alone so that "seen at 8.8.8.8." still matches.
_PATTERN_IPV4 = r"(?<![\w.])\d{1,3}(?:\.\d{1,3}){3}(?![\w])(?!\.[\w])"

# The alternatives cover a full address and every legal position of the double
# colon. Anything that matches is still parsed before it is accepted, so a
# structurally plausible but invalid address is discarded rather than reported.
_PATTERN_IPV6 = (
    r"(?<![0-9A-Za-z:.])"
    r"(?:"
    r"(?:[0-9a-f]{1,4}:){7}[0-9a-f]{1,4}"
    r"|(?:[0-9a-f]{1,4}:){1,7}:"
    r"|(?:[0-9a-f]{1,4}:){1,6}:[0-9a-f]{1,4}"
    r"|(?:[0-9a-f]{1,4}:){1,5}(?::[0-9a-f]{1,4}){1,2}"
    r"|(?:[0-9a-f]{1,4}:){1,4}(?::[0-9a-f]{1,4}){1,3}"
    r"|(?:[0-9a-f]{1,4}:){1,3}(?::[0-9a-f]{1,4}){1,4}"
    r"|(?:[0-9a-f]{1,4}:){1,2}(?::[0-9a-f]{1,4}){1,5}"
    r"|[0-9a-f]{1,4}:(?::[0-9a-f]{1,4}){1,6}"
    r"|::(?:[0-9a-f]{1,4}:){0,6}[0-9a-f]{1,4}"
    r")"
    r"(?![0-9A-Za-z:])"
)

_PATTERNS = (
    ("sha256", _PATTERN_SHA256),
    ("sha1", _PATTERN_SHA1),
    ("md5", _PATTERN_MD5),
    ("url", _PATTERN_URL),
    ("email", _PATTERN_EMAIL),
    ("ipv6", _PATTERN_IPV6),
    ("ipv4", _PATTERN_IPV4),
    ("domain", _PATTERN_DOMAIN),
)

_COMPILED = tuple((indicator_type, re.compile(source, _FLAGS)) for indicator_type, source in _PATTERNS)

# Tie break when two matches at the same place are the same length. The lower
# number wins, so a URL beats the domain inside it and an address beats the
# label that happens to look like one.
_PRIORITY = {
    "url": 0,
    "email": 1,
    "sha256": 2,
    "sha1": 3,
    "md5": 4,
    "ipv6": 5,
    "ipv4": 6,
    "domain": 7,
}

# The byte that marks a character of the text as taken by a kept match.
_COVERED = b"\x01"

_HASH_TYPES = frozenset(("sha256", "sha1", "md5"))

# Sentence punctuation trimmed from the tail of a URL match.
_URL_TAIL_PUNCTUATION = ".,;:!?'\""

# Scheme, authority and remainder of a URL, used to lower case the scheme and
# the host while leaving the path exactly as it was written.
_URL_SHAPE_RE = re.compile(r"^([a-z][a-z0-9+.\-]*)://([^/?#]*)([\s\S]*)\Z", _FLAGS)


def refang_text(text: str) -> str:
    """Rewrite the defanged forms analysts paste into their canonical form.

    Covers hxxp and hxxps, [.] and (.) and {.}, the spelled out [dot] and
    (dot), the [:] and [://] separators, and [@], (@), [at] and (at). Safe to
    run over a whole document.
    """
    refanged = _REFANG_SCHEME_RE.sub("http", text)
    refanged = refanged.replace("[://]", "://")
    refanged = refanged.replace("[:]", ":")
    refanged = _REFANG_DOT_RE.sub(".", refanged)
    refanged = _REFANG_DOT_WORD_RE.sub(".", refanged)
    refanged = _REFANG_AT_RE.sub("@", refanged)
    refanged = _REFANG_AT_WORD_RE.sub("@", refanged)
    return refanged


def _canonical_url(url: str) -> str:
    """Lower case the scheme and the host of a URL, keep the path as written."""
    shape = _URL_SHAPE_RE.match(url)
    if shape is None:
        return url
    return f"{shape.group(1).lower()}://{shape.group(2).lower()}{shape.group(3)}"


def _canonical_email(address: str) -> str:
    """Lower case the domain of an address, keep the local part as written."""
    at_sign = address.rfind("@")
    if at_sign < 0:
        return address
    return f"{address[:at_sign]}@{address[at_sign + 1 :].lower()}"


def _trim_url_tail(span: str) -> str:
    """Drop trailing sentence punctuation and unbalanced closing brackets.

    The bracket counts are taken once and adjusted as characters are dropped,
    because recounting the remaining text for every trailing character made a
    long run of closing brackets quadratic.
    """
    end = len(span)
    open_round = span.count("(")
    close_round = span.count(")")
    open_square = span.count("[")
    close_square = span.count("]")
    while end > 0:
        character = span[end - 1]
        if character in _URL_TAIL_PUNCTUATION:
            end -= 1
            continue
        if character == ")" and open_round < close_round:
            close_round -= 1
            end -= 1
            continue
        if character == "]" and open_square < close_square:
            close_square -= 1
            end -= 1
            continue
        break
    return span[:end]


def _looks_like_filename(domain: str) -> bool:
    return domain.rsplit(".", 1)[-1] in FILE_EXTENSIONS


def _is_reserved_address(address: str) -> bool:
    """True for an address no external service can be asked about.

    Uses the same test as the actions that take an address, so an address
    reported as public here is one ScanIp and SearchIp will accept: shared
    address space (100.64.0.0/10) and every other range that is not globally
    routable lands here too. They are reported separately rather than
    discarded, because internal infrastructure in a report is often the point.
    """
    parsed = ipaddress.ip_address(address)
    return parsed.is_unspecified or non_public(parsed) is not None


def _candidate_value(indicator_type: str, raw: str) -> str | None:
    """Validate and canonicalise one raw match, or return None to suppress it."""
    if indicator_type in _HASH_TYPES:
        return raw.lower()

    if indicator_type == "ipv4":
        try:
            ipaddress.IPv4Address(raw)
        except ValueError:
            return None
        return raw

    if indicator_type == "ipv6":
        try:
            parsed = ipaddress.IPv6Address(raw)
        except ValueError:
            return None
        return str(parsed)

    if indicator_type == "domain":
        domain = raw.lower()
        if _looks_like_filename(domain):
            return None
        return domain

    if indicator_type == "email":
        return _canonical_email(raw)

    if indicator_type == "url":
        return _canonical_url(_trim_url_tail(raw))

    return None


def extract_indicators(text: str) -> dict[str, list[str]]:
    """Extract indicators from text and return one deduplicated list per type.

    Each list keeps the order the indicators appear in the text, and each value
    appears once. Where two matches overlap, the longer one wins, so a domain
    or an address that is only part of a URL is not also reported on its own.
    A domain written standalone somewhere else in the same text still reports.
    """
    refanged = refang_text(text)

    candidates: list[tuple[int, int, str, str]] = []
    for indicator_type, pattern in _COMPILED:
        for match in pattern.finditer(refanged):
            raw = match.group(0)
            if indicator_type == "url":
                raw = _trim_url_tail(raw)
                if not raw:
                    continue
            value = _candidate_value(indicator_type, raw)
            if value is not None:
                candidates.append((match.start(), match.start() + len(raw), indicator_type, value))

    # Longest span first, type priority breaking a tie. Both sorts are stable,
    # so matches that tie on every key stay in the order they were found.
    candidates.sort(key=lambda candidate: (-(candidate[1] - candidate[0]), _PRIORITY[candidate[2]]))

    # Whether a candidate overlaps anything already kept is answered from a
    # coverage map, one byte per character of the text. Kept spans never
    # overlap, so marking them touches each character at most once, and a
    # candidate is tested by looking for a marked byte inside its own span.
    # That is linear in the text however many matches there are, where
    # comparing every candidate against every kept span grows with the square
    # of the match count and let a few hundred kilobytes run for seconds.
    covered = bytearray(len(refanged))
    kept: list[tuple[int, int, str, str]] = []
    for candidate in candidates:
        start, end = candidate[0], candidate[1]
        if covered.find(_COVERED, start, end) != -1:
            continue
        covered[start:end] = _COVERED * (end - start)
        kept.append(candidate)

    kept.sort(key=lambda candidate: (candidate[0], _PRIORITY[candidate[2]]))

    buckets: dict[str, list[str]] = {
        "ipv4": [],
        "ipv6": [],
        "domain": [],
        "url": [],
        "md5": [],
        "sha1": [],
        "sha256": [],
        "email": [],
        "reserved_ip": [],
    }

    # A set beside each list answers "seen already" in constant time, and the
    # list keeps the order the indicators appeared in.
    seen: dict[str, set[str]] = {name: set() for name in buckets}

    for _, _, indicator_type, value in kept:
        bucket = indicator_type
        if indicator_type in ("ipv4", "ipv6") and _is_reserved_address(value):
            bucket = "reserved_ip"
        if value not in seen[bucket]:
            seen[bucket].add(value)
            buckets[bucket].append(value)

    return buckets


class ExtractIocsArguments(BaseModel):
    text: str | None = Field(
        default=None,
        description=(
            "Text to extract indicators from, up to 5 MB. Supply this or a file, not both. Nothing is "
            "sent to PolySwarm: this runs locally and spends no quota."
        ),
    )
    file: str | None = Field(
        default=None,
        description=(
            "Name of a text file to extract indicators from, relative to the run data directory "
            "where Sekoia delivers it, up to 5 MB. Supply this or text, not both. Nothing is sent to "
            "PolySwarm: this runs locally and spends no quota."
        ),
    )


class ExtractIocsResponse(BaseModel):
    ipv4: list[str]
    ipv6: list[str]
    domain: list[str]
    url: list[str]
    md5: list[str]
    sha1: list[str]
    sha256: list[str]
    email: list[str]
    reserved_ip: list[str]
    total_count: int


class ExtractIocs(PolyswarmAction):
    """Action to extract indicators of compromise from text or from a file.

    Unlike every other action in this module, this one never calls the
    PolySwarm API: it runs entirely locally, costs nothing and spends no
    quota.
    """

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        args = ExtractIocsArguments(**arguments)

        # A field a playbook left empty arrives as an empty string rather than
        # as nothing at all, and whitespace is not text to scan.
        text = args.text if args.text and args.text.strip() else None
        file_name = args.file if args.file and args.file.strip() else None

        if text is None and file_name is None:
            self.error("Supply either text or file. Neither was provided")
            return None
        if text is not None and file_name is not None:
            self.error("Supply either text or file. Both were provided, so there is nothing to choose between them")
            return None

        if file_name is not None:
            path = self.resolve_data_file(file_name)
            if path is None:
                return None
            content = self._read_text(path)
            if content is None:
                return None
        else:
            content = text or ""
            if len(content.encode("utf-8", errors="replace")) > MAX_INPUT_BYTES:
                self.error(f"The text is larger than the {MAX_INPUT_BYTES // (1024 * 1024)} MB extraction limit")
                return None

        buckets = extract_indicators(content)
        total_count = sum(len(values) for values in buckets.values())

        return ExtractIocsResponse(total_count=total_count, **buckets).model_dump()

    def _read_text(self, path: Path) -> str | None:
        # Check the size on disk before reading anything: reading first would
        # pull the whole file into memory just to refuse it.
        try:
            size = path.stat().st_size
        except OSError:
            self.error("The file could not be read from the run data directory")
            return None
        if size > MAX_INPUT_BYTES:
            self.error(f"The file is larger than the {MAX_INPUT_BYTES // (1024 * 1024)} MB extraction limit")
            return None

        try:
            raw = path.read_bytes()
        except OSError:
            self.error("The file could not be read from the run data directory")
            return None

        # Reports arrive with mixed encodings and the occasional binary blob.
        # Replacing what does not decode keeps the readable indicators rather
        # than failing the whole run on one byte.
        return raw.decode("utf-8", errors="replace")
