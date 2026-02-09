"""
all_plots_dht_anomaly_model.py

Evaluate TinyML anomaly model with multiple metrics and advanced visualizations.

- Loads trained Keras model (.keras)
- Loads HCMC dataset CSV
- Evaluates over multiple random train/test splits
- Computes accuracy, precision, recall, F1
- Generates and SAVES many plots into the "plots" folder:

  1) Metric curves over runs
  2) Metric mean ± std bar chart
  3) Confusion matrix heatmaps (counts + normalized) for one reference run
  4) ROC curve + AUC for the anomaly class
  5) Precision–Recall curve + Average Precision
  6) Threshold sweep: Accuracy / Precision / Recall / F1 vs threshold
  7) Probability histograms for normal vs anomaly
  8) Reliability (calibration) diagram
  9) Metric distributions across runs (boxplot + histograms)
 10) 2D decision boundary over (temperature, humidity)
 11) 3D probability surface over (temperature, humidity)
 12) 3D scatter of (temperature, humidity, predicted probability)
 13) Inference time distribution for single-sample predictions
 14) Model size comparison (.keras, .tflite, .h)

Make sure you have:
- data/tinyml_training_data_hcmc.csv
- trained models/dht_anomaly_model.keras
(optionally)
- trained models/dht_anomaly_model.tflite
- trained models/dht_anomaly_model.h
"""

import os
import time
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    confusion_matrix,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_curve,
    roc_auc_score,
    precision_recall_curve,
    average_precision_score,
)

import tensorflow as tf
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  # needed for 3D projection


# =========================
#  Config paths
# =========================

PREFIX = "dht_anomaly_model"

DATA_DIR = "data"
MODEL_DIR = "trained models"
PLOTS_DIR = "plots/detail plots 5000"  # folder to save images

CSV_PATH = os.path.join(DATA_DIR, "tinyml_training_data_hcmc.csv")
KERAS_MODEL_PATH = os.path.join(MODEL_DIR, PREFIX + ".keras")
TFLITE_MODEL_PATH = os.path.join(MODEL_DIR, PREFIX + ".tflite")
HEADER_PATH = os.path.join(MODEL_DIR, PREFIX + ".h")

TEST_SIZE = 0.2                # 20% test
RANDOM_STATES = range(1, 5000)  # 1, 2, ..., 99  (you can change this)


# =========================
#  Data & IO helpers
# =========================

def load_data(csv_path: str):
    """Load dataset from CSV (no header)."""
    df = pd.read_csv(csv_path, header=None)
    X = df[[0, 1]].values.astype(np.float32)  # temp, humidity
    y = df[2].values.astype(np.int32)         # label: 0 = normal, 1 = anomaly
    return X, y


def ensure_plots_dir(path: str):
    """Create the plots directory if it does not already exist."""
    os.makedirs(path, exist_ok=True)


# =========================
#  Basic metric plots (multi-run)
# =========================

def plot_metric_curves(all_acc, all_prec, all_rec, all_f1, out_dir: str):
    """Save metric values across random_state runs as line plots."""
    runs = np.arange(1, len(all_acc) + 1)

    # Accuracy curve
    plt.figure()
    plt.plot(runs, all_acc)
    plt.xlabel("Run index")
    plt.ylabel("Accuracy")
    plt.title("Accuracy over random train/test splits")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "accuracy_curve.png"))
    plt.close()

    # Precision curve
    plt.figure()
    plt.plot(runs, all_prec)
    plt.xlabel("Run index")
    plt.ylabel("Precision (anomaly)")
    plt.title("Precision (anomaly) over random train/test splits")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "precision_curve.png"))
    plt.close()

    # Recall curve
    plt.figure()
    plt.plot(runs, all_rec)
    plt.xlabel("Run index")
    plt.ylabel("Recall (anomaly)")
    plt.title("Recall (anomaly) over random train/test splits")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "recall_curve.png"))
    plt.close()

    # F1 curve
    plt.figure()
    plt.plot(runs, all_f1)
    plt.xlabel("Run index")
    plt.ylabel("F1-score (anomaly)")
    plt.title("F1-score (anomaly) over random train/test splits")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "f1_curve.png"))
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
    plt.bar(x, values, yerr=stds, capsize=5)
    plt.xticks(x, metrics, rotation=15)
    plt.ylim(0.0, 1.0)
    plt.ylabel("Score")
    plt.title("TinyML anomaly model performance\n(mean ± std over random splits)")
    plt.grid(True, axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "metrics_mean_std.png"))
    plt.close()


