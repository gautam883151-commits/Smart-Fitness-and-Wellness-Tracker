import pandas as pd
from pathlib import Path

# -----------------------------
# 1) Set folder paths
# -----------------------------
base_dir = Path(r"C:\Users\sooru\OneDrive\Documents\DAV data\mturkfitbit_export_4.12.16-5.12.16\Fitabase Data 4.12.16-5.12.16")
output_dir = base_dir / "cleaned_data"
output_dir.mkdir(exist_ok=True)

# -----------------------------
# 2) Helper functions
# -----------------------------
def clean_numeric_columns(df):
    # Convert all numeric-looking columns to numeric and remove invalid values
    for col in df.columns:
        if col.lower() in {"id", "logid"}:
            continue
        if df[col].dtype == "object":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def clean_datetime_columns(df, date_cols):
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df

def basic_clean(df, date_cols=None):
    df = df.drop_duplicates()
    df = df.replace({"": pd.NA, " ": pd.NA})
    df = clean_numeric_columns(df)

    if date_cols:
        df = clean_datetime_columns(df, date_cols)

    # Sort by ID and date for clean analysis
    if "Id" in df.columns:
        df["Id"] = df["Id"].astype("int64")
    return df.reset_index(drop=True)

# -----------------------------
# 3) Load the raw CSV files
# -----------------------------
daily_activity = pd.read_csv(base_dir / "dailyActivity_merged.csv")
sleep_day = pd.read_csv(base_dir / "sleepDay_merged.csv")
weight_log = pd.read_csv(base_dir / "weightLogInfo_merged.csv")
heart_rate = pd.read_csv(base_dir / "heartrate_seconds_merged.csv")

# -----------------------------
# 4) Clean each dataset
# -----------------------------
daily_activity = basic_clean(daily_activity, ["ActivityDate"])
daily_activity = daily_activity[
    (daily_activity["Calories"].notna()) &
    (daily_activity["TotalSteps"].notna()) &
    (daily_activity["TotalDistance"].notna())
].copy()

# Remove impossible/invalid values
daily_activity = daily_activity[
    (daily_activity["TotalSteps"] >= 0) &
    (daily_activity["Calories"] > 0)
].copy()

sleep_day = basic_clean(sleep_day, ["SleepDay"])
sleep_day = sleep_day[
    (sleep_day["TotalMinutesAsleep"].notna()) &
    (sleep_day["TotalTimeInBed"].notna())
].copy()

weight_log = basic_clean(weight_log, ["Date"])
weight_log["IsManualReport"] = weight_log["IsManualReport"].astype(str).str.lower().eq("true")
weight_log = weight_log.dropna(subset=["WeightKg"]).copy()

heart_rate = basic_clean(heart_rate, ["Time"])
heart_rate = heart_rate[heart_rate["Value"].notna()].copy()

# -----------------------------
# 5) Save cleaned files
# -----------------------------
daily_activity.to_csv(output_dir / "daily_activity_cleaned.csv", index=False)
sleep_day.to_csv(output_dir / "sleep_day_cleaned.csv", index=False)
weight_log.to_csv(output_dir / "weight_log_cleaned.csv", index=False)
heart_rate.to_csv(output_dir / "heart_rate_cleaned.csv", index=False)

# Optional Excel export
daily_activity.to_excel(output_dir / "daily_activity_cleaned.xlsx", index=False)
sleep_day.to_excel(output_dir / "sleep_day_cleaned.xlsx", index=False)
weight_log.to_excel(output_dir / "weight_log_cleaned.xlsx", index=False)
heart_rate.to_excel(output_dir / "heart_rate_cleaned.xlsx", index=False)

print("Cleaning completed successfully.")
print(f"Files saved in: {output_dir}")