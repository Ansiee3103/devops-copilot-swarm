from datetime import datetime, timezone, timedelta
from typing import List, Dict
from backend.core.logger import get_logger

logger = get_logger("predictor")
IST    = timezone(timedelta(hours=5, minutes=30))

class TrafficPredictor:
    """
    Predicts traffic patterns and recommends
    replica counts before deployment
    """

    # Historical traffic patterns (hour → relative load)
    HOURLY_PATTERN = {
        0: 0.1,  1: 0.1,  2: 0.1,  3: 0.1,
        4: 0.1,  5: 0.2,  6: 0.4,  7: 0.6,
        8: 0.8,  9: 1.0,  10: 1.0, 11: 1.0,
        12: 0.9, 13: 1.0, 14: 1.0, 15: 1.0,
        16: 0.9, 17: 0.8, 18: 0.7, 19: 0.6,
        20: 0.5, 21: 0.4, 22: 0.3, 23: 0.2
    }

    # Day multipliers
    DAY_PATTERN = {
        0: 1.0,   # Monday
        1: 1.0,   # Tuesday
        2: 1.0,   # Wednesday
        3: 0.95,  # Thursday
        4: 0.9,   # Friday
        5: 0.5,   # Saturday
        6: 0.4    # Sunday
    }

    SERVICE_BASE_REPLICAS = {
        "frontend":              3,
        "checkoutservice":       2,
        "paymentservice":        2,
        "cartservice":           2,
        "productcatalogservice": 2,
        "recommendationservice": 2,
        "shippingservice":       1,
        "emailservice":          1,
        "adservice":             1,
        "currencyservice":       1,
        "loadgenerator":         1
    }

    def predict_load(self, hours_ahead: int = 1) -> Dict:
        """Predict load for next N hours"""
        now       = datetime.now(IST)
        future    = now + timedelta(hours=hours_ahead)
        hour      = future.hour
        weekday   = future.weekday()

        load       = self.HOURLY_PATTERN[hour] * self.DAY_PATTERN[weekday]
        is_peak    = load >= 0.8
        is_low     = load <= 0.3

        return {
            "predicted_hour":      future.strftime("%H:%M"),
            "load_factor":         round(load, 2),
            "is_peak_hours":       is_peak,
            "is_low_traffic":      is_low,
            "traffic_level":       "peak"    if is_peak else
                                   "normal"  if load > 0.5 else
                                   "low",
            "deploy_recommended":  not is_peak,
            "reason":              "Peak traffic hours — avoid deployment"
                                   if is_peak else
                                   "Low traffic — ideal for deployment"
                                   if is_low else
                                   "Normal traffic — deployment possible"
        }

    def recommend_replicas(
        self,
        service_name: str,
        current_hour: int = None,
        current_day:  int = None
    ) -> Dict:
        """Recommend replica count based on predicted traffic"""
        now         = datetime.now(IST)
        hour        = current_hour if current_hour is not None else now.hour
        day         = current_day  if current_day  is not None else now.weekday()

        base        = self.SERVICE_BASE_REPLICAS.get(service_name, 2)
        load        = self.HOURLY_PATTERN[hour] * self.DAY_PATTERN[day]
        recommended = max(1, round(base * load * 1.2))  # 20% headroom

        # Peak hours — add extra buffer
        if load >= 0.8:
            recommended = max(recommended, base + 1)

        return {
            "service_name":       service_name,
            "base_replicas":      base,
            "load_factor":        round(load, 2),
            "recommended":        recommended,
            "min_replicas":       1,
            "max_replicas":       recommended * 2,
            "scale_suggestion":   "scale_up"   if recommended > base else
                                  "scale_down" if recommended < base else
                                  "maintain",
            "kubectl_command":    f"kubectl scale deployment {service_name} "
                                  f"--replicas={recommended}"
        }

    def get_deployment_window(self) -> Dict:
        """Find optimal deployment windows for next 24 hours"""
        now     = datetime.now(IST)
        windows = []

        for h in range(24):
            future  = now + timedelta(hours=h)
            hour    = future.hour
            weekday = future.weekday()
            load    = self.HOURLY_PATTERN[hour] * self.DAY_PATTERN[weekday]

            if load <= 0.4:
                windows.append({
                    "time":         future.strftime("%H:%M"),
                    "load_factor":  round(load, 2),
                    "quality":      "excellent" if load <= 0.2 else "good"
                })

        return {
            "optimal_windows": windows[:5],
            "next_best_time":  windows[0]["time"] if windows else "No ideal window in 24h",
            "current_load":    round(
                self.HOURLY_PATTERN[now.hour] * self.DAY_PATTERN[now.weekday()],
                2
            )
        }

traffic_predictor = TrafficPredictor()