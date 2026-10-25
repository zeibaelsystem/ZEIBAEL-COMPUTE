"""Classify the FIRST actionable failure signal without claiming uncertain provider limits.

No remote calls, credentials, or speculative attribution. Returned excerpts are
bounded and redacted. UNKNOWN is deliberate when evidence is insufficient.
"""
import re

TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\dT[^ ]+\s*")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
TOKEN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{12,})\b")
AUTH = re.compile(r"(?i)\b(Authorization:\s*Bearer\s+)\S+")
ASSIGNMENT = re.compile(r"(?i)\b(token|password|api[_-]?key|secret)\s*[:=]\s*[^\s,;]+")
EXIT_ONLY = re.compile(r"(?i)(?:process completed with exit code|exit code \d+|^FAILED \(failures=|^##\[endgroup\])")

RULES = (
    ("PROVIDER_LIMIT", "high", re.compile(
        r"(?i)(you.ve hit the limit for github-hosted runners|"
        r"exceeded.*github actions.*concurrent|"
        r"no hosted parallelism has been purchased|"
        r"github actions.*(storage quota|billing limit)|"
        r"hosted runner.*quota exceeded)"),
     "GitHub provider limit reported explicitly in the job log"),
    ("ZEIBAEL_INTERNAL", "high", re.compile(
        r"(?i)(NuGet\.targets.*(?:path1|Value cannot be null)|"
        r"unsupported runtime/runner combination in ZEIBAEL|"
        r"Unsupported runtime in ZEIBAEL|"
        r"ZEIBAEL internal allowlist|"
        r"Expected 1[–-]20 jobs|"
        r"Public output exceeds 100 files or 50 MB)"),
     "ZEIBAEL configuration, allowlist, or previously confirmed Windows NuGet regression"),
    ("ZEIBAEL_INTERNAL", "medium", re.compile(
        r"(?i)(Kotlin Windows batch compiler not found|kotlinc\\.bat.*not found)"),
     "Reviewed Windows Kotlin CLI resolution failed in ZEIBAEL driver"),
    ("TRANSIENT", "medium", re.compile(
        r"(?i)(\bHTTP\s*(?:429|502|503|504)\b|"
        r"server returned (?:429|502|503|504)|"
        r"the runner has received a shutdown signal|"
        r"runner lost communication|"
        r"connection (?:reset|timed out)\b)"),
     "Transient network, runner, or service error indicated; retry requires review"),
    ("USER_CODE", "medium", re.compile(
        r"(?i)(SyntaxError:|AssertionError:|TypeError:|NameError:|"
        r"ModuleNotFoundError:|\berror (?:TS|CS|E)\d{3,}|"
        r"\bfatal error: .*\.(?:c|cpp|h):|"
        r"\bFAIL\s+tests?/)"),
     "Program or test failure in supplied job source"),
)
ACTIONABLE = re.compile(r"(?i)(error|exception|failed|fatal|timeout|denied|quota|limit|not found|unavailable)")


def redact(value):
    value = ANSI.sub("", str(value))
    value = TOKEN.sub("[REDACTED]", value)
    value = AUTH.sub(r"\1[REDACTED]", value)
    value = ASSIGNMENT.sub(lambda m: m.group(1) + "=[REDACTED]", value)
    return value[:280]


def diagnose_failure(log):
    """Return an evidence-backed classification, never mistake exit-code wrappers for root cause."""
    unknown = {"category": "UNKNOWN", "confidence": "none",
               "reason": "No attributable root cause found in available log",
               "first_error": ""}
    if not isinstance(log, str) or not log:
        return dict(unknown)
    lines = []
    for raw in log.splitlines():
        line = TIMESTAMP.sub("", ANSI.sub("", raw)).strip()
        line = re.sub(r"^##\[error\]\s*", "", line)
        if not line or EXIT_ONLY.search(line):
            continue
        lines.append(line)
    for line in lines:
        for category, confidence, pattern, reason in RULES:
            if pattern.search(line):
                return {"category": category, "confidence": confidence,
                        "reason": reason, "first_error": redact(line)}
    for line in lines:
        if ACTIONABLE.search(line):
            return {**unknown, "first_error": redact(line)}
    return dict(unknown)


def summarize_failed_jobs(jobs):
    """Jobs must be in GitHub start order; prefer the earliest classifiable failure."""
    fallback = {"category": "UNKNOWN", "confidence": "none",
                "reason": "No attributable root cause found in available job logs",
                "first_error": "", "job": ""}
    for job in jobs:
        if job.get("conclusion") != "failure":
            continue
        result = diagnose_failure(job.get("log", ""))
        result["job"] = redact(job.get("name", ""))[:120]
        if result["category"] != "UNKNOWN":
            return result
        if not fallback["job"]:
            fallback = result
    return fallback
