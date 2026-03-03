import csv, os, datetime

def log_to_csv(data):
    # Log everything to a single master file as requested
    filename = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "air_quality.csv")

    file_exists = os.path.exists(filename)

    with open(filename, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "CO","Gas","Temp","Humidity","Pressure","Oxygen","Alert","Escape_Time"
            ])
        writer.writerow(data)