"""
=============================================================================
Smart Home Behavior Learning - Complete ML Pipeline
=============================================================================
This script:
1. Generates synthetic user behavior data
2. Trains and benchmarks 5 ML models
3. Generates comparison charts and metrics
4. Exports results for LaTeX report

Models benchmarked:
- Logistic Regression (baseline)
- Random Forest
- XGBoost  
- LightGBM
- Neural Network (MLP)

Run: python ml_behavior_learning.py
Output: ./ml_output/ folder with data, models, plots
=============================================================================
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os
import time
import warnings
warnings.filterwarnings('ignore')

# Create output directories - output to current folder (data/, models/, plots/)
OUTPUT_DIR = os.path.dirname(__file__)
os.makedirs(os.path.join(OUTPUT_DIR, 'data'), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, 'models'), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, 'plots'), exist_ok=True)

print(f"Output directory: {OUTPUT_DIR}")

# ===========================================================================
# PART 1: SYNTHETIC DATASET GENERATION
# ===========================================================================

NUM_DAYS = 60  # 2 months of data
USERS = ['dad', 'mom', 'son', 'daughter']
DEVICES = ['living_room_light', 'bedroom_light', 'kitchen_light', 'fan', 'ac']

USER_PROFILES = {
    'dad': {
        'wake_hour': 6, 'sleep_hour': 22,
        'work_start': 8, 'work_end': 18,
        'preferred_brightness': 80, 'preferred_temp': 25,
        'activity_level': 0.7
    },
    'mom': {
        'wake_hour': 6, 'sleep_hour': 23,
        'work_start': 9, 'work_end': 17,
        'preferred_brightness': 70, 'preferred_temp': 24,
        'activity_level': 0.8
    },
    'son': {
        'wake_hour': 7, 'sleep_hour': 24,
        'work_start': 8, 'work_end': 16,
        'preferred_brightness': 100, 'preferred_temp': 22,
        'activity_level': 0.6
    },
    'daughter': {
        'wake_hour': 7, 'sleep_hour': 23,
        'work_start': 8, 'work_end': 16,
        'preferred_brightness': 60, 'preferred_temp': 23,
        'activity_level': 0.5
    }
}

def generate_base_temperature(hour, day_of_year):
    """Generate realistic temperature based on time and season"""
    base = 28  # Tropical climate base
    daily_var = 4 * np.sin((hour - 6) * np.pi / 12) if 6 <= hour <= 18 else -2
    seasonal_var = 2 * np.sin((day_of_year - 80) * 2 * np.pi / 365)
    noise = np.random.normal(0, 1)
    return base + daily_var + seasonal_var + noise

def generate_humidity(temp, hour):
    """Generate humidity inversely correlated with temperature"""
    base = 70 - (temp - 25) * 2
    if hour < 6 or hour > 20:
        base += 10
    return np.clip(base + np.random.normal(0, 5), 40, 95)

def should_user_act(user, hour, day_of_week, temp, humidity):
    """Determine if user is likely to interact with devices"""
    profile = USER_PROFILES[user]
    
    if hour < profile['wake_hour'] or hour >= profile['sleep_hour']:
        return False
    
    is_weekday = day_of_week < 5
    is_work_time = profile['work_start'] <= hour < profile['work_end']
    
    if is_weekday and is_work_time:
        prob = 0.1
    else:
        prob = profile['activity_level']
    
    if temp > 30 or temp < 22:
        prob += 0.2
    
    return np.random.random() < prob

def predict_device_action(user, hour, temp, humidity, current_states):
    """Predict which device user will control"""
    profile = USER_PROFILES[user]
    actions = []
    
    # Light control based on time
    if 6 <= hour < 8:
        actions.append(('living_room_light', 'on', profile['preferred_brightness']))
    elif 18 <= hour < 22:
        actions.append(('living_room_light', 'on', int(profile['preferred_brightness'] * 0.8)))
    elif hour >= 22 or hour < 6:
        actions.append(('bedroom_light', 'on', 30))
    
    # AC/Fan based on temperature
    if temp > 28:
        if temp > 32:
            actions.append(('ac', 'on', profile['preferred_temp']))
        else:
            actions.append(('fan', 'on', 3))
    elif temp < 24:
        actions.append(('ac', 'off', 0))
        actions.append(('fan', 'off', 0))
    
    # Kitchen light during meals
    if hour in [7, 12, 19]:
        actions.append(('kitchen_light', 'on', 90))
    
    if actions:
        return actions[np.random.randint(0, len(actions))]
    return None

def generate_dataset():
    """Generate full synthetic dataset"""
    data = []
    start_date = datetime(2025, 1, 1)
    
    for day in range(NUM_DAYS):
        current_date = start_date + timedelta(days=day)
        day_of_week = current_date.weekday()
        day_of_year = current_date.timetuple().tm_yday
        
        device_states = {d: {'state': 'off', 'value': 0} for d in DEVICES}
        
        for hour in range(24):
            temp = generate_base_temperature(hour, day_of_year)
            humidity = generate_humidity(temp, hour)
            
            for user in USERS:
                if should_user_act(user, hour, day_of_week, temp, humidity):
                    action = predict_device_action(user, hour, temp, humidity, device_states)
                    
                    if action:
                        device, state, value = action
                        
                        if state == 'on' and value > 0:
                            value = int(np.clip(value + np.random.normal(0, 5), 0, 100))
                        
                        data.append({
                            'timestamp': current_date.replace(hour=hour, minute=np.random.randint(0, 60)),
                            'user_id': user,
                            'hour': hour,
                            'minute': np.random.randint(0, 60),
                            'day_of_week': day_of_week,
                            'is_weekend': 1 if day_of_week >= 5 else 0,
                            'temperature': round(temp, 1),
                            'humidity': round(humidity, 1),
                            'device': device,
                            'action': state,
                            'value': value,
                            'light_state': 1 if device_states['living_room_light']['state'] == 'on' else 0,
                            'fan_state': 1 if device_states['fan']['state'] == 'on' else 0,
                            'ac_state': 1 if device_states['ac']['state'] == 'on' else 0,
                        })
                        
                        device_states[device] = {'state': state, 'value': value}
    
    return pd.DataFrame(data)

def create_ml_features(df):
    """Create features for ML models"""
    # Cyclical encoding
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['dow_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
    df['dow_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
    
    # Encode categoricals
    device_map = {d: i for i, d in enumerate(DEVICES)}
    df['device_id'] = df['device'].map(device_map)
    
    user_map = {u: i for i, u in enumerate(USERS)}
    df['user_num'] = df['user_id'].map(user_map)
    
    df['action_binary'] = (df['action'] == 'on').astype(int)
    
    return df

# ===========================================================================
# PART 2: MODEL TRAINING AND BENCHMARKING
# ===========================================================================

def prepare_data_for_training(df, user_id):
    """Prepare features and target for a specific user"""
    from sklearn.preprocessing import LabelEncoder
    
    user_df = df[df['user_id'] == user_id].copy()
    
    feature_cols = [
        'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos',
        'is_weekend', 'temperature', 'humidity',
        'light_state', 'fan_state', 'ac_state'
    ]
    
    X = user_df[feature_cols].values
    
    # Use LabelEncoder to ensure consecutive class labels (0, 1, 2, ...)
    le = LabelEncoder()
    y = le.fit_transform(user_df['device_id'].values)
    
    return X, y, feature_cols, le

def benchmark_models(X_train, X_test, y_train, y_test):
    """Train and evaluate 5 different models"""
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.neural_network import MLPClassifier
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
    
    # Try importing advanced models
    try:
        from xgboost import XGBClassifier
        has_xgb = True
    except ImportError:
        has_xgb = False
        print("XGBoost not installed, skipping...")
    
    try:
        from lightgbm import LGBMClassifier
        has_lgb = True
    except ImportError:
        has_lgb = False
        print("LightGBM not installed, skipping...")
    
    results = []
    models_dict = {}
    
    # 1. Logistic Regression (baseline)
    print("  Training Logistic Regression...")
    start = time.time()
    lr = LogisticRegression(max_iter=1000, random_state=42)
    lr.fit(X_train, y_train)
    train_time = time.time() - start
    y_pred = lr.predict(X_test)
    results.append({
        'model': 'Logistic Regression',
        'accuracy': accuracy_score(y_test, y_pred),
        'f1_macro': f1_score(y_test, y_pred, average='macro', zero_division=0),
        'precision': precision_score(y_test, y_pred, average='macro', zero_division=0),
        'recall': recall_score(y_test, y_pred, average='macro', zero_division=0),
        'train_time': train_time
    })
    models_dict['logistic'] = lr
    
    # 2. Random Forest
    print("  Training Random Forest...")
    start = time.time()
    rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    rf.fit(X_train, y_train)
    train_time = time.time() - start
    y_pred = rf.predict(X_test)
    results.append({
        'model': 'Random Forest',
        'accuracy': accuracy_score(y_test, y_pred),
        'f1_macro': f1_score(y_test, y_pred, average='macro', zero_division=0),
        'precision': precision_score(y_test, y_pred, average='macro', zero_division=0),
        'recall': recall_score(y_test, y_pred, average='macro', zero_division=0),
        'train_time': train_time
    })
    models_dict['random_forest'] = rf
    
    # 3. XGBoost
    if has_xgb:
        print("  Training XGBoost...")
        start = time.time()
        xgb = XGBClassifier(n_estimators=100, max_depth=6, learning_rate=0.1, 
                           random_state=42, verbosity=0)
        xgb.fit(X_train, y_train)
        train_time = time.time() - start
        y_pred = xgb.predict(X_test)
        results.append({
            'model': 'XGBoost',
            'accuracy': accuracy_score(y_test, y_pred),
            'f1_macro': f1_score(y_test, y_pred, average='macro', zero_division=0),
            'precision': precision_score(y_test, y_pred, average='macro', zero_division=0),
            'recall': recall_score(y_test, y_pred, average='macro', zero_division=0),
            'train_time': train_time
        })
        models_dict['xgboost'] = xgb
    
    # 4. LightGBM
    if has_lgb:
        print("  Training LightGBM...")
        start = time.time()
        lgb = LGBMClassifier(n_estimators=100, max_depth=6, learning_rate=0.1,
                            random_state=42, verbose=-1)
        lgb.fit(X_train, y_train)
        train_time = time.time() - start
        y_pred = lgb.predict(X_test)
        results.append({
            'model': 'LightGBM',
            'accuracy': accuracy_score(y_test, y_pred),
            'f1_macro': f1_score(y_test, y_pred, average='macro', zero_division=0),
            'precision': precision_score(y_test, y_pred, average='macro', zero_division=0),
            'recall': recall_score(y_test, y_pred, average='macro', zero_division=0),
            'train_time': train_time
        })
        models_dict['lightgbm'] = lgb
    
    # 5. Neural Network (MLP)
    print("  Training Neural Network (MLP)...")
    start = time.time()
    mlp = MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=500, random_state=42)
    mlp.fit(X_train, y_train)
    train_time = time.time() - start
    y_pred = mlp.predict(X_test)
    results.append({
        'model': 'Neural Network',
        'accuracy': accuracy_score(y_test, y_pred),
        'f1_macro': f1_score(y_test, y_pred, average='macro', zero_division=0),
        'precision': precision_score(y_test, y_pred, average='macro', zero_division=0),
        'recall': recall_score(y_test, y_pred, average='macro', zero_division=0),
        'train_time': train_time
    })
    models_dict['mlp'] = mlp
    
    return results, models_dict

# ===========================================================================
# PART 3: VISUALIZATION
# ===========================================================================

def generate_plots(all_results, output_dir):
    """Generate comparison plots"""
    import matplotlib.pyplot as plt
    
    # Aggregate results across users
    model_names = list(set([r['model'] for r in all_results]))
    
    # Calculate mean metrics per model
    metrics_summary = {}
    for model in model_names:
        model_results = [r for r in all_results if r['model'] == model]
        metrics_summary[model] = {
            'accuracy': np.mean([r['accuracy'] for r in model_results]),
            'f1_macro': np.mean([r['f1_macro'] for r in model_results]),
            'precision': np.mean([r['precision'] for r in model_results]),
            'recall': np.mean([r['recall'] for r in model_results]),
            'train_time': np.mean([r['train_time'] for r in model_results]),
            'accuracy_std': np.std([r['accuracy'] for r in model_results]),
            'f1_std': np.std([r['f1_macro'] for r in model_results]),
        }
    
    # Sort by accuracy
    sorted_models = sorted(metrics_summary.keys(), 
                          key=lambda x: metrics_summary[x]['accuracy'], 
                          reverse=True)
    
    # Plot 1: Accuracy comparison bar chart
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(sorted_models))
    accuracies = [metrics_summary[m]['accuracy'] * 100 for m in sorted_models]
    errors = [metrics_summary[m]['accuracy_std'] * 100 for m in sorted_models]
    
    bars = ax.bar(x, accuracies, yerr=errors, capsize=5, color=['#2ecc71', '#3498db', '#9b59b6', '#e74c3c', '#f39c12'][:len(sorted_models)])
    ax.set_xlabel('Model', fontsize=12)
    ax.set_ylabel('Accuracy (%)', fontsize=12)
    ax.set_title('Model Comparison: Accuracy on Device Prediction Task', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(sorted_models, rotation=15, ha='right')
    ax.set_ylim(0, 100)
    
    # Add value labels
    for bar, acc in zip(bars, accuracies):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, 
                f'{acc:.1f}%', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'plots', 'accuracy_comparison.png'), dpi=150)
    plt.savefig(os.path.join(output_dir, 'plots', 'accuracy_comparison.pdf'))
    plt.close()
    print(f"  Saved: accuracy_comparison.png")
    
    # Plot 2: Multi-metric radar chart
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))
    
    metrics = ['Accuracy', 'F1 Score', 'Precision', 'Recall']
    num_metrics = len(metrics)
    angles = np.linspace(0, 2 * np.pi, num_metrics, endpoint=False).tolist()
    angles += angles[:1]  # Complete the loop
    
    colors = ['#2ecc71', '#3498db', '#9b59b6', '#e74c3c', '#f39c12']
    for idx, model in enumerate(sorted_models[:5]):  # Top 5
        values = [
            metrics_summary[model]['accuracy'],
            metrics_summary[model]['f1_macro'],
            metrics_summary[model]['precision'],
            metrics_summary[model]['recall']
        ]
        values += values[:1]
        ax.plot(angles, values, 'o-', linewidth=2, label=model, color=colors[idx % len(colors)])
        ax.fill(angles, values, alpha=0.1, color=colors[idx % len(colors)])
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics, fontsize=11)
    ax.set_ylim(0, 1)
    ax.set_title('Multi-Metric Model Comparison', fontsize=14, fontweight='bold', pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'plots', 'radar_comparison.png'), dpi=150)
    plt.savefig(os.path.join(output_dir, 'plots', 'radar_comparison.pdf'))
    plt.close()
    print(f"  Saved: radar_comparison.png")
    
    # Plot 3: Training time comparison
    fig, ax = plt.subplots(figsize=(10, 6))
    times = [metrics_summary[m]['train_time'] * 1000 for m in sorted_models]  # Convert to ms
    
    bars = ax.barh(sorted_models, times, color=['#2ecc71', '#3498db', '#9b59b6', '#e74c3c', '#f39c12'][:len(sorted_models)])
    ax.set_xlabel('Training Time (ms)', fontsize=12)
    ax.set_title('Model Training Time Comparison', fontsize=14, fontweight='bold')
    
    for bar, t in zip(bars, times):
        ax.text(bar.get_width() + 5, bar.get_y() + bar.get_height()/2, 
                f'{t:.1f}ms', ha='left', va='center', fontsize=10)
    
    ax.grid(axis='x', alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'plots', 'training_time.png'), dpi=150)
    plt.savefig(os.path.join(output_dir, 'plots', 'training_time.pdf'))
    plt.close()
    print(f"  Saved: training_time.png")
    
    # Plot 4: Per-user accuracy comparison
    fig, ax = plt.subplots(figsize=(12, 6))
    
    users = USERS
    x = np.arange(len(users))
    width = 0.15
    
    for idx, model in enumerate(sorted_models[:5]):
        user_accs = []
        for user in users:
            user_results = [r for r in all_results if r['model'] == model and r.get('user') == user]
            if user_results:
                user_accs.append(user_results[0]['accuracy'] * 100)
            else:
                user_accs.append(0)
        
        offset = (idx - len(sorted_models[:5])/2 + 0.5) * width
        ax.bar(x + offset, user_accs, width, label=model, color=colors[idx % len(colors)])
    
    ax.set_xlabel('User', fontsize=12)
    ax.set_ylabel('Accuracy (%)', fontsize=12)
    ax.set_title('Per-User Model Performance', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([u.capitalize() for u in users])
    ax.legend(loc='upper right')
    ax.set_ylim(0, 100)
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'plots', 'per_user_accuracy.png'), dpi=150)
    plt.savefig(os.path.join(output_dir, 'plots', 'per_user_accuracy.pdf'))
    plt.close()
    print(f"  Saved: per_user_accuracy.png")
    
    return metrics_summary, sorted_models

def generate_latex_table(metrics_summary, sorted_models, output_dir):
    """Generate LaTeX table for report"""
    latex = r"""
