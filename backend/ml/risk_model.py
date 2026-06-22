import os
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from backend.core.logger import get_logger

logger  = get_logger("risk_model")
IST     = timezone(timedelta(hours=5, minutes=30))
MODEL_PATH = "models/risk_model.joblib"
os.makedirs("models", exist_ok=True)

# ── Feature Engineering ───────────────────────────────────

CRITICAL_SERVICES = [
    "paymentservice", "checkoutservice",
    "cartservice", "frontend",
    "productcatalogservice", "currencyservice"
]

SERVICE_CRITICALITY = {
    "frontend":              10,
    "checkoutservice":       10,
    "paymentservice":        10,
    "cartservice":           8,
    "productcatalogservice": 8,
    "currencyservice":       7,
    "shippingservice":       5,
    "recommendationservice": 4,
    "emailservice":          3,
    "adservice":             2,
    "loadgenerator":         1
}

DEPENDENCY_COUNT = {
    "frontend":              8,
    "checkoutservice":       6,
    "cartservice":           2,
    "productcatalogservice": 0,
    "currencyservice":       0,
    "paymentservice":        0,
    "shippingservice":       0,
    "emailservice":          0,
    "recommendationservice": 1,
    "adservice":             0,
    "loadgenerator":         1
}

def extract_features(
    service_name:  str,
    changes:       str,
    hour_of_day:   int   = None,
    day_of_week:   int   = None,
    prev_failures: int   = 0,
    change_size:   str   = "small"
) -> np.ndarray:
    """Extract ML features from deployment request"""

    now = datetime.now(IST)
    hour = hour_of_day if hour_of_day is not None else now.hour
    day  = day_of_week  if day_of_week  is not None else now.weekday()

    # Service criticality score
    criticality = SERVICE_CRITICALITY.get(service_name, 5)

    # Dependency count
    deps = DEPENDENCY_COUNT.get(service_name, 0)

    # Is critical service
    is_critical = 1 if service_name in CRITICAL_SERVICES else 0

    # Change size score
    change_words = len(changes.split())
    change_score = min(change_words / 10, 10)

    # High risk keywords in changes
    high_risk_words = [
        "payment", "auth", "database", "migration",
        "schema", "delete", "drop", "breaking", "critical",
        "security", "password", "token", "key", "secret"
    ]
    risk_keywords = sum(
        1 for w in high_risk_words
        if w in changes.lower()
    )

    # Time-based risk (peak hours = higher risk)
    is_peak_hours  = 1 if 9 <= hour <= 18 else 0
    is_weekend     = 1 if day >= 5 else 0
    is_friday      = 1 if day == 4 else 0  # never deploy on Friday!

    features = np.array([
        criticality,      # 0-10
        deps,             # 0-8
        is_critical,      # 0/1
        change_score,     # 0-10
        risk_keywords,    # 0-n
        is_peak_hours,    # 0/1
        is_weekend,       # 0/1
        is_friday,        # 0/1
        prev_failures,    # 0-n
        hour / 24,        # normalized hour
    ]).reshape(1, -1)

    return features

# ── Model Training ────────────────────────────────────────

class RiskModel:
    def __init__(self):
        self.model   = None
        self.trained = False
        self._load_or_init()

    def _load_or_init(self):
        if os.path.exists(MODEL_PATH):
            try:
                self.model   = joblib.load(MODEL_PATH)
                self.trained = True
                logger.info("✅ Risk model loaded from disk")
            except:
                self._init_model()
        else:
            self._init_model()

    def _init_model(self):
        self.model = GradientBoostingClassifier(
            n_estimators       = 100,
            learning_rate      = 0.1,
            max_depth          = 4,
            random_state       = 42,
            min_samples_split  = 5
        )
        logger.info("🆕 New risk model initialized")

    def predict(self, service_name: str, changes: str,
                prev_failures: int = 0) -> dict:
        """Predict risk score using ML model"""

        features = extract_features(
            service_name  = service_name,
            changes       = changes,
            prev_failures = prev_failures
        )

        if self.trained:
            # Use trained ML model
            risk_proba   = self.model.predict_proba(features)[0]
            risk_class   = self.model.predict(features)[0]
            risk_score   = round(risk_proba[1] * 10, 1)
            confidence   = round(max(risk_proba) * 100, 1)
            source       = "ml_model"
        else:
            # Fallback to heuristic
            risk_score, confidence = self._heuristic_risk(
                service_name, changes, prev_failures
            )
            risk_class = 1 if risk_score >= 6 else 0
            source     = "heuristic"

        return {
            "risk_score":  risk_score,
            "risk_class":  int(risk_class),
            "is_safe":     risk_score < 6.0,
            "confidence":  confidence,
            "source":      source,
            "features":    {
                "service_criticality": SERVICE_CRITICALITY.get(service_name, 5),
                "dependency_count":    DEPENDENCY_COUNT.get(service_name, 0),
                "is_critical":         service_name in CRITICAL_SERVICES,
                "prev_failures":       prev_failures,
                "deploy_hour":         datetime.now(IST).hour,
                "is_friday":           datetime.now(IST).weekday() == 4
            }
        }

    def _heuristic_risk(self, service_name: str,
                        changes: str, prev_failures: int) -> tuple:
        """Rule-based risk when no ML model available"""
        score = SERVICE_CRITICALITY.get(service_name, 5)
        score += min(DEPENDENCY_COUNT.get(service_name, 0), 3)

        high_risk = ["payment","auth","database","migration","delete","drop"]
        score += sum(2 for w in high_risk if w in changes.lower())
        score += min(prev_failures * 2, 4)

        if datetime.now(IST).weekday() == 4:
            score += 2  # Friday penalty
        if not (9 <= datetime.now(IST).hour <= 17):
            score += 1  # Off-hours penalty

        return (min(round(score, 1), 10), 75.0)

    def train(self, deployments: list) -> dict:
        """Train model on historical deployment data"""
        if len(deployments) < 10:
            return {
                "success": False,
                "message": f"Need at least 10 deployments to train. Have: {len(deployments)}"
            }

        X, y = [], []
        for dep in deployments:
            if dep.get("status") not in ["healed", "blocked", "failed"]:
                continue
            try:
                features = extract_features(
                    service_name  = dep["service_name"],
                    changes       = dep.get("changes", ""),
                    prev_failures = dep.get("prev_failures", 0)
                )
                # Label: 1 = high risk, 0 = safe
                label = 1 if dep["status"] in ["blocked", "failed"] else 0
                X.append(features.flatten())
                y.append(label)
            except:
                continue

        if len(X) < 10:
            return {"success": False, "message": "Not enough valid samples"}

        X = np.array(X)
        y = np.array(y)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        self.model.fit(X_train, y_train)
        self.trained = True

        # Save model
        joblib.dump(self.model, MODEL_PATH)

        # Evaluate
        y_pred = self.model.predict(X_test)
        report = classification_report(y_test, y_pred, output_dict=True)

        logger.info(f"✅ Model trained on {len(X)} samples")

        return {
            "success":        True,
            "samples":        len(X),
            "accuracy":       round(report["accuracy"] * 100, 1),
            "high_risk_f1":   round(report.get("1", {}).get("f1-score", 0) * 100, 1),
            "model_path":     MODEL_PATH,
            "feature_importance": dict(zip(
                ["criticality","deps","is_critical","change_score",
                 "risk_keywords","peak_hours","weekend","friday",
                 "prev_failures","hour"],
                self.model.feature_importances_.tolist()
            ))
        }

# ── Singleton ─────────────────────────────────────────────
risk_model = RiskModel()