from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


class _NextTemplateLSTM(nn.Module):
    def __init__(
        self,
        vocabulary_size: int,
        embedding_dim: int,
        hidden_size: int,
        num_layers: int,
    ) -> None:
        super().__init__()
        self.embedding = nn.Embedding(vocabulary_size, embedding_dim, padding_idx=0)
        self.lstm = nn.LSTM(
            embedding_dim,
            hidden_size,
            num_layers=num_layers,
            batch_first=True,
        )
        self.output = nn.Linear(hidden_size, vocabulary_size)

    def forward(self, context: torch.Tensor) -> torch.Tensor:
        embedded = self.embedding(context)
        encoded, _ = self.lstm(embedded)
        return self.output(encoded[:, -1, :])


@dataclass(frozen=True)
class DeepLogTrainingSummary:
    sequences: int
    vocabulary_size: int
    epochs: int
    final_loss: float


class DeepLogDetector:
    """DeepLog-style next-template LSTM with top-k anomaly decisions.

    Sequences are chronological within host (or global when host is absent). Labels
    may filter the one-time offline fit, but ``update`` treats selected rows as
    pseudo-normal and never inspects labels.
    """

    _PAD = 0
    _UNKNOWN = 1

    def __init__(
        self,
        *,
        sequence_length: int = 10,
        embedding_dim: int = 32,
        hidden_size: int = 64,
        num_layers: int = 1,
        top_k: int = 9,
        epochs: int = 5,
        update_epochs: int = 1,
        batch_size: int = 512,
        learning_rate: float = 1e-3,
        max_training_sequences: int = 300_000,
        replay_events: int = 100_000,
        score_quantile: float = 0.95,
        random_seed: int = 101,
        device: str = "cpu",
        torch_num_threads: int = 1,
    ) -> None:
        if sequence_length <= 0 or embedding_dim <= 0 or hidden_size <= 0:
            raise ValueError("Sequence length and model dimensions must be positive")
        if num_layers <= 0 or top_k <= 0 or epochs <= 0 or update_epochs <= 0:
            raise ValueError("Layer, top-k, and epoch settings must be positive")
        if batch_size <= 0 or learning_rate <= 0 or max_training_sequences <= 0:
            raise ValueError("Training settings must be positive")
        if replay_events <= 0 or not 0 < score_quantile < 1:
            raise ValueError("Replay size must be positive and score_quantile must be in (0, 1)")
        self.sequence_length = sequence_length
        self.embedding_dim = embedding_dim
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.top_k = top_k
        self.epochs = epochs
        self.update_epochs = update_epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.max_training_sequences = max_training_sequences
        self.replay_events = replay_events
        self.score_quantile = score_quantile
        self.random_seed = random_seed
        self.device = torch.device(device)
        torch.set_num_threads(torch_num_threads)
        self.template_to_index: dict[str, int] = {}
        self.model: _NextTemplateLSTM | None = None
        self.score_scale = 1.0
        self.training_summary: DeepLogTrainingSummary | None = None
        self._replay = pd.DataFrame()
        self._model_version = 0
        self._cache_key: tuple[int, int, str, str] | None = None
        self._cache_scores: np.ndarray | None = None
        self._cache_predictions: np.ndarray | None = None

    def fit(self, events: pd.DataFrame) -> None:
        training = events
        if "anomaly_label" in events.columns:
            normal = events[events["anomaly_label"] == 0]
            if not normal.empty:
                training = normal
        if training.empty:
            raise ValueError("Cannot fit DeepLog on empty data")
        self.template_to_index = {}
        self.model = None
        self._model_version = 0
        self._ensure_templates(training)
        contexts, targets = self._sequence_arrays(
            training, sample_limit=self.max_training_sequences
        )
        final_loss = self._train_arrays(contexts, targets, self.epochs)
        scores, _ = self._infer_arrays(contexts, targets)
        finite = scores[np.isfinite(scores)]
        self.score_scale = max(float(np.quantile(finite, self.score_quantile)), 1e-6)
        self.training_summary = DeepLogTrainingSummary(
            sequences=len(targets),
            vocabulary_size=len(self.template_to_index),
            epochs=self.epochs,
            final_loss=final_loss,
        )
        self._replay = self._replay_frame(training)
        self._invalidate_cache()

    def score(self, events: pd.DataFrame) -> np.ndarray:
        return self._infer(events)[0].copy()

    def normalized_score(self, events: pd.DataFrame) -> np.ndarray:
        # DeepLog's operational decision is top-k membership. Using the binary miss
        # indicator keeps window-level anomaly evidence calibrated and avoids NLL
        # saturation across vocabularies of different sizes.
        return self.predict(events).astype(float)

    def predict(self, events: pd.DataFrame) -> np.ndarray:
        return self._infer(events)[1].copy()

    def update(self, events: pd.DataFrame) -> None:
        if events.empty:
            return
        update_frame = self._replay_frame(events)
        self._ensure_templates(update_frame)
        combined = pd.concat([self._replay, update_frame], ignore_index=True)
        if "event_uid" in combined:
            combined = combined.drop_duplicates("event_uid", keep="last")
        contexts, targets = self._sequence_arrays(
            combined,
            sample_limit=self.max_training_sequences,
        )
        final_loss = self._train_arrays(contexts, targets, self.update_epochs)
        self._replay = self._replay_frame(combined)
        self.training_summary = DeepLogTrainingSummary(
            sequences=len(targets),
            vocabulary_size=len(self.template_to_index),
            epochs=self.update_epochs,
            final_loss=final_loss,
        )
        self._invalidate_cache()

    def _ensure_templates(self, events: pd.DataFrame) -> None:
        observed = sorted({str(value) for value in events["template_id"]})
        new_templates = [value for value in observed if value not in self.template_to_index]
        if not new_templates and self.model is not None:
            return
        old_model = self.model
        for template in new_templates:
            self.template_to_index[template] = len(self.template_to_index) + 2
        vocabulary_size = len(self.template_to_index) + 2
        torch.manual_seed(self.random_seed + self._model_version)
        expanded = _NextTemplateLSTM(
            vocabulary_size,
            self.embedding_dim,
            self.hidden_size,
            self.num_layers,
        ).to(self.device)
        if old_model is not None:
            with torch.no_grad():
                old_size = old_model.embedding.num_embeddings
                expanded.embedding.weight[:old_size].copy_(old_model.embedding.weight)
                expanded.lstm.load_state_dict(old_model.lstm.state_dict())
                expanded.output.weight[:old_size].copy_(old_model.output.weight)
                expanded.output.bias[:old_size].copy_(old_model.output.bias)
        self.model = expanded
        self._model_version += 1
        self._invalidate_cache()

    def _sequence_arrays(
        self,
        events: pd.DataFrame,
        *,
        sample_limit: int | None,
    ) -> tuple[np.ndarray, np.ndarray]:
        required = {"timestamp", "template_id"}
        missing = required - set(events.columns)
        if missing:
            raise ValueError(f"DeepLog input is missing columns: {sorted(missing)}")
        chronological = events.sort_values("timestamp", kind="stable")
        contexts = np.zeros((len(chronological), self.sequence_length), dtype=np.int64)
        targets = np.zeros(len(chronological), dtype=np.int64)
        histories: dict[str, deque[int]] = {}
        has_host = "host" in chronological.columns
        for position, row in enumerate(chronological.itertuples(index=False)):
            host_value = getattr(row, "host", "__global__") if has_host else "__global__"
            host = str(host_value) if str(host_value) else "__global__"
            history = histories.setdefault(host, deque(maxlen=self.sequence_length))
            if history:
                contexts[position, -len(history) :] = list(history)
            template = str(row.template_id)
            target = self.template_to_index.get(template, self._UNKNOWN)
            targets[position] = target
            history.append(target)
        if sample_limit is not None and len(targets) > sample_limit:
            selected = np.linspace(0, len(targets) - 1, sample_limit, dtype=np.int64)
            contexts = contexts[selected]
            targets = targets[selected]
        return contexts, targets

    def _train_arrays(self, contexts: np.ndarray, targets: np.ndarray, epochs: int) -> float:
        if self.model is None:
            raise RuntimeError("DeepLog model has not been initialized")
        if len(targets) == 0:
            raise ValueError("DeepLog needs at least one training sequence")
        generator = torch.Generator().manual_seed(self.random_seed + self._model_version)
        dataset = TensorDataset(torch.from_numpy(contexts), torch.from_numpy(targets))
        loader = DataLoader(
            dataset,
            batch_size=self.batch_size,
            shuffle=True,
            generator=generator,
        )
        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)
        criterion = nn.CrossEntropyLoss()
        final_loss = float("nan")
        self.model.train()
        for _ in range(epochs):
            total_loss = 0.0
            total_examples = 0
            for context, target in loader:
                context = context.to(self.device)
                target = target.to(self.device)
                optimizer.zero_grad(set_to_none=True)
                loss = criterion(self.model(context), target)
                loss.backward()
                optimizer.step()
                total_loss += float(loss.detach()) * len(target)
                total_examples += len(target)
            final_loss = total_loss / total_examples
        return final_loss

    def _infer(self, events: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        if self.model is None:
            raise RuntimeError("DeepLog must be fitted before inference")
        if events.empty:
            return np.array([], dtype=float), np.array([], dtype=np.int8)
        first = str(events["event_uid"].iloc[0]) if "event_uid" in events else str(events.index[0])
        last = str(events["event_uid"].iloc[-1]) if "event_uid" in events else str(events.index[-1])
        key = (self._model_version, len(events), first, last)
        if key != self._cache_key:
            contexts, targets = self._sequence_arrays(events, sample_limit=None)
            scores, predictions = self._infer_arrays(contexts, targets)
            self._cache_key = key
            self._cache_scores = scores
            self._cache_predictions = predictions
        assert self._cache_scores is not None and self._cache_predictions is not None
        return self._cache_scores, self._cache_predictions

    def _infer_arrays(
        self, contexts: np.ndarray, targets: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        if self.model is None:
            raise RuntimeError("DeepLog model has not been initialized")
        score_parts: list[np.ndarray] = []
        prediction_parts: list[np.ndarray] = []
        self.model.eval()
        with torch.no_grad():
            for start in range(0, len(targets), self.batch_size):
                stop = start + self.batch_size
                context = torch.from_numpy(contexts[start:stop]).to(self.device)
                target = torch.from_numpy(targets[start:stop]).to(self.device)
                logits = self.model(context)
                log_probabilities = torch.log_softmax(logits, dim=1)
                unknown = target == self._UNKNOWN
                safe_target = target.clone()
                safe_target[unknown] = self._PAD
                scores = -log_probabilities.gather(1, safe_target[:, None]).squeeze(1)
                scores[unknown] = -np.log(1e-12)
                candidate_logits = logits.clone()
                candidate_logits[:, :2] = -torch.inf
                candidate_count = min(self.top_k, len(self.template_to_index))
                candidates = torch.topk(candidate_logits, k=candidate_count, dim=1).indices
                predicted = ~(candidates == target[:, None]).any(dim=1)
                predicted[unknown] = True
                score_parts.append(scores.cpu().numpy())
                prediction_parts.append(predicted.to(torch.int8).cpu().numpy())
        return np.concatenate(score_parts), np.concatenate(prediction_parts)

    def _replay_frame(self, events: pd.DataFrame) -> pd.DataFrame:
        columns = [
            column
            for column in ["event_uid", "timestamp", "host", "template_id"]
            if column in events
        ]
        return (
            events.loc[:, columns]
            .sort_values("timestamp", kind="stable")
            .tail(self.replay_events)
            .copy()
        )

    def _invalidate_cache(self) -> None:
        self._cache_key = None
        self._cache_scores = None
        self._cache_predictions = None
