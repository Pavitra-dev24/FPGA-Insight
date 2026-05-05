import numpy as np
from collections import deque
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
N_FEATURES    = 7
TRAIN_SAMPLES = 300
WINDOW_MAX    = 500
THRESHOLD     = -0.25

class AnomalyDetector:

    def __init__(self):
        self.scaler      = StandardScaler()
        self.model       = IsolationForest(
            n_estimators=150,
            max_samples="auto",
            contamination=0.05,
            random_state=42,
            n_jobs=-1,
        )
        self.trained      = False
        self._buffer      = []
        self.scores       = deque(maxlen=WINDOW_MAX)
        self.labels       = deque(maxlen=WINDOW_MAX)
        self.alert_log    = []
    def add_training_sample(self, features: list) -> bool:
        self._buffer.append(features)
        if len(self._buffer) >= TRAIN_SAMPLES:
            self._fit()
            return True
        return False

    def _fit(self):
        X = np.array(self._buffer)
        self.scaler.fit(X)
        X_scaled = self.scaler.transform(X)
        self.model.fit(X_scaled)
        self.trained = True
    def score(self, features: list) -> tuple:
        if not self.trained:
            progress = int(len(self._buffer) / TRAIN_SAMPLES * 100)
            return False, 0.0, f"TRAINING ({progress}%)"

        x = np.array(features, dtype=float).reshape(1, -1)
        x_scaled = self.scaler.transform(x)
        raw_score = float(self.model.score_samples(x_scaled)[0])

        is_anom = raw_score < THRESHOLD
        self.scores.append(raw_score)
        self.labels.append(is_anom)

        if raw_score < -0.45:
            severity = "CRITICAL"
        elif raw_score < THRESHOLD:
            severity = "WARNING"
        else:
            severity = "NORMAL"

        return is_anom, raw_score, severity
    def get_score_history(self) -> tuple:
        return list(self.scores), list(self.labels)

    def training_progress(self) -> float:
        return min(1.0, len(self._buffer) / TRAIN_SAMPLES)

    def log_alert(self, timestamp: str, message: str):
        self.alert_log.append((timestamp, message))
        if len(self.alert_log) > 200:
            self.alert_log.pop(0)
