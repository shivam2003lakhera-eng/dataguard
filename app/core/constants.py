from enum import StrEnum


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RunStatus(StrEnum):
    SUCCESS = "SUCCESS"
    COMPLETED_WITH_ISSUES = "COMPLETED_WITH_ISSUES"
    FAILED = "FAILED"