# predictor.py — ML Fire Prediction Engine

import joblib
import numpy as np
import os

# Load model and scaler
MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")
model = joblib.load(os.path.join(MODEL_DIR, "fire_model.pkl"))
scaler = joblib.load(os.path.join(MODEL_DIR, "scaler.pkl"))

print("ML Model loaded successfully!")
print(f"   Model type: {type(model).__name__}")


def predict_fire(temp, rh, ws):
    """
    Predict fire risk from sensor readings.
    
    Args:
        temp: Temperature reading from sensor
        rh: Relative Humidity reading from sensor
        ws: Wind Speed reading from sensor
    
    Returns:
        dict with prediction result, confidence, and risk level
    """
    try:
        # Prepare input — matches data.csv columns: Temperature, RH, Ws
        features = np.array([[float(temp), float(rh), float(ws)]])
        
        # Scale features
        features_scaled = scaler.transform(features)
        
        # Predict
        prediction = model.predict(features_scaled)[0]
        
        # Get probability if available
        confidence = 0.0
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(features_scaled)[0]
            confidence = float(max(proba)) * 100
        
        # Determine result
        # Model output: 1 = fire, 0 = safe (common convention)
        is_fire = int(prediction) == 1
        
        result = {
            "prediction": "FIRE DETECTED 🔥" if is_fire else "SAFE ✅",
            "is_fire": is_fire,
            "confidence": round(confidence, 2),
            "risk_level": _get_risk_level(confidence, is_fire),
            "input": {
                "temperature": float(temp),
                "humidity": float(rh),
                "wind_speed": float(ws)
            }
        }
        
        return result
    
    except Exception as e:
        print(f"❌ Prediction error: {e}")
        return {
            "prediction": "ERROR",
            "is_fire": False,
            "confidence": 0.0,
            "risk_level": "UNKNOWN",
            "error": str(e),
            "input": {
                "temperature": float(temp),
                "humidity": float(rh),
                "wind_speed": float(ws)
            }
        }


def _get_risk_level(confidence, is_fire):
    """Classify risk level based on confidence and prediction."""
    if not is_fire:
        if confidence >= 90:
            return "LOW"
        elif confidence >= 70:
            return "MODERATE"
        else:
            return "MODERATE"
    else:
        if confidence >= 90:
            return "CRITICAL"
        elif confidence >= 70:
            return "HIGH"
        else:
            return "MODERATE"
