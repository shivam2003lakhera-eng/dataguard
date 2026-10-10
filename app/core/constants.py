from enum import StrEnum


class SourceType(StrEnum):
    CSV = "CSV"
    JSON = "JSON"
    REST_API = "REST_API"


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    ERROR = "ERROR"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class RunStatus(StrEnum):
    SUCCESS = "SUCCESS"
    COMPLETED_WITH_ISSUES = "COMPLETED_WITH_ISSUES"
    FAILED = "FAILED"


class IncidentStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class ProcessingPolicy(StrEnum):
    REPORT_ONLY = "REPORT_ONLY"
    PARTIAL_LOAD = "PARTIAL_LOAD"
    FAIL_ON_CRITICAL = "FAIL_ON_CRITICAL"