# =========================
#  Confusion matrix & ROC/PR
# =========================

def plot_confusion_matrices(cm, out_dir: str, prefix: str = "ref_run"):
    """Plot confusion matrix (counts + normalized)."""
    class_names = ["Normal (0)", "Anomaly (1)"]

    # Raw counts
    plt.figure()
    plt.imshow(cm, interpolation="nearest")
    plt.title("Confusion matrix (counts)")
    plt.colorbar()
    tick_marks = np.arange(len(class_names))
    plt.xticks(tick_marks, class_names, rotation=45)
    plt.yticks(tick_marks, class_names)

    thresh = cm.max() / 2.0 if cm.max() > 0 else 0.5
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            plt.text(
                j,
                i,
                format(cm[i, j], "d"),
                horizontalalignment="center",
                color="white" if cm[i, j] > thresh else "black",
            )

    plt.ylabel("True label")
    plt.xlabel("Predicted label")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"{prefix}_confusion_matrix_counts.png"))
    plt.close()

    # Normalized (per true class)
    with np.errstate(all="ignore"):
        cm_norm = cm.astype(np.float32) / cm.sum(axis=1, keepdims=True)
        cm_norm = np.nan_to_num(cm_norm)

    plt.figure()
    plt.imshow(cm_norm, interpolation="nearest", vmin=0.0, vmax=1.0)
    plt.title("Confusion matrix (normalized)")
    plt.colorbar()
    plt.xticks(tick_marks, class_names, rotation=45)
    plt.yticks(tick_marks, class_names)

    for i in range(cm_norm.shape[0]):
        for j in range(cm_norm.shape[1]):
            plt.text(
                j,
                i,
                f"{cm_norm[i, j]:.2f}",
                horizontalalignment="center",
                color="white" if cm_norm[i, j] > 0.5 else "black",
            )

    plt.ylabel("True label")
    plt.xlabel("Predicted label")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"{prefix}_confusion_matrix_normalized.png"))
    plt.close()


def plot_roc_pr_curves(y_true, y_proba, out_dir: str, prefix: str = "ref_run"):
    """Plot ROC and Precision-Recall curves."""
    # ROC
    fpr, tpr, _ = roc_curve(y_true, y_proba)
    roc_auc = roc_auc_score(y_true, y_proba)

    plt.figure()
    plt.plot(fpr, tpr, label=f"ROC curve (AUC = {roc_auc:.3f})")
    plt.plot([0, 1], [0, 1], linestyle="--")
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("ROC curve (anomaly class = 1)")
    plt.legend(loc="lower right")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"{prefix}_roc_curve.png"))
    plt.close()

    # Precision-Recall
    precision, recall, _ = precision_recall_curve(y_true, y_proba)
    ap = average_precision_score(y_true, y_proba)

    plt.figure()
    plt.plot(recall, precision, label=f"PR curve (AP = {ap:.3f})")
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("Precision-Recall curve (anomaly class = 1)")
    plt.legend(loc="lower left")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"{prefix}_pr_curve.png"))
    plt.close()


# =========================
#  Threshold sweep
# =========================

def plot_threshold_sweep(y_true, y_proba, out_path: str):
    """Plot Accuracy / Precision / Recall / F1 as a function of threshold."""
    thresholds = np.linspace(0.0, 1.0, 201)
    accs, precs, recs, f1s = [], [], [], []

    for thr in thresholds:
        y_pred = (y_proba >= thr).astype(np.int32)

        accs.append(accuracy_score(y_true, y_pred))
        precs.append(precision_score(y_true, y_pred, zero_division=0))
        recs.append(recall_score(y_true, y_pred, zero_division=0))
        f1s.append(f1_score(y_true, y_pred, zero_division=0))

    plt.figure(figsize=(8, 6))
    plt.plot(thresholds, accs, label="Accuracy")
    plt.plot(thresholds, precs, label="Precision")
    plt.plot(thresholds, recs, label="Recall")
    plt.plot(thresholds, f1s, label="F1-score")
    plt.xlabel("Threshold")
    plt.ylabel("Metric value")
    plt.title("Metric vs threshold (anomaly class = 1)")
    plt.xlim(0.0, 1.0)
    plt.ylim(0.0, 1.05)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


# =========================
#  Probability distributions & calibration
# =========================

