"""
Predictive TinyML — ML Model Comparison Pipeline
==================================================
Trains and compares multiple ML models for next-value prediction
of (temperature, humidity) tabular time series on ESP32-S3:

  1. Dense (MLP)              — neural network baseline (TFLite-deployable)
  2. Random Forest             — ensemble of decision trees
  3. Gradient Boosting         — sequential boosted trees
  4. Support Vector Regression — kernel-based regression
  5. K-Nearest Neighbors       — instance-based learning
  6. Ridge Regression          — regularised linear baseline

Classical ML models serve as benchmarks.  The MLP is the only model
that can be converted to TFLite for on-device deployment on ESP32-S3.

Usage:
    cd backend/"Tiny ML"
    python predictive_model.py
"""

import os
import time

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.svm import SVR
from sklearn.neighbors import KNeighborsRegressor
from sklearn.linear_model import Ridge
from sklearn.multioutput import MultiOutputRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error
import tensorflow as tf

# ── Config ────────────────────────────────────────────────────

WINDOW_SIZE = 10          # number of past readings in sliding window
FEATURES = 2              # temperature, humidity
EPOCHS = 300
BATCH_SIZE = 32
RANDOM_STATE = 42

DATA_DIR = "data"
OUTPUT_DIR = "trained models"
TRAINING_DATA = os.path.join(DATA_DIR, "HCMC_temp_humid_raw.csv")

# ── Data loading & normalization ──────────────────────────────

def load_and_normalize(path: str):
    """Load CSV (temp, humidity, label) and Z-score normalize."""
    df = pd.read_csv(path, names=["temp", "humidity", "label"])
    df_normal = df[df["label"] == 0].reset_index(drop=True)
    print(f"[Data] Total rows: {len(df)}, Normal rows: {len(df_normal)}")

    values = df_normal[["temp", "humidity"]].values.astype(np.float32)

    temp_mean, temp_std = values[:, 0].mean(), values[:, 0].std()
    humi_mean, humi_std = values[:, 1].mean(), values[:, 1].std()

    normalized = np.zeros_like(values)
    normalized[:, 0] = (values[:, 0] - temp_mean) / (temp_std + 1e-7)
    normalized[:, 1] = (values[:, 1] - humi_mean) / (humi_std + 1e-7)

    stats = {
        "temp_mean": temp_mean, "temp_std": temp_std,
        "humi_mean": humi_mean, "humi_std": humi_std,
    }
    return normalized, stats


def create_sequences(data: np.ndarray, window: int):
    """Sliding-window: X[i] = data[i:i+window], y[i] = data[i+window]."""
    X, y = [], []
    for i in range(len(data) - window):
        X.append(data[i : i + window])
        y.append(data[i + window])
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


# ── MLP (Dense) — the only TFLite-deployable model ───────────

def build_dense():
    """MLP: Flatten → Dense(20) → Dense(16) → Dense(8) → Dense(2)."""
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(WINDOW_SIZE, FEATURES)),
        tf.keras.layers.Flatten(),
        tf.keras.layers.Dense(20, activation="relu"),
        tf.keras.layers.Dense(16, activation="relu"),
        tf.keras.layers.Dense(8, activation="relu"),
        tf.keras.layers.Dense(FEATURES),
    ])
    return model


def train_dense(X_train, y_train, X_test, y_test):
    """Train MLP and return (model, metrics_dict, train_time)."""
    model = build_dense()
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss="mse",
        metrics=["mae"],
    )

    print(f"\n{'='*55}")
    print(f"  Training: Dense (MLP)")
    print(f"{'='*55}")
    model.summary()

    t0 = time.perf_counter()
    history = model.fit(
        X_train, y_train,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        validation_data=(X_test, y_test),
        callbacks=[
            tf.keras.callbacks.EarlyStopping(
                patience=30, restore_best_weights=True,
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                factor=0.5, patience=15, min_lr=1e-6,
            ),
        ],
        verbose=1,
    )
    train_time = time.perf_counter() - t0

    loss, mae = model.evaluate(X_test, y_test, verbose=0)
    actual_epochs = len(history.history["loss"])

    return model, {"mse": loss, "mae": mae, "epochs": actual_epochs}, train_time


# ── Sklearn model definitions ─────────────────────────────────

