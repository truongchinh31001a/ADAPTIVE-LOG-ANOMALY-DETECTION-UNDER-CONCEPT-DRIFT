from __future__ import annotations

from typing import Protocol

import numpy as np
import pandas as pd


class Detector(Protocol):
    """Detector-neutral contract used by the experiment runner."""

    def fit(self, events: pd.DataFrame) -> None: ...

    def score(self, events: pd.DataFrame) -> np.ndarray: ...

    def normalized_score(self, events: pd.DataFrame) -> np.ndarray: ...

    def predict(self, events: pd.DataFrame) -> np.ndarray: ...

    def update(self, events: pd.DataFrame) -> None: ...
