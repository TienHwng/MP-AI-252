import csv
import random

OUTPUT_FILE = "data/dht_anomaly_dataset_1000.csv"

num_normal = 800     # bình thường
num_anomaly = 200    # bất thường

# Vùng bình thường
normal_temp_range = (25, 35)
normal_humid_range = (60, 80)

# Vùng bất thường (toàn khoảng)
anomaly_temp_range = (10, 50)
anomaly_humid_range = (20, 100)

with open(OUTPUT_FILE, "w", newline="") as f:
    writer = csv.writer(f)

    # NORMAL (label = 0)
    for _ in range(num_normal):
        temp  = int(random.uniform(*normal_temp_range))
        humid = int(random.uniform(*normal_humid_range))
        writer.writerow([temp, humid, 0])

    # ANOMALY (label = 1)
    for _ in range(num_anomaly):
        while True:
            temp  = int(random.uniform(*anomaly_temp_range))
            humid = int(random.uniform(*anomaly_humid_range))

            # Nếu KHÔNG nằm trong vùng bình thường → anomaly
            if not (normal_temp_range[0] <= temp <= normal_temp_range[1] and
                    normal_humid_range[0] <= humid <= normal_humid_range[1]):
                writer.writerow([temp, humid, 1])
                break

print("✔ Đã tạo file:", OUTPUT_FILE)
