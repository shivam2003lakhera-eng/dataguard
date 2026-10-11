import pandas as pd

from app.core.constants import CheckStatus
from app.quality.rules.base import BaseRule


class Demo(BaseRule):
    rule_type = "demo"

    def evaluate(self, df):
        return self._result(CheckStatus.PASS, "all good", len(df))


print(Demo("demo_rule", {}).evaluate(pd.DataFrame({"a": [1, 2]})))