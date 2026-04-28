import pandas as pd
from datetime import datetime

file_path = "data/charlotte_polo_properties.csv"

df = pd.read_csv(file_path)

# Example: update last_seen for all rows
df["last_seen"] = datetime.now().strftime("%Y-%m-%d")

df.to_csv(file_path, index=False)