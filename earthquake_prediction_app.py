import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import joblib
from sklearn.model_selection import train_test_split

# Load the model
model = joblib.load("data/earthquake_magnitude_model.pkl")

# Load and clean the dataset
@st.cache_data
def load_data():
    df = pd.read_excel("data/Official Website of National Center of Seismology.xlsx", sheet_name='Sheet1')
    df_cleaned = df[1:].copy()
    df_cleaned.columns = df.iloc[0]
    df_cleaned = df_cleaned[1:]
    df_cleaned['Lat'] = pd.to_numeric(df_cleaned['Lat'], errors='coerce')
    df_cleaned['Long'] = pd.to_numeric(df_cleaned['Long'], errors='coerce')
    df_cleaned['Depth'] = pd.to_numeric(df_cleaned['Depth'], errors='coerce')
    df_cleaned['Magnitude'] = pd.to_numeric(df_cleaned['Magnitude'], errors='coerce')
    df_cleaned = df_cleaned.dropna(subset=['Lat', 'Long', 'Depth', 'Magnitude'])
    return df_cleaned

# Load data
df_cleaned = load_data()
X = df_cleaned[['Lat', 'Long', 'Depth']]
y = df_cleaned['Magnitude']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
y_pred = model.predict(X_test)

# Streamlit UI
st.title("🌍 Earthquake Magnitude Predictor")
st.markdown("Enter the earthquake parameters below to predict the magnitude.")

lat = st.number_input("Latitude", value=28.5, format="%.4f")
lon = st.number_input("Longitude", value=77.2, format="%.4f")
depth = st.number_input("Depth (km)", value=10.0, format="%.1f")

if st.button("Predict Magnitude"):
    input_data = pd.DataFrame({'Lat': [lat], 'Long': [lon], 'Depth': [depth]})
    prediction = model.predict(input_data)[0]
    st.success(f"🌋 Predicted Earthquake Magnitude: **{prediction:.2f}**")

# Plot actual vs predicted
st.subheader("📊 Predicted vs Actual Magnitudes (Test Data)")

fig, ax = plt.subplots(figsize=(8, 5))
ax.scatter(y_test, y_pred, alpha=0.7)
ax.plot([min(y_test), max(y_test)], [min(y_test), max(y_test)], 'r--')
ax.set_xlabel("Actual Magnitude")
ax.set_ylabel("Predicted Magnitude")
ax.set_title("Predicted vs Actual")
ax.grid(True)
st.pyplot(fig)
