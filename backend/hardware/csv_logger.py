import csv, os, datetime

def log_to_csv(data, env_mode="BUILDING"):
    # Log to separate files for Building and Vehicle to allow independent training
    suffix = "building" if env_mode.upper() == "BUILDING" else "vehicle"
    filename = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", f"air_quality_{suffix}.csv")

    file_exists = os.path.exists(filename)
    
    # Ensure data directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    with open(filename, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "CO","Gas","Temp","Humidity","Pressure","Oxygen","Alert","Escape_Time"
            ])
        writer.writerow(data)