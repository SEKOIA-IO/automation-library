"""Reading PolySwarm's sandbox provider list once and answering every question from it.

The Sandbox actions need the list for two things: refusing a provider the
platform does not offer, and choosing an image that can take the artifact.
Reading it separately for each meant a failed read was tolerated by the first
and silently swallowed by the second, which then blamed the provider for having
no image. Here the list is read once, and a failed read stays distinguishable
from a provider that really has nothing suitable.
"""

from collections.abc import Callable
from typing import Any, NamedTuple

from polyswarm_api.api import PolyswarmAPI

from polyswarm_modules.client import CLIENT_ERRORS, failure_kind


class ProviderList(NamedTuple):
    """The providers PolySwarm offers, or None with the reason they could not be read."""

    providers: list[Any] | None
    failure: str = ""


def read_providers(api: PolyswarmAPI, log: Callable[..., Any]) -> ProviderList:
    """Fetch the provider list once. A failure is logged and carried, never raised."""
    try:
        return ProviderList(list(api.sandbox_providers()))
    except CLIENT_ERRORS as exc:
        reason = failure_kind(exc)
        log(
            f"Could not read PolySwarm's sandbox provider list ({reason}), "
            "so the provider and image cannot be checked against it",
            level="warning",
        )
        return ProviderList(None, reason)


def unknown_provider_message(listing: ProviderList, sandbox: str) -> str | None:
    """Why the provider is refused, or None when it is offered or the list could not be read.

    A list that could not be read trusts the configured value, as it always
    has: refusing every run during an outage would be worse than letting the
    platform refuse a wrong slug itself.
    """
    if listing.providers is None:
        return None
    slugs = {getattr(p, "slug", "") for p in listing.providers if getattr(p, "slug", "")}
    if slugs and sandbox not in slugs:
        return (
            f"'{sandbox}' is not a sandbox provider PolySwarm currently offers. "
            f"Known providers: {', '.join(sorted(slugs))}."
        )
    return None


def pick_vm_slug(listing: ProviderList, provider_slug: str, artifact_type: str) -> str | None:
    """An image of this provider that can detonate this kind of artifact.

    Images differ by what they can take, and only some of them can open a URL
    at all, so the choice depends on the artifact as well as the provider.
    None when the list could not be read or the provider offers nothing
    suitable. Naming an image is never guessed.
    """
    if listing.providers is None:
        return None

    wanted = artifact_type.upper()
    for provider in listing.providers:
        raw = getattr(provider, "json", None) or {}
        if (raw.get("slug") or getattr(provider, "slug", "")) != provider_slug:
            continue
        for name, vm in (raw.get("vms") or {}).items():
            if wanted in (vm.get("supported_artifact_types") or []):
                return str(vm.get("slug") or name)
    return None


def no_image_message(listing: ProviderList, sandbox: str) -> str:
    """The error for a run that has no image to detonate in, saying which of two causes it is."""
    if listing.providers is None:
        return (
            f"PolySwarm's sandbox provider list could not be read ({listing.failure}), so no image was chosen "
            f"for {sandbox}. Try again, or name one with vm_slug."
        )
    return (
        f"PolySwarm has no sandbox image for {sandbox} that can detonate this artifact. "
        "Name one explicitly, or check the provider."
    )
