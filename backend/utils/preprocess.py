# utils/preprocess.py — Data Validation & Normalization

def validate_sensor_data(temp, rh, ws):
    """
    Validate sensor readings are within reasonable ranges.
    
    Returns:
        tuple: (is_valid, cleaned_values, warnings)
    """
    warnings = []
    
    try:
        temp = float(temp)
        rh = float(rh)
        ws = float(ws)
    except (ValueError, TypeError) as e:
        return False, None, [f"Invalid numeric values: {e}"]
    
    # Temperature: -50 to 100°C (forest fire context)
    if temp < -50 or temp > 150:
        warnings.append(f"Temperature {temp}°C out of expected range [-50, 150]")
    
    # Humidity: 0 to 100%
    if rh < 0 or rh > 100:
        warnings.append(f"Humidity {rh}% out of expected range [0, 100]")
    
    # Wind speed: 0 to 200 km/h
    if ws < 0 or ws > 200:
        warnings.append(f"Wind speed {ws} km/h out of expected range [0, 200]")
    
    return True, {"temp": temp, "rh": rh, "ws": ws}, warnings