SKLEARN_MODELS = {
    "rf": (
        "Random Forest",
        RandomForestRegressor(
            n_estimators=200,
            max_depth=12,
            min_samples_leaf=4,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
    ),
    "gb": (
        "Gradient Boost",
        MultiOutputRegressor(
            GradientBoostingRegressor(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                random_state=RANDOM_STATE,
            ),
        ),
    ),
    "svr": (
        "SVR (RBF)",
        MultiOutputRegressor(
            SVR(kernel="rbf", C=10.0, epsilon=0.05),
        ),
    ),
    "knn": (
        "KNN",
        KNeighborsRegressor(
            n_neighbors=7,
            weights="distance",
            n_jobs=-1,
        ),
    ),
    "ridge": (
        "Ridge",
        Ridge(alpha=1.0),
    ),
}


def train_sklearn(name, label, model, X_train_flat, y_train, X_test_flat, y_test):
    """Train a sklearn model and return (model, metrics_dict, train_time)."""
    print(f"\n{'='*55}")
    print(f"  Training: {label}")
    print(f"{'='*55}")

    t0 = time.perf_counter()
    model.fit(X_train_flat, y_train)
    train_time = time.perf_counter() - t0

    y_pred = model.predict(X_test_flat)
    mse = mean_squared_error(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)

    print(f"  MSE={mse:.6f}  MAE={mae:.6f}  Time={train_time:.2f}s")
    return model, {"mse": mse, "mae": mae}, train_time


# ── TFLite conversion & export ────────────────────────────────

def convert_to_tflite(model, output_path: str) -> int:
    """Convert Keras model to FP16-quantised TFLite and return size."""
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    tflite_model = converter.convert()
    with open(output_path, "wb") as f:
        f.write(tflite_model)
    return len(tflite_model)


def measure_inference_time(tflite_path: str, X_sample: np.ndarray,
                           n_runs: int = 100) -> float:
    """Measure average TFLite inference time in milliseconds."""
    interpreter = tf.lite.Interpreter(model_path=tflite_path)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()

    sample = X_sample[:1].astype(np.float32)
    for _ in range(10):  # warm-up
        interpreter.set_tensor(input_details[0]["index"], sample)
        interpreter.invoke()

    t0 = time.perf_counter()
    for _ in range(n_runs):
        interpreter.set_tensor(input_details[0]["index"], sample)
        interpreter.invoke()
    return (time.perf_counter() - t0) / n_runs * 1000


def measure_sklearn_inference(model, X_sample_flat: np.ndarray,
                              n_runs: int = 1000) -> float:
    """Measure average sklearn inference time in milliseconds."""
    sample = X_sample_flat[:1]
    for _ in range(10):  # warm-up
        model.predict(sample)

    t0 = time.perf_counter()
    for _ in range(n_runs):
        model.predict(sample)
    return (time.perf_counter() - t0) / n_runs * 1000


def export_tflite_header(tflite_path: str, header_path: str, prefix: str):
    """Convert .tflite binary into a C header for firmware."""
    with open(tflite_path, "rb") as f:
        content = f.read()

    hex_lines = [
        ", ".join(f"0x{b:02x}" for b in content[i : i + 12])
        for i in range(0, len(content), 12)
    ]

    var_name = prefix.replace("-", "_")
    lines = [
        f"// Auto-generated from {prefix}.tflite",
        f"// Model size: {len(content)} bytes",
        f"// Window size: {WINDOW_SIZE}, Features: {FEATURES}",
        "",
        "#ifndef DHT_PREDICTIVE_MODEL_H",
        "#define DHT_PREDICTIVE_MODEL_H",
        "",
        "#include <stdint.h>",
        "",
        f"const unsigned int {var_name}_len = {len(content)};",
        f"alignas(8) const uint8_t {var_name}[] = {{",
    ]
    lines.extend(f"    {hl}," for hl in hex_lines)
    lines.append("};")
    lines.append("")
    lines.append("#endif")

    with open(header_path, "w") as f:
        f.write("\n".join(lines))
    print(f"[Export] C header -> {header_path} ({len(content)} bytes)")


def export_stats(stats: dict, path: str):
    """Save normalization stats for firmware."""
    pd.DataFrame([stats]).to_csv(path, index=False)
    print(f"[Export] Stats -> {path}")


# ── Main ──────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("  Predictive TinyML — ML Model Comparison Pipeline")
    print("=" * 60)

    # ── 1. Data preparation ───────────────────────────────────
    data, stats = load_and_normalize(TRAINING_DATA)
    X, y = create_sequences(data, WINDOW_SIZE)
    print(f"[Data] Sequences: {X.shape[0]}, Window: {WINDOW_SIZE}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE,
    )

    # Flattened views for sklearn (N, 10, 2) -> (N, 20)
    X_train_flat = X_train.reshape(X_train.shape[0], -1)
    X_test_flat = X_test.reshape(X_test.shape[0], -1)

    results = []

    # ── 2. Train Dense (MLP) — TFLite-deployable ─────────────
    tf.keras.backend.clear_session()
    dense_model, dense_metrics, dense_time = train_dense(
        X_train, y_train, X_test, y_test,
    )

    tflite_path = os.path.join(OUTPUT_DIR, "dht_predictive_model.tflite")
    tflite_size = convert_to_tflite(dense_model, tflite_path)
    infer_ms = measure_inference_time(tflite_path, X_test)

    results.append({
        "key": "dense", "label": "Dense (MLP)",
        "params": dense_model.count_params(),
        "mse": dense_metrics["mse"], "mae": dense_metrics["mae"],
        "model_bytes": tflite_size, "infer_ms": infer_ms,
        "train_time_s": dense_time,
        "epochs": dense_metrics.get("epochs", "-"),
        "deployable": True,
    })

    print(f"[Dense (MLP)] MSE={dense_metrics['mse']:.6f} "
          f"MAE={dense_metrics['mae']:.6f} "
          f"Params={dense_model.count_params()} "
          f"TFLite={tflite_size}B")

    # ── 3. Train sklearn models ───────────────────────────────
    for key, (label, sk_model) in SKLEARN_MODELS.items():
        model, metrics, t = train_sklearn(
            key, label, sk_model,
            X_train_flat, y_train, X_test_flat, y_test,
        )

        sk_infer = measure_sklearn_inference(model, X_test_flat)
        import pickle as _pickle
        pkl_size = len(_pickle.dumps(model))

        results.append({
            "key": key, "label": label,
            "params": "-",
            "mse": metrics["mse"], "mae": metrics["mae"],
            "model_bytes": pkl_size, "infer_ms": sk_infer,
            "train_time_s": t,
            "epochs": "-",
            "deployable": False,
        })

        print(f"[{label}] MSE={metrics['mse']:.6f} "
              f"MAE={metrics['mae']:.6f} "
              f"Size={pkl_size}B Infer={sk_infer:.3f}ms")

    # ── 4. Comparison table ───────────────────────────────────
    print("\n" + "=" * 95)
    print("  MODEL COMPARISON (sorted by MSE)")
    print("=" * 95)
    results_sorted = sorted(results, key=lambda r: r["mse"])

    header = (f"{'Model':<18} {'Params':>8} {'MSE':>10} {'MAE':>10} "
              f"{'Size':>10} {'Infer(ms)':>10} {'ESP32?':>7}")
    print(header)
    print("-" * 95)
    for r in results_sorted:
        params_str = str(r["params"]) if r["params"] != "-" else "-"
        esp = "Yes" if r["deployable"] else "No"
        print(f"{r['label']:<18} {params_str:>8} {r['mse']:>10.6f} "
              f"{r['mae']:>10.6f} "
              f"{r['model_bytes']:>8} B {r['infer_ms']:>9.3f} "
              f"{esp:>7}")

    # ── 5. Select best overall & best deployable ──────────────
    best_overall = results_sorted[0]
    best_deploy = min(
        [r for r in results if r["deployable"]],
        key=lambda r: r["mse"],
    )

    print(f"\n  Best overall : {best_overall['label']} "
          f"(MSE={best_overall['mse']:.6f})")
    print(f"  Best for ESP32: {best_deploy['label']} "
          f"(MSE={best_deploy['mse']:.6f})")

    # ── 6. Export MLP to TFLite C header for ESP32 ────────────
    prefix = "dht_predictive_model"
    header_path = os.path.join(OUTPUT_DIR, f"{prefix}.h")
    export_tflite_header(tflite_path, header_path, prefix)

    stats_path = os.path.join(OUTPUT_DIR, f"{prefix}_stats.csv")
    export_stats(stats, stats_path)

    # Save comparison CSV
    comparison_path = os.path.join(OUTPUT_DIR, "model_comparison.csv")
    pd.DataFrame(results_sorted).to_csv(comparison_path, index=False)
    print(f"[Export] Comparison -> {comparison_path}")

    print(f"\n  All {len(results)} models trained and compared.")
    print(f"  MLP deployed to TFLite for ESP32-S3 ({tflite_size} bytes).")


if __name__ == "__main__":
    main()
