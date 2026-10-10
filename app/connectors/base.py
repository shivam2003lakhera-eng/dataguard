from abc import ABC, abstractmethod

import pandas as pd


class BaseConnector(ABC):
    """Every connector must be able to read its source into a DataFrame."""

    @abstractmethod
    def read(self) -> pd.DataFrame:
        """Return the source data as a DataFrame."""