def plot_probability_histograms(y_true, y_proba, out_path: str):
    """Histogram of predicted probabilities for normal vs anomaly."""
    y_true = np.asarray(y_true)
    y_proba = np.asarray(y_proba)

    normal_probs = y_proba[y_true == 0]
    anomaly_probs = y_proba[y_true == 1]

    plt.figure(figsize=(8, 6))
    bins = np.linspace(0.0, 1.0, 25)
    plt.hist(normal_probs, bins=bins, alpha=0.6, label="Normal (label=0)")
    plt.hist(anomaly_probs, bins=bins, alpha=0.6, label="Anomaly (label=1)")
    plt.xlabel("Predicted anomaly probability")
    plt.ylabel("Count")
    plt.title("Probability distribution by class")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def plot_reliability_diagram(y_true, y_proba, out_path: str, n_bins: int = 10):
    """Reliability (calibration) diagram: predicted prob vs actual freq."""
    y_true = np.asarray(y_true)
    y_proba = np.asarray(y_proba)

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_centers = (bins[:-1] + bins[1:]) / 2.0

    actual = []
    predicted = []

    for i in range(n_bins):
        left, right = bins[i], bins[i + 1]
        mask = (y_proba >= left) & (y_proba < right)
        if np.any(mask):
            predicted.append(y_proba[mask].mean())
            actual.append(y_true[mask].mean())

    if len(predicted) == 0:
        print("No data for reliability diagram (all probabilities were NaN?).")
        return

    plt.figure(figsize=(6, 6))
    plt.plot([0, 1], [0, 1], linestyle="--", label="Perfect calibration")
    plt.plot(predicted, actual, marker="o", label="Model")
    plt.xlabel("Predicted probability (bin mean)")
    plt.ylabel("Actual frequency of anomaly")
    plt.title("Reliability diagram (anomaly class = 1)")
    plt.xlim(0.0, 1.0)
    plt.ylim(0.0, 1.0)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


# =========================
#  Metric distributions across runs
# =========================

def plot_metric_distributions(all_acc, all_prec, all_rec, all_f1, out_dir: str):
    """Boxplot + histograms for metric distributions over runs."""
    metrics = ["Accuracy", "Precision", "Recall", "F1"]
    all_metrics = [np.array(all_acc), np.array(all_prec), np.array(all_rec), np.array(all_f1)]

    # Boxplot
    plt.figure(figsize=(8, 6))
    plt.boxplot(all_metrics, labels=metrics, showmeans=True)
    plt.ylabel("Score")
    plt.title("Metric distributions over random splits")
    plt.grid(True, axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "metrics_boxplot.png"))
    plt.close()

    # Histograms
    plt.figure(figsize=(10, 8))
    for idx, (name, values) in enumerate(zip(metrics, all_metrics), start=1):
        plt.subplot(2, 2, idx)
        plt.hist(values, bins=15)
        plt.title(name)
        plt.xlabel("Score")
        plt.ylabel("Count")
        plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "metrics_histograms.png"))
    plt.close()


# =========================
#  2D decision boundary
# =========================

def plot_decision_boundary_2d(model, X, y, out_path: str):
    """2D decision boundary over (temp, humidity) with data points."""
    X = np.asarray(X)
    y = np.asarray(y)

    temp = X[:, 0]
    humid = X[:, 1]

    temp_min, temp_max = temp.min() - 1.0, temp.max() + 1.0
    humid_min, humid_max = humid.min() - 1.0, humid.max() + 1.0

    grid_temp, grid_humid = np.meshgrid(
        np.linspace(temp_min, temp_max, 200),
        np.linspace(humid_min, humid_max, 200),
    )
    grid_points = np.c_[grid_temp.ravel(), grid_humid.ravel()]

    grid_proba = model.predict(grid_points, verbose=0).reshape(grid_temp.shape)

    plt.figure(figsize=(8, 6))
    # Background: probability of anomaly
    cs = plt.contourf(grid_temp, grid_humid, grid_proba, levels=30, alpha=0.8)
    plt.colorbar(cs, label="Predicted anomaly probability")

    # Decision boundary at 0.5
    plt.contour(grid_temp, grid_humid, grid_proba, levels=[0.5], linewidths=2)

    # Scatter real data
    normal_mask = (y == 0)
    anomaly_mask = (y == 1)

    plt.scatter(temp[normal_mask], humid[normal_mask], s=10, label="Normal (0)")
    plt.scatter(temp[anomaly_mask], humid[anomaly_mask], s=20, marker="x", label="Anomaly (1)")

    plt.xlabel("Temperature")
    plt.ylabel("Humidity")
    plt.title("2D decision boundary over (temp, humidity)")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


