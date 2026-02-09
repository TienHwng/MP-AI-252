import numpy as np
import tensorflow as tf

# ==============================
# 🧠 NHẬP DỮ LIỆU ĐỂ TEST THỦ CÔNG
# ==============================
temp = input("Enter temperature (°C): ")      # 🌡️ Nhiệt độ (°C)
temp = float(temp)
humi = input("Enter humidity (%): ")      # 💧 Độ ẩm (%)
humi = float(humi)
# ==============================

MODEL_PATH = "trained models/dht_anomaly_model.tflite"

# --- Load model ---
interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# --- Chuẩn bị input ---
input_data = np.array([[temp, humi]], dtype=np.float32)

# --- Chạy inference ---
interpreter.set_tensor(input_details[0]['index'], input_data)
interpreter.invoke()
output_data = interpreter.get_tensor(output_details[0]['index'])
prob = float(output_data[0][0])

# --- In kết quả ---
print(f"🌡️  Temperature: {temp:.2f} °C")
print(f"💧 Humidity: {humi:.2f} %")
print(f"📊 Model output (probability): {prob:.4f}")

if prob > 0.5:
    print("🚨 Prediction: ABNORMAL")
else:
    print("✅ Prediction: NORMAL")