import os
import pandas as pd
from sklearn.model_selection import train_test_split
import tensorflow as tf
import data_cleaner  # Ensure data is cleaned before training

# Define file prefix name
PREFIX = "dht_anomaly_model"

# Define paths
DATA_DIR 		= "data"
OUTPUT_DIR 		= "trained models"
INPUT_FILE 		= os.path.join(DATA_DIR, "tinyml_training_data_hcmc.csv")
OUTPUT_TFLITE 	= os.path.join(OUTPUT_DIR, PREFIX + ".tflite")
OUTPUT_HEADER 	= os.path.join(OUTPUT_DIR, PREFIX + ".h")
OUTPUT_KERAS 	= os.path.join(OUTPUT_DIR, PREFIX + ".keras")
# Load data
data = pd.read_csv(INPUT_FILE, names=["temp", "humidity", "label"])
X = data[["temp", "humidity"]].values
y = data["label"].values

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# Simple classifier model
model = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(2,)),
    tf.keras.layers.Dense(8, activation='relu'),
    tf.keras.layers.Dense(1, activation='sigmoid')
])

model.compile(loss="binary_crossentropy", optimizer="adam", metrics=["accuracy"])
model.fit(X_train, y_train, epochs=500, validation_data=(X_test, y_test))
model.save(OUTPUT_KERAS)

# Convert to TFLite
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()

with open(OUTPUT_TFLITE, "wb") as f:
    f.write(tflite_model)

# Convert to .h
with open(OUTPUT_TFLITE, 'rb') as tflite_file:
    tflite_content = tflite_file.read()

hex_lines = [
    ', '.join([f'0x{byte:02x}' for byte in tflite_content[i:i + 12]])
    for i in range(0, len(tflite_content), 12)
]

hex_array = ',\n    '.join(hex_lines)

with open(OUTPUT_HEADER, 'w') as header_file:
    # You can change the variable name 'dht_anomaly_model_tflite' if needed
    header_file.write('const unsigned char ')
    header_file.write(PREFIX + '_tflite' + '[] = {\n    ')
    header_file.write(f'{hex_array}\n')
    header_file.write('};\n\n')

print("Saved files:")
print(" - Keras model:", OUTPUT_KERAS)
print(" - TFLite model:", OUTPUT_TFLITE)
print(" - Header file:", OUTPUT_HEADER)
