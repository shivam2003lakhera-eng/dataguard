from typing import Any

from app.core.constants import Severity
from app.core.exceptions import ConfigurationError
from app.quality.rules.allowed_values import AllowedValuesRule
from app.quality.rules.base import BaseRule
from app.quality.rules.columns import RequiredColumnsRule
from app.quality.rules.datatypes import DataTypeRule
from app.quality.rules.duplicates import DuplicatesRule
from app.quality.rules.nulls import RequiredValuesRule
from app.quality.rules.ranges import NumericRangeRule

RULE_TYPES: dict[str, type[BaseRule]] = {
    rule.rule_type: rule
    for rule in (
        RequiredColumnsRule,
        RequiredValuesRule,
        DuplicatesRule,
        NumericRangeRule,
        AllowedValuesRule,
        DataTypeRule,
    )
}


def build_rule(
    rule_type: str,
    name: str,
    config: dict[str, Any],
    severity: str | Severity = "MEDIUM",
) -> BaseRule:
    """Create a validated rule, or raise ConfigurationError."""
    rule_class = RULE_TYPES.get(rule_type)
    if rule_class is None:
        raise ConfigurationError(
            f"Unknown rule type '{rule_type}'.", {"supported": sorted(RULE_TYPES)}
        )
    if not isinstance(config, dict):
        raise ConfigurationError("Rule configuration must be an object.")
    try:
        severity_value = Severity(str(severity).upper())
    except ValueError:
        raise ConfigurationError(
            f"Severity must be one of: {', '.join(s.value for s in Severity)}."
        ) from None
    return rule_class(name, config, severity_value)