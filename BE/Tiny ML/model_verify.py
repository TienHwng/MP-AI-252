"""
multi_eval_dht_anomaly_model_saveplots.py

Evaluate the TinyML anomaly model over multiple random train/test splits
and SAVE the metric plots as image files into a folder.

- Loads the trained Keras model (.keras)
- Loads the HCMC dataset CSV
- For several random_state values, splits into train/test
- Computes accuracy, precision, recall, and F1-score on the test set
- Prints per-run metrics and overall mean / std
- Saves:
  * Line plots of metrics across runs
  * Bar chart of mean metrics with error bars
into a "plots" folder.
"""

import os
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    confusion_matrix,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)
import tensorflow as tf
import matplotlib.pyplot as plt


# =========================
#  Config paths
# =========================

DATA_DIR = "data"
MODEL_DIR = "trained models"
PLOTS_DIR = "plots"  # folder to save images

CSV_PATH = os.path.join(DATA_DIR, "tinyml_training_data_hcmc.csv")
KERAS_MODEL_PATH = os.path.join(MODEL_DIR, "dht_anomaly_model.keras")

TEST_SIZE = 0.2                # 20% test
RANDOM_STATES = range(1, 100)  # 1, 2, ..., 1000


def load_data(csv_path: str):
    """Load dataset from CSV (no header)."""
    df = pd.read_csv(csv_path, header=None)
    X = df[[0, 1]].values.astype(np.float32)  # temp, humidity
    y = df[2].values.astype(np.int32)         # label: 0 = normal, 1 = anomaly
    return X, y


def ensure_plots_dir(path: str):
    """Create the plots directory if it does not already exist."""
    os.makedirs(path, exist_ok=True)


def plot_metric_curves(all_acc, all_prec, all_rec, all_f1, out_dir: str):
    """Save metric values across random_state runs as line plots."""
    runs = np.arange(1, len(all_acc) + 1)

    # Accuracy curve
    plt.figure()
    plt.plot(runs, all_acc)
    plt.xlabel("Run index")
    plt.ylabel("Accuracy")
    plt.title("Accuracy over random train/test splits")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "accuracy_over_splits.png"))
    plt.close()

    # Precision curve (anomaly)
    plt.figure()
    plt.plot(runs, all_prec)
    plt.xlabel("Run index")
    plt.ylabel("Precision (anomaly)")
    plt.title("Precision for anomaly class over random splits")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "precision_over_splits.png"))
    plt.close()

    # Recall curve (anomaly)
    plt.figure()
    plt.plot(runs, all_rec)
    plt.xlabel("Run index")
    plt.ylabel("Recall (anomaly)")
    plt.title("Recall for anomaly class over random splits")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "recall_over_splits.png"))
    plt.close()

    # F1-score curve (anomaly)
    plt.figure()
    plt.plot(runs, all_f1)
    plt.xlabel("Run index")
    plt.ylabel("F1-score (anomaly)")
    plt.title("F1-score for anomaly class over random splits")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "f1_over_splits.png"))
    plt.close()


def plot_metric_summary(all_acc, all_prec, all_rec, all_f1, out_dir: str):
    """Save bar chart of mean metrics with std as error bars."""
    metrics = ["Accuracy", "Precision (abn)", "Recall (abn)", "F1 (abn)"]
    values = np.array([
        np.mean(all_acc),
        np.mean(all_prec),
        np.mean(all_rec),
        np.mean(all_f1),
    ])
    stds = np.array([
        np.std(all_acc),
        np.std(all_prec),
        np.std(all_rec),
        np.std(all_f1),
    ])

    x = np.arange(len(metrics))

    plt.figure()
    plt.bar(x, values, yerr=stds)
    plt.xticks(x, metrics, rotation=15)
    plt.ylim(0.0, 1.0)
    plt.ylabel("Score")
    plt.title("TinyML anomaly model performance\n(mean ± std over random splits)")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "metrics_mean_std.png"))
    plt.close()


def main():
    # 1. Prepare plots directory
    ensure_plots_dir(PLOTS_DIR)

    # 2. Load data
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"CSV file not found: {CSV_PATH}")

    print(f"Loading dataset from: {CSV_PATH}")
    X, y = load_data(CSV_PATH)
    print(f"Dataset shape: X = {X.shape}, y = {y.shape}")
    print(f"Label distribution: {np.bincount(y)} (index = class label)")

    # 3. Load trained Keras model once
    if not os.path.exists(KERAS_MODEL_PATH):
        raise FileNotFoundError(f"Keras model not found: {KERAS_MODEL_PATH}")

    print(f"\nLoading Keras model from: {KERAS_MODEL_PATH}")
    model = tf.keras.models.load_model(KERAS_MODEL_PATH)

    # 4. Loop over multiple random_state values
    all_acc = []
    all_prec = []
    all_rec = []
    all_f1 = []

    for idx, rs in enumerate(RANDOM_STATES, start=1):
        print(f"\n=== Evaluation run {idx} with random_state = {rs} ===")

        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=TEST_SIZE,
            random_state=rs,
            stratify=y,
        )

        # Predict probabilities
        y_proba = model.predict(X_test).reshape(-1)

        # Convert to binary using fixed threshold
        threshold = 0.5
        y_pred = (y_proba >= threshold).astype(np.int32)

        # Metrics
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred)
        rec = recall_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)
        cm = confusion_matrix(y_test, y_pred)

        all_acc.append(acc)
        all_prec.append(prec)
        all_rec.append(rec)
        all_f1.append(f1)

        print("Confusion matrix (rows = true, cols = pred):")
        print(cm)
        print(f"Accuracy : {acc:.4f}")
        print(f"Precision: {prec:.4f} (anomaly class = 1)")
        print(f"Recall   : {rec:.4f} (anomaly class = 1)")
        print(f"F1-score : {f1:.4f} (anomaly class = 1)")

    # 5. Summary over all runs
    def summary(name, values):
        values = np.array(values)
        return f"{name}: mean = {values.mean():.4f}, std = {values.std():.4f}"

    print("\n=== Summary over random_state runs ===")
    print(summary("Accuracy", all_acc))
    print(summary("Precision (anomaly)", all_prec))
    print(summary("Recall (anomaly)", all_rec))
    print(summary("F1-score (anomaly)", all_f1))

    # 6. Save metric curves and summary plots
    plot_metric_curves(all_acc, all_prec, all_rec, all_f1, PLOTS_DIR)
    plot_metric_summary(all_acc, all_prec, all_rec, all_f1, PLOTS_DIR)

    print(f'\nAll plots saved to folder: "{PLOTS_DIR}"')


if __name__ == "__main__":
    main()
