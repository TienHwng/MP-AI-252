import os
import pandas as pd

# Define file prefix name
PREFIX = "tinyml_training_data_hcmc"

# Define paths
DATA_DIR 		= "data"
OUTPUT_DIR 		= "trained models"
INPUT_FILE 		= os.path.join(DATA_DIR, "dht_anomaly_dataset_1000.csv")
OUTPUT_FILE 	= os.path.join(OUTPUT_DIR, PREFIX + ".csv")

# Define bounds for anomaly detection
temp_lower_bound        = 25    # minimum value for column 1
temp_upper_bound        = 35    # maximum value for column 1

humidity_lower_bound    = 60    # minimum value for column 2
humidity_upper_bound    = 80    # maximum value for column 2

# Đọc file CSV không có header
df = pd.read_csv(INPUT_FILE, header=None)

# df có 3 cột: 0, 1, 2
# Nếu cột 0 không trong (a < x < b) hoặc cột 1 không trong (c < y < d)
# thì set cột 2 = 1

condition = ( (df[0] <= temp_lower_bound)       | (df[0] >= temp_upper_bound) | 
			  (df[1] <= humidity_lower_bound)   | (df[1] >= humidity_upper_bound) )

df.loc[condition, 2] = 1

# Remove duplicates if any (optional)
# df = df.drop_duplicates(subset=[0, 1], keep="first")

# Lưu lại file
df.to_csv(OUTPUT_FILE, header=False, index=False)

print(f"File saved to {OUTPUT_FILE}")