\begin{table}[H]
    \centering
    \caption{Model Benchmark Results on Device Prediction Task (averaged across 4 users)}
    \label{tab:model-benchmark}
    \renewcommand{\arraystretch}{1.3}
    \small
    \begin{tabular}{@{} l c c c c c @{}}
        \toprule
        \textbf{Model} & \textbf{Accuracy} & \textbf{F1 Score} & \textbf{Precision} & \textbf{Recall} & \textbf{Train Time} \\
        \midrule
"""
    
    for model in sorted_models:
        m = metrics_summary[model]
        latex += f"        {model} & {m['accuracy']*100:.1f}\\% & {m['f1_macro']:.3f} & {m['precision']:.3f} & {m['recall']:.3f} & {m['train_time']*1000:.1f}ms \\\\\n"
    
    latex += r"""        \bottomrule
    \end{tabular}
\end{table}
"""
    
    with open(os.path.join(output_dir, 'benchmark_table.tex'), 'w') as f:
        f.write(latex)
    print(f"  Saved: benchmark_table.tex")
    
    return latex

# ===========================================================================
# MAIN EXECUTION
# ===========================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("SMART HOME BEHAVIOR LEARNING - ML PIPELINE")
    print("=" * 70)
    
    # Step 1: Generate dataset
    print("\n[1/4] Generating synthetic dataset...")
    df = generate_dataset()
    df = create_ml_features(df)
    print(f"  Generated {len(df)} samples")
    
    # Save dataset
    df.to_csv(os.path.join(OUTPUT_DIR, 'data', 'behavior_data.csv'), index=False)
    print(f"  Saved: data/behavior_data.csv")
    
    # Print dataset stats
    print(f"\n  Dataset Statistics:")
    print(f"  - Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"  - Users: {df['user_id'].nunique()}")
    print(f"  - Devices: {df['device'].nunique()}")
    print(f"  - Samples per user: {df.groupby('user_id').size().to_dict()}")
    
    # Step 2: Train models for each user
    print("\n[2/4] Training and benchmarking models...")
    
    from sklearn.model_selection import train_test_split
    
    all_results = []
    best_models = {}
    
    for user in USERS:
        print(f"\n  Training models for user: {user}")
        X, y, feature_cols, label_encoder = prepare_data_for_training(df, user)
        
        if len(X) < 50:
            print(f"    Skipping {user} - insufficient data ({len(X)} samples)")
            continue
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y if len(np.unique(y)) > 1 else None
        )
        
        print(f"    Train: {len(X_train)}, Test: {len(X_test)}")
        
        results, models = benchmark_models(X_train, X_test, y_train, y_test)
        
        # Add user info to results
        for r in results:
            r['user'] = user
        all_results.extend(results)
        
        # Find best model for this user
        best = max(results, key=lambda x: x['accuracy'])
        best_models[user] = best['model']
        print(f"    Best model: {best['model']} (accuracy: {best['accuracy']*100:.1f}%)")
        
        # Save all models for this user using native formats
        import pickle
        models_dir = os.path.join(OUTPUT_DIR, 'models', user)
        os.makedirs(models_dir, exist_ok=True)
        
        for model_name, model_obj in models.items():
            if model_name == 'xgboost':
                # XGBoost native format
                model_path = os.path.join(models_dir, f'{model_name}.json')
                model_obj.save_model(model_path)
            elif model_name == 'lightgbm':
                # LightGBM native format
                model_path = os.path.join(models_dir, f'{model_name}.txt')
                model_obj.booster_.save_model(model_path)
            else:
                # Pickle for sklearn models (RandomForest, Logistic, MLP)
                model_path = os.path.join(models_dir, f'{model_name}.pkl')
                with open(model_path, 'wb') as f:
                    pickle.dump(model_obj, f)
        
        # Save label encoder as pickle
        with open(os.path.join(models_dir, 'label_encoder.pkl'), 'wb') as f:
            pickle.dump(label_encoder, f)
        
        print(f"    Saved {len(models)} models to models/{user}/")
        print(f"      - XGBoost: .json | LightGBM: .txt | Others: .pkl")
    
    # Step 3: Generate plots and metrics
    print("\n[3/4] Generating visualizations...")
    metrics_summary, sorted_models = generate_plots(all_results, OUTPUT_DIR)
    
    # Step 4: Generate LaTeX output
    print("\n[4/4] Generating LaTeX table...")
    latex_table = generate_latex_table(metrics_summary, sorted_models, OUTPUT_DIR)
    
    # Final summary
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    
    print("\nModel Rankings (by accuracy):")
    for i, model in enumerate(sorted_models, 1):
        m = metrics_summary[model]
        print(f"  {i}. {model}: {m['accuracy']*100:.1f}% accuracy, {m['train_time']*1000:.1f}ms training")
    
    print(f"\nBest model per user:")
    for user, model in best_models.items():
        print(f"  - {user.capitalize()}: {model}")
    
    print(f"\nOutput files saved to: {OUTPUT_DIR}/")
    print("  - data/behavior_data.csv")
    print("  - plots/accuracy_comparison.png")
    print("  - plots/radar_comparison.png")
    print("  - plots/training_time.png")
    print("  - plots/per_user_accuracy.png")
    print("  - benchmark_table.tex")
    
    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE!")
    print("=" * 70)
