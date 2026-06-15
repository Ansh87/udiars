# Required libraries
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import classification_report, confusion_matrix, mean_squared_error, r2_score
import matplotlib.pyplot as plt

# === Load your dataset ===
df = pd.read_csv("data/ml_earthquake_risk_dataset_with_risk_category.csv")

# === Simulate Insurance Premiums ===
df["premium_estimate"] = (
    0.0008 * df["historic_damage_usd"] +
    150 * df["soil_liquefaction_risk"] +
    0.2 * df["insurance_claims_count"]
).round(2)

# === Risk Category Classification ===

# Features and target for classification
class_features = [
    "earthquake_count", "avg_magnitude", "population_density",
    "distance_to_fault_km", "soil_liquefaction_risk",
    "historic_damage_usd", "insurance_claims_count"
]
X_class = df[class_features].dropna()
y_class = df.loc[X_class.index, "risk_category"]

# Train-test split
X_train_c, X_test_c, y_train_c, y_test_c = train_test_split(
    X_class, y_class, test_size=0.2, stratify=y_class, random_state=42
)

# Train Random Forest Classifier
clf = RandomForestClassifier(n_estimators=100, random_state=42)
clf.fit(X_train_c, y_train_c)

# Predict & evaluate
y_pred_c = clf.predict(X_test_c)
print("=== Classification Report ===")
print(classification_report(y_test_c, y_pred_c))
print("Confusion Matrix:")
print(confusion_matrix(y_test_c, y_pred_c))

# === Premium Estimate Regression ===

# Features and target for regression
X_reg = df[class_features].dropna()
y_reg = df.loc[X_reg.index, "premium_estimate"]

# Train-test split
X_train_r, X_test_r, y_train_r, y_test_r = train_test_split(
    X_reg, y_reg, test_size=0.2, random_state=42
)

# Train Random Forest Regressor
reg = RandomForestRegressor(n_estimators=100, random_state=42)
reg.fit(X_train_r, y_train_r)

# Predict & evaluate
y_pred_r = reg.predict(X_test_r)
rmse = np.sqrt(mean_squared_error(y_test_r, y_pred_r))
r2 = r2_score(y_test_r, y_pred_r)

print("\n=== Regression Performance ===")
print(f"RMSE: ${rmse:.2f}")
print(f"R² Score: {r2:.3f}")

# Plot actual vs predicted
plt.figure(figsize=(6, 5))
plt.scatter(y_test_r, y_pred_r, color='blue', alpha=0.7)
plt.plot([y_test_r.min(), y_test_r.max()], [y_test_r.min(), y_test_r.max()], 'r--')
plt.xlabel("Actual Premium")
plt.ylabel("Predicted Premium")
plt.title("Predicted vs Actual Insurance Premium")
plt.grid(True)
plt.tight_layout()
plt.show()
