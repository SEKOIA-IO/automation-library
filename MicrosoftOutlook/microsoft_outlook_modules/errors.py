"""Safe, consistent errors for analyst-facing actions and per-item results."""

import binascii
import logging
from typing import Any
from uuid import uuid4

import requests
from pydantic import ValidationError
from urllib3.exceptions import InvalidHeader as RetryHeaderError

logger = logging.getLogger(__name__)


class ActionInputError(ValueError):
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


class AttachmentError(ValueError):
    pass


class IncompleteResultsError(RuntimeError):
    pass


class VerificationError(RuntimeError):
    pass


class GraphAPIError(requests.HTTPError):
    """Retain a Graph response without exposing its raw body in action results."""


def describe_error(exc: Exception, *, may_modify: bool = False) -> dict[str, Any]:
    code, message, retryable, unknown = "unexpected_error", "", False, False
    status = None
    reference = None
    if isinstance(exc, ValidationError):
        descriptions = []
        for item in exc.errors(include_input=False, include_context=False, include_url=False)[:3]:
            field = ".".join(str(part) for part in item["loc"]) or "arguments"
            descriptions.append(f"{field}: {item['msg']}")
        code, message = "invalid_arguments", "Invalid parameters: " + "; ".join(descriptions)
    elif isinstance(exc, ActionInputError):
        code = "invalid_arguments"
        message = f"Invalid {exc.field or 'parameters'}: {exc}"
    elif isinstance(exc, AttachmentError | binascii.Error | UnicodeError) or type(exc) is LookupError:
        code, message = (
            "attachment_processing_failed",
            "Attachment could not be decoded or parsed; check its format and size.",
        )
        if isinstance(exc, AttachmentError):
            message = str(exc)
    elif isinstance(exc, IncompleteResultsError):
        code, message = (
            "incomplete_results",
            "Graph pagination limit reached; results are incomplete. Narrow the search.",
        )
    elif isinstance(exc, VerificationError):
        code, message = "verification_failed", str(exc)
    elif isinstance(exc, requests.HTTPError):
        response = exc.response
        status = response.status_code if response is not None else None
        auth_endpoint = response is not None and (response.url or "").startswith("https://login.microsoftonline.com/")
        if status == 429:
            code, message, retryable = (
                "rate_limited",
                "Microsoft service rate limit reached. Wait before trying again.",
                True,
            )
        elif status is not None and status >= 500:
            code, message, retryable = "service_unavailable", "Microsoft service is temporarily unavailable.", True
            unknown = may_modify and not auth_endpoint
        elif auth_endpoint or status == 401:
            code, message = (
                "authentication_failed",
                "Authentication failed. Check the tenant, application and credentials.",
            )
        elif status == 403:
            code, message = (
                "access_denied",
                "Access denied. Check application permissions, admin consent and mailbox scope.",
            )
        elif status == 404:
            code, message = (
                "not_found",
                "Mailbox, message or folder was not found or is not accessible. Refresh the target.",
            )
        elif status == 410:
            code, message = "resource_expired", "The resource or continuation has expired. Run a fresh search."
        elif status == 409:
            code, message = (
                "conflict",
                "The target changed or conflicts with this operation. Refresh it before retrying.",
            )
        else:
            code, message = (
                "request_rejected",
                "Microsoft rejected the request. Check the parameters and target identifiers.",
            )
    elif isinstance(exc, requests.Timeout):
        code, message, retryable = "timeout", "The Microsoft request timed out.", True
        unknown = may_modify
    elif isinstance(
        exc,
        requests.ConnectionError | requests.exceptions.ChunkedEncodingError | requests.exceptions.ContentDecodingError,
    ):
        code, message, retryable = "connection_failed", "Could not complete the connection to Microsoft.", True
        unknown = may_modify
    elif isinstance(exc, requests.exceptions.RetryError):
        code, message, retryable = (
            "retries_exhausted",
            "Microsoft request retries were exhausted. Try again later.",
            True,
        )
        unknown = may_modify
    elif isinstance(exc, RetryHeaderError | requests.exceptions.InvalidHeader):
        code, message, retryable = (
            "retry_delay_exceeded",
            "Microsoft requested a retry delay outside the action budget.",
            True,
        )
    elif isinstance(exc, requests.RequestException):
        code, message = (
            "request_failed",
            "Could not complete the Microsoft request. Check connectivity and configuration.",
        )
        unknown = may_modify
    else:
        reference = str(uuid4())
        # Deliberately exclude exception text, local variables and source lines: these can contain credentials.
        frames = []
        traceback = exc.__traceback__
        while traceback is not None:
            frame = traceback.tb_frame
            frames.append(f"{frame.f_code.co_filename}:{traceback.tb_lineno} in {frame.f_code.co_name}")
            traceback = traceback.tb_next
        logger.error("Diagnostic %s: %s; %s", reference, type(exc).__name__, " -> ".join(frames))
        message = f"An unexpected technical error occurred. See action logs (reference {reference})."
        unknown = may_modify
    if unknown:
        message += " The change may already have been applied; verify the current state before retrying."
    result: dict[str, Any] = {
        "code": code,
        "message": message,
        "retryable": retryable and not may_modify,
        "outcome_unknown": unknown,
    }
    if status is not None:
        result["http_status"] = status
    if reference is not None:
        result["diagnostic_reference"] = reference
    return result