# =========================
#  3D plots
# =========================

def plot_3d_probability_surface(model, X, out_path: str):
    """3D surface: temp (x), humidity (y), predicted anomaly probability (z)."""
    X = np.asarray(X)
    temp = X[:, 0]
    humid = X[:, 1]

    temp_min, temp_max = temp.min() - 1.0, temp.max() + 1.0
    humid_min, humid_max = humid.min() - 1.0, humid.max() + 1.0

    grid_temp, grid_humid = np.meshgrid(
        np.linspace(temp_min, temp_max, 60),
        np.linspace(humid_min, humid_max, 60),
    )
    grid_points = np.c_[grid_temp.ravel(), grid_humid.ravel()]
    grid_proba = model.predict(grid_points, verbose=0).reshape(grid_temp.shape)

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")

    ax.plot_surface(grid_temp, grid_humid, grid_proba, linewidth=0, antialiased=True, alpha=0.8)

    ax.set_xlabel("Temperature")
    ax.set_ylabel("Humidity")
    ax.set_zlabel("Anomaly probability")
    ax.set_title("3D surface: anomaly probability over (temp, humidity)")

    plt.tight_layout()
    plt.savefig(out_path)
    plt.close(fig)


def plot_3d_scatter_prob(X, y_true, y_proba, out_path: str):
    """3D scatter: temp (x), humidity (y), predicted probability (z)."""
    X = np.asarray(X)
    y_true = np.asarray(y_true)
    y_proba = np.asarray(y_proba)

    temp = X[:, 0]
    humid = X[:, 1]

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")

    normal_mask = (y_true == 0)
    anomaly_mask = (y_true == 1)

    ax.scatter(temp[normal_mask], humid[normal_mask], y_proba[normal_mask], s=15, label="Normal (0)")
    ax.scatter(temp[anomaly_mask], humid[anomaly_mask], y_proba[anomaly_mask], s=25, marker="x", label="Anomaly (1)")

    ax.set_xlabel("Temperature")
    ax.set_ylabel("Humidity")
    ax.set_zlabel("Predicted anomaly probability")
    ax.set_title("3D scatter: prob vs (temp, humidity)")

    ax.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close(fig)


# =========================
#  Inference time & model size
# =========================

def measure_inference_times(model, X, n_runs: int = 200):
    """Measure single-sample inference times (ms) for random samples from X."""
    X = np.asarray(X)
    n_samples = X.shape[0]
    indices = np.random.randint(0, n_samples, size=n_runs)

    times_ms = []

    # Warm-up (to avoid first-call overhead)
    _ = model.predict(X[indices[0:1]], verbose=0)

    for idx in indices:
        sample = X[idx:idx + 1]
        t0 = time.perf_counter()
        _ = model.predict(sample, verbose=0)
        t1 = time.perf_counter()
        times_ms.append((t1 - t0) * 1000.0)

    return np.array(times_ms)


def plot_inference_time_distribution(times_ms, out_dir: str):
    """Plot histogram + boxplot of inference times."""
    times_ms = np.asarray(times_ms)

    plt.figure(figsize=(8, 6))
    plt.hist(times_ms, bins=20)
    plt.xlabel("Inference time (ms)")
    plt.ylabel("Count")
    plt.title("Single-sample inference time distribution")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "inference_time_hist.png"))
    plt.close()

    plt.figure(figsize=(6, 6))
    plt.boxplot(times_ms, vert=True, showmeans=True)
    plt.ylabel("Inference time (ms)")
    plt.title("Inference time boxplot")
    plt.grid(True, axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "inference_time_boxplot.png"))
    plt.close()


