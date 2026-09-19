"""HTTP security header analysis without external HTTP dependencies."""

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class HeaderFinding:
    """A single security header recommendation."""

    header: str
    severity: str
    message: str
    recommendation: str

    def as_dict(self) -> dict[str, str]:
        return {
            "header": self.header,
            "severity": self.severity,
            "message": self.message,
            "recommendation": self.recommendation,
        }


class SecurityHeaderScanner:
    """Evaluate response headers for common security weaknesses."""

    def scan(self, headers: Mapping[str, str]) -> list[HeaderFinding]:
        normalized = {key.lower(): value.strip() for key, value in headers.items()}
        findings: list[HeaderFinding] = []

        checks = (
            self._check_csp,
            self._check_hsts,
            self._check_x_content_type_options,
            self._check_x_frame_options,
            self._check_referrer_policy,
            self._check_permissions_policy,
        )

        for check in checks:
            finding = check(normalized)
            if finding is not None:
                findings.append(finding)

        return findings

    @staticmethod
    def _missing(header: str, recommendation: str) -> HeaderFinding:
        return HeaderFinding(
            header=header,
            severity="high",
            message=f"{header} is missing.",
            recommendation=recommendation,
        )

    def _check_csp(self, headers: Mapping[str, str]) -> HeaderFinding | None:
        value = headers.get("content-security-policy")
        if not value:
            return self._missing(
                "Content-Security-Policy",
                "Define a restrictive policy and avoid unsafe-inline and unsafe-eval.",
            )
        if "unsafe-inline" in value or "unsafe-eval" in value:
            return HeaderFinding(
                "Content-Security-Policy",
                "medium",
                "The policy allows unsafe-inline or unsafe-eval.",
                "Replace inline code with nonces or hashes and remove unsafe-eval.",
            )
        return None

    def _check_hsts(self, headers: Mapping[str, str]) -> HeaderFinding | None:
        value = headers.get("strict-transport-security")
        if not value:
            return self._missing(
                "Strict-Transport-Security",
                "Set max-age to at least 31536000 and consider includeSubDomains.",
            )
        try:
            max_age = int(value.lower().split("max-age=", 1)[1].split(";", 1)[0].strip())
        except (IndexError, ValueError):
            max_age = 0
        if max_age < 31536000:
            return HeaderFinding(
                "Strict-Transport-Security",
                "medium",
                "The HSTS max-age is shorter than one year or invalid.",
                "Use max-age=31536000 or longer after validating HTTPS everywhere.",
            )
        return None

    def _check_x_content_type_options(self, headers: Mapping[str, str]) -> HeaderFinding | None:
        value = headers.get("x-content-type-options")
        if value is None:
            return self._missing(
                "X-Content-Type-Options",
                "Set the value to nosniff.",
            )
        if value.lower() != "nosniff":
            return HeaderFinding(
                "X-Content-Type-Options",
                "medium",
                "The value is not nosniff.",
                "Set X-Content-Type-Options: nosniff.",
            )
        return None

    def _check_x_frame_options(self, headers: Mapping[str, str]) -> HeaderFinding | None:
        value = headers.get("x-frame-options")
        if value is None:
            return self._missing(
                "X-Frame-Options",
                "Use DENY or SAMEORIGIN when framing is not required.",
            )
        if value.upper() not in {"DENY", "SAMEORIGIN"}:
            return HeaderFinding(
                "X-Frame-Options",
                "medium",
                "The value is weak or unsupported.",
                "Use DENY or SAMEORIGIN, or control framing with CSP frame-ancestors.",
            )
        return None

    def _check_referrer_policy(self, headers: Mapping[str, str]) -> HeaderFinding | None:
        value = headers.get("referrer-policy")
        if not value:
            return self._missing(
                "Referrer-Policy",
                "Use strict-origin-when-cross-origin or a stricter policy.",
            )
        if value.lower() in {"unsafe-url", "no-referrer-when-downgrade"}:
            return HeaderFinding(
                "Referrer-Policy",
                "low",
                "The policy may disclose more URL information than necessary.",
                "Prefer strict-origin-when-cross-origin or no-referrer.",
            )
        return None

    def _check_permissions_policy(self, headers: Mapping[str, str]) -> HeaderFinding | None:
        if not headers.get("permissions-policy"):
            return self._missing(
                "Permissions-Policy",
                "Disable browser features that the application does not need.",
            )
        return None


def scan_headers(headers: Mapping[str, str]) -> list[dict[str, str]]:
    """Return JSON-friendly findings for a response header mapping."""

    return [finding.as_dict() for finding in SecurityHeaderScanner().scan(headers)]