def plot_model_size_bar_chart(keras_path, tflite_path, header_path, out_path: str):
    """Bar chart comparing model file sizes (.keras, .tflite, .h) in KB."""
    names = []
    sizes_kb = []

    def add_if_exists(path, label):
        if os.path.exists(path):
            names.append(label)
            sizes_kb.append(os.path.getsize(path) / 1024.0)
        else:
            print(f"[WARN] File not found, skipping size plot entry: {path}")

    add_if_exists(keras_path, "Keras (.keras)")
    add_if_exists(tflite_path, "TFLite (.tflite)")
    add_if_exists(header_path, "Header (.h)")

    if not names:
        print("No model files found for size comparison.")
        return

    x = np.arange(len(names))
    plt.figure(figsize=(8, 6))
    plt.bar(x, sizes_kb)
    plt.xticks(x, names, rotation=15)
    plt.ylabel("Size (KB)")
    plt.title("Model file size comparison")
    plt.grid(True, axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


# =========================
#  Main evaluation
# =========================

def main():
    # 1. Prepare plots directory
    ensure_plots_dir(PLOTS_DIR)

    # 2. Load data
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"CSV dataset not found: {CSV_PATH}")

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

    # For "reference run" advanced plots (ROC, PR, etc.)
    ref_X_test = None
    ref_y_test = None
    ref_y_proba = None
    ref_cm = None

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
        y_proba = model.predict(X_test, verbose=0).reshape(-1)

        # Convert to binary using fixed threshold
        threshold = 0.5
        y_pred = (y_proba >= threshold).astype(np.int32)

        # Metrics
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
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

        # Save the first run as reference for detailed plots
        if ref_X_test is None:
            ref_X_test = X_test.copy()
            ref_y_test = y_test.copy()
            ref_y_proba = y_proba.copy()
            ref_cm = cm.copy()

    # 5. Summary over all runs
    def summary(name, values):
        values = np.array(values)
        return f"{name}: mean = {values.mean():.4f}, std = {values.std():.4f}"

    print("\n=== Summary over random_state runs ===")
    print(summary("Accuracy", all_acc))
    print(summary("Precision (anomaly)", all_prec))
    print(summary("Recall (anomaly)", all_rec))
    print(summary("F1-score (anomaly)", all_f1))

    # 6. Save basic metric plots
    plot_metric_curves(all_acc, all_prec, all_rec, all_f1, PLOTS_DIR)
    plot_metric_summary(all_acc, all_prec, all_rec, all_f1, PLOTS_DIR)

    # 7. Advanced plots using reference run
    if ref_X_test is not None:
        # Confusion matrices
        plot_confusion_matrices(ref_cm, PLOTS_DIR, prefix="ref_run")

        # ROC + PR curves
        plot_roc_pr_curves(ref_y_test, ref_y_proba, PLOTS_DIR, prefix="ref_run")

        # Threshold sweep
        plot_threshold_sweep(
            ref_y_test,
            ref_y_proba,
            os.path.join(PLOTS_DIR, "ref_run_threshold_sweep.png"),
        )

        # Probability histograms
        plot_probability_histograms(
            ref_y_test,
            ref_y_proba,
            os.path.join(PLOTS_DIR, "ref_run_probability_hist.png"),
        )

        # Reliability diagram
        plot_reliability_diagram(
            ref_y_test,
            ref_y_proba,
            os.path.join(PLOTS_DIR, "ref_run_reliability.png"),
        )

        # 3D scatter for test set
        plot_3d_scatter_prob(
            ref_X_test,
            ref_y_test,
            ref_y_proba,
            os.path.join(PLOTS_DIR, "ref_run_3d_scatter_prob.png"),
        )

    else:
        print("[WARN] No reference run data collected; skipping ref-run plots.")

    # 8. Metric distributions across runs
    plot_metric_distributions(all_acc, all_prec, all_rec, all_f1, PLOTS_DIR)

    # 9. 2D decision boundary & 3D surface (use all data X, y)
    plot_decision_boundary_2d(
        model,
        X,
        y,
        os.path.join(PLOTS_DIR, "decision_boundary_2d.png"),
    )

    plot_3d_probability_surface(
        model,
        X,
        os.path.join(PLOTS_DIR, "probability_surface_3d.png"),
    )

    # 10. Inference time distribution (single-sample)
    times_ms = measure_inference_times(model, X, n_runs=200)
    print(
        f"\nInference time stats (single-sample, ms): "
        f"mean={times_ms.mean():.4f}, "
        f"std={times_ms.std():.4f}, "
        f"min={times_ms.min():.4f}, "
        f"p95={np.percentile(times_ms, 95):.4f}"
    )
    plot_inference_time_distribution(times_ms, PLOTS_DIR)

    # 11. Model size comparison
    plot_model_size_bar_chart(
        KERAS_MODEL_PATH,
        TFLITE_MODEL_PATH,
        HEADER_PATH,
        os.path.join(PLOTS_DIR, "model_size_comparison.png"),
    )

    print(f'\nAll plots saved to folder: "{PLOTS_DIR}"')


if __name__ == "__main__":
    main()
