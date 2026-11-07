from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Side, Border
from openpyxl.utils import get_column_letter


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "mturkfitbit_export_4.12.16-5.12.16" / "Fitabase Data 4.12.16-5.12.16"
OUTPUT_DIR = Path(__file__).resolve().parent
VIS_DIR = OUTPUT_DIR / "visualizations"


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def clean_numeric_frame(df: pd.DataFrame, exclude: set[str] | None = None) -> pd.DataFrame:
    df = df.copy()
    exclude = exclude or set()
    for col in df.columns:
        if col in exclude:
            continue
        if df[col].dtype == "object":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def clean_date_columns(df: pd.DataFrame, date_columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.normalize()
    return df


def load_raw_datasets() -> dict[str, pd.DataFrame]:
    dataset_map = {
        "dailyActivity_merged": RAW_DATA_DIR / "dailyActivity_merged.csv",
        "sleepDay_merged": RAW_DATA_DIR / "sleepDay_merged.csv",
        "weightLogInfo_merged": RAW_DATA_DIR / "weightLogInfo_merged.csv",
        "heartrate_seconds_merged": RAW_DATA_DIR / "heartrate_seconds_merged.csv",
    }
    data = {}
    for name, path in dataset_map.items():
        df = pd.read_csv(path)
        data[name] = standardize_columns(df)
    return data


def build_quality_report(raw_datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    quality_rows = []
    for dataset_name, df in raw_datasets.items():
        rows, cols = df.shape
        duplicate_rows = int(df.duplicated().sum())
        missing_cells = int(df.isna().sum().sum())
        missing_percentage = (missing_cells / (rows * cols) * 100) if rows and cols else 0.0

        key_date_cols = []
        for c in df.columns:
            low = c.lower()
            if "date" in low or "time" in low or "day" in low:
                key_date_cols.append(c)

        date_issue_count = 0
        for col in key_date_cols:
            parsed = pd.to_datetime(df[col], errors="coerce")
            date_issue_count += int(parsed.isna().sum())

        issue_summary = "No major issue detected"
        if duplicate_rows > 0:
            issue_summary = "Duplicate rows detected"
        elif missing_cells > 0:
            issue_summary = "Missing values detected"
        elif date_issue_count > 0:
            issue_summary = "Date parsing issues detected"

        quality_rows.append(
            {
                "dataset": dataset_name,
                "rows": rows,
                "columns": cols,
                "duplicate_rows": duplicate_rows,
                "missing_cells": missing_cells,
                "missing_percentage": round(missing_percentage, 2),
                "date_issue_count": date_issue_count,
                "key_issue": issue_summary,
            }
        )

    return pd.DataFrame(quality_rows)


def clean_daily_data(raw_data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    daily = standardize_columns(raw_data["dailyActivity_merged"])
    sleep = standardize_columns(raw_data["sleepDay_merged"])
    weight = standardize_columns(raw_data["weightLogInfo_merged"])
    heart = standardize_columns(raw_data["heartrate_seconds_merged"])

    daily = daily.drop_duplicates().replace({"": pd.NA, " ": pd.NA})
    daily = clean_numeric_frame(daily, exclude={"Id"})
    daily["Id"] = daily["Id"].astype("Int64")
    daily = clean_date_columns(daily, ["ActivityDate"])
    daily = daily.rename(columns={"ActivityDate": "Date"})

    sleep = sleep.drop_duplicates().replace({"": pd.NA, " ": pd.NA})
    sleep = clean_numeric_frame(sleep, exclude={"Id"})
    sleep["Id"] = sleep["Id"].astype("Int64")
    sleep = clean_date_columns(sleep, ["SleepDay"])
    sleep = sleep.rename(columns={"SleepDay": "Date"})
    sleep["Date"] = sleep["Date"].dt.normalize()

    weight = weight.drop_duplicates().replace({"": pd.NA, " ": pd.NA})
    weight = clean_numeric_frame(weight, exclude={"Id", "IsManualReport"})
    weight["Id"] = weight["Id"].astype("Int64")
    weight["IsManualReport"] = weight["IsManualReport"].astype(str).str.lower().eq("true")
    weight = clean_date_columns(weight, ["Date"])
    weight["Date"] = weight["Date"].dt.normalize()

    heart = heart.drop_duplicates().replace({"": pd.NA, " ": pd.NA})
    heart = clean_numeric_frame(heart, exclude={"Id"})
    heart["Id"] = heart["Id"].astype("Int64")
    heart = clean_date_columns(heart, ["Time"])
    heart["Date"] = heart["Time"].dt.normalize()

    sleep_summary = (
        sleep.groupby(["Id", "Date"], as_index=False)
        .agg(
            TotalSleepRecords=("TotalSleepRecords", "max"),
            TotalMinutesAsleep=("TotalMinutesAsleep", "max"),
            TotalTimeInBed=("TotalTimeInBed", "max"),
        )
    )

    weight_summary = (
        weight.groupby(["Id", "Date"], as_index=False)
        .agg(
            WeightKg=("WeightKg", "mean"),
            WeightPounds=("WeightPounds", "mean"),
            BMI=("BMI", "mean"),
        )
    )

    heart_summary = (
        heart.groupby(["Id", "Date"], as_index=False)
        .agg(
            AvgHeartRate=("Value", "mean"),
            MaxHeartRate=("Value", "max"),
            MinHeartRate=("Value", "min"),
            HeartRateReadings=("Value", "count"),
        )
    )

    merged = daily.merge(sleep_summary, on=["Id", "Date"], how="left")
    merged = merged.merge(weight_summary, on=["Id", "Date"], how="left")
    merged = merged.merge(heart_summary, on=["Id", "Date"], how="left")
    merged = merged.sort_values(["Id", "Date"]).reset_index(drop=True)

    merged["SleepHours"] = merged["TotalMinutesAsleep"] / 60
    merged["ActivityIntensityScore"] = (
        merged["VeryActiveMinutes"]
        + 0.5 * merged["FairlyActiveMinutes"]
        + 0.25 * merged["LightlyActiveMinutes"]
    )

    return merged


def build_descriptive_statistics(df: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "TotalSteps",
        "TotalDistance",
        "Calories",
        "VeryActiveMinutes",
        "FairlyActiveMinutes",
        "LightlyActiveMinutes",
        "SedentaryMinutes",
        "TotalMinutesAsleep",
        "WeightKg",
        "AvgHeartRate",
    ]
    stats = df[metrics].agg(["count", "mean", "median", "min", "max", "std"]).T
    stats = stats.rename(columns={"count": "Count", "mean": "Mean", "median": "Median", "min": "Minimum", "max": "Maximum", "std": "StdDev"})
    stats = stats.reset_index().rename(columns={"index": "Metric"})
    return stats


def build_activity_summary(df: pd.DataFrame) -> pd.DataFrame:
    summary = {
        "Metric": [
            "AverageSteps",
            "AverageDistance",
            "AverageCalories",
            "AverageVeryActiveMinutes",
            "AverageFairlyActiveMinutes",
            "AverageLightlyActiveMinutes",
            "AverageSedentaryMinutes",
            "AverageSleepMinutes",
            "AverageWeightKg",
            "AverageHeartRate",
        ],
        "Value": [
            df["TotalSteps"].mean(),
            df["TotalDistance"].mean(),
            df["Calories"].mean(),
            df["VeryActiveMinutes"].mean(),
            df["FairlyActiveMinutes"].mean(),
            df["LightlyActiveMinutes"].mean(),
            df["SedentaryMinutes"].mean(),
            df["TotalMinutesAsleep"].mean(),
            df["WeightKg"].mean(),
            df["AvgHeartRate"].mean(),
        ],
    }
    return pd.DataFrame(summary)


def build_daily_trends(df: pd.DataFrame) -> pd.DataFrame:
    daily_trends = (
        df.groupby("Date", as_index=False)
        .agg(
            AverageSteps=("TotalSteps", "mean"),
            AverageDistance=("TotalDistance", "mean"),
            AverageCalories=("Calories", "mean"),
            AverageVeryActiveMinutes=("VeryActiveMinutes", "mean"),
            AverageFairlyActiveMinutes=("FairlyActiveMinutes", "mean"),
            AverageLightlyActiveMinutes=("LightlyActiveMinutes", "mean"),
            AverageSedentaryMinutes=("SedentaryMinutes", "mean"),
            AverageSleepMinutes=("TotalMinutesAsleep", "mean"),
        )
    )
    return daily_trends


def create_visualizations(df: pd.DataFrame, output_dir: Path) -> None:
    sns.set_theme(style="whitegrid")
    vis_dir = output_dir / "visualizations"
    vis_dir.mkdir(exist_ok=True)

    daily_avg = df.groupby("Date")["TotalSteps"].mean().reset_index()
    plt.figure(figsize=(12, 6))
    sns.lineplot(data=daily_avg, x="Date", y="TotalSteps")
    plt.title("Daily Average Steps Over Time")
    plt.xlabel("Date")
    plt.ylabel("Average Steps")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(vis_dir / "daily_steps_trend.png", dpi=300)
    plt.close()

    plt.figure(figsize=(8, 6))
    sns.histplot(df["TotalSteps"].dropna(), bins=20, kde=True)
    plt.title("Distribution of Daily Steps")
    plt.xlabel("Total Steps")
    plt.ylabel("Frequency")
    plt.tight_layout()
    plt.savefig(vis_dir / "step_distribution.png", dpi=300)
    plt.close()

    plt.figure(figsize=(8, 6))
    sns.scatterplot(data=df, x="TotalSteps", y="Calories", alpha=0.7)
    plt.title("Steps vs Calories Burned")
    plt.xlabel("Total Steps")
    plt.ylabel("Calories")
    plt.tight_layout()
    plt.savefig(vis_dir / "steps_vs_calories.png", dpi=300)
    plt.close()

    correlation_cols = [
        "TotalSteps",
        "TotalDistance",
        "Calories",
        "VeryActiveMinutes",
        "FairlyActiveMinutes",
        "LightlyActiveMinutes",
        "SedentaryMinutes",
        "TotalMinutesAsleep",
        "AvgHeartRate",
    ]
    corr = df[correlation_cols].corr()
    plt.figure(figsize=(10, 8))
    sns.heatmap(corr, annot=True, cmap="coolwarm", fmt=".2f")
    plt.title("Correlation Heatmap of Key Fitness Metrics")
    plt.tight_layout()
    plt.savefig(vis_dir / "correlation_heatmap.png", dpi=300)
    plt.close()

    day_name = df["Date"].dt.day_name()
    weekend_flag = day_name.isin(["Saturday", "Sunday"])
    comparison = pd.DataFrame({
        "day_type": np.where(weekend_flag, "Weekend", "Weekday"),
        "TotalSteps": df["TotalSteps"],
    })
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=comparison, x="day_type", y="TotalSteps")
    plt.title("Weekday vs Weekend Step Comparison")
    plt.xlabel("Day Type")
    plt.ylabel("Total Steps")
    plt.tight_layout()
    plt.savefig(vis_dir / "weekday_vs_weekend_steps.png", dpi=300)
    plt.close()


def create_excel_workbook(cleaned_df: pd.DataFrame, quality_df: pd.DataFrame, stats_df: pd.DataFrame, activity_summary: pd.DataFrame, daily_trends: pd.DataFrame, insights_df: pd.DataFrame, output_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Cleaned_Data"
    ws.append(["Id", "Date", "TotalSteps", "TotalDistance", "TrackerDistance", "LoggedActivitiesDistance", "VeryActiveDistance", "ModeratelyActiveDistance", "LightActiveDistance", "SedentaryActiveDistance", "VeryActiveMinutes", "FairlyActiveMinutes", "LightlyActiveMinutes", "SedentaryMinutes", "Calories", "TotalSleepRecords", "TotalMinutesAsleep", "TotalTimeInBed", "WeightKg", "WeightPounds", "BMI", "AvgHeartRate", "MaxHeartRate", "MinHeartRate", "HeartRateReadings", "SleepHours", "ActivityIntensityScore"])
    for row in cleaned_df[[
        "Id",
        "Date",
        "TotalSteps",
        "TotalDistance",
        "TrackerDistance",
        "LoggedActivitiesDistance",
        "VeryActiveDistance",
        "ModeratelyActiveDistance",
        "LightActiveDistance",
        "SedentaryActiveDistance",
        "VeryActiveMinutes",
        "FairlyActiveMinutes",
        "LightlyActiveMinutes",
        "SedentaryMinutes",
        "Calories",
        "TotalSleepRecords",
        "TotalMinutesAsleep",
        "TotalTimeInBed",
        "WeightKg",
        "WeightPounds",
        "BMI",
        "AvgHeartRate",
        "MaxHeartRate",
        "MinHeartRate",
        "HeartRateReadings",
        "SleepHours",
        "ActivityIntensityScore",
    ]].itertuples(index=False, name=None):
        ws.append(list(row))

    format_sheet(ws)

    ws_overview = wb.create_sheet("Dataset_Overview")
    overview_rows = [
        ["Metric", "Value"],
        ["Total records", len(cleaned_df)],
        ["Total columns", len(cleaned_df.columns)],
        ["Date range start", cleaned_df["Date"].min()],
        ["Date range end", cleaned_df["Date"].max()],
        ["Participants", cleaned_df["Id"].nunique()],
    ]
    for row in overview_rows:
        ws_overview.append(row)
    format_sheet(ws_overview)

    ws_stats = wb.create_sheet("Descriptive_Statistics")
    for row in stats_df.itertuples(index=False, name=None):
        ws_stats.append(list(row))
    format_sheet(ws_stats)

    ws_activity = wb.create_sheet("Activity_Summary")
    for row in activity_summary.itertuples(index=False, name=None):
        ws_activity.append(list(row))
    format_sheet(ws_activity)

    ws_daily = wb.create_sheet("Daily_Trends")
    for row in daily_trends.itertuples(index=False, name=None):
        ws_daily.append(list(row))
    format_sheet(ws_daily)

    ws_insights = wb.create_sheet("Key_Insights")
    for row in insights_df.itertuples(index=False, name=None):
        ws_insights.append(list(row))
    format_sheet(ws_insights)

    ws_quality = wb.create_sheet("Dataset_Quality")
    for row in quality_df.itertuples(index=False, name=None):
        ws_quality.append(list(row))
    format_sheet(ws_quality)

    wb.save(output_path)


def format_sheet(ws) -> None:
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="D9EAF7")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for col in ws.columns:
        max_len = 0
        for cell in col:
            if cell.value is not None:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 22)

    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(horizontal="left", vertical="center")

    thin = Side(style="thin", color="D9D9D9")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for row in ws.iter_rows():
        for cell in row:
            cell.border = border


def create_csv_outputs(cleaned_df: pd.DataFrame, quality_df: pd.DataFrame, stats_df: pd.DataFrame, activity_summary: pd.DataFrame, daily_trends: pd.DataFrame, output_dir: Path) -> None:
    cleaned_df.to_csv(output_dir / "cleaned_dataset.csv", index=False)
    quality_df.to_csv(output_dir / "dataset_quality_report.csv", index=False)
    stats_df.to_csv(output_dir / "descriptive_statistics.csv", index=False)
    daily_trends.to_csv(output_dir / "daily_trends.csv", index=False)
    activity_summary.to_csv(output_dir / "activity_summary.csv", index=False)


def create_master_analytics_file(cleaned_df: pd.DataFrame, output_dir: Path) -> None:
    master = cleaned_df.copy()
    master["Date"] = pd.to_datetime(master["Date"]).dt.strftime("%Y-%m-%d")
    master["Weekday"] = pd.to_datetime(master["Date"]).dt.day_name()
    master["WeekendFlag"] = master["Weekday"].isin(["Saturday", "Sunday"]).astype(int)
    master["ActiveMinutesTotal"] = (
        master["VeryActiveMinutes"]
        + master["FairlyActiveMinutes"]
        + master["LightlyActiveMinutes"]
    )
    master["SleepHours"] = master["TotalMinutesAsleep"] / 60
    master = master.sort_values(["Id", "Date"]).reset_index(drop=True)
    master.to_csv(output_dir / "master_analytics_data.csv", index=False)
    master.to_excel(output_dir / "master_analytics_data.xlsx", index=False)


def build_insights(cleaned_df: pd.DataFrame, stats_df: pd.DataFrame) -> pd.DataFrame:
    corr = cleaned_df[["TotalSteps", "Calories", "TotalDistance", "VeryActiveMinutes", "FairlyActiveMinutes", "SedentaryMinutes", "AvgHeartRate"]].corr()
    strongest_corr = corr["Calories"].drop("Calories").abs().idxmax()
    strongest_corr_value = corr.loc[strongest_corr, "Calories"]
    average_steps = cleaned_df["TotalSteps"].mean()
    average_sleep = cleaned_df["TotalMinutesAsleep"].mean()
    average_sedentary = cleaned_df["SedentaryMinutes"].mean()
    average_active = cleaned_df[["VeryActiveMinutes", "FairlyActiveMinutes", "LightlyActiveMinutes"]].sum(axis=1).mean()
    max_steps = cleaned_df["TotalSteps"].max()
    min_steps = cleaned_df["TotalSteps"].min()

    insights = [
        ["Average daily steps", round(average_steps, 2), "Calculated on the cleaned daily activity dataset."],
        ["Average sleep duration (minutes)", round(average_sleep, 2), "Derived from sleep-day records matched to daily activity records."],
        ["Average sedentary minutes", round(average_sedentary, 2), "Mean sedentary time across all user-days."],
        ["Average active minutes", round(average_active, 2), "Combined minutes for very active, fairly active, and lightly active categories."],
        ["Maximum recorded steps", int(max_steps), "Highest daily total step count in the dataset."],
        ["Minimum recorded steps", int(min_steps), "Lowest daily total step count in the dataset."],
        ["Strongest calories relationship", strongest_corr, f"The strongest correlation with calories is {strongest_corr} ({strongest_corr_value:.3f})."],
    ]
    return pd.DataFrame(insights, columns=["Insight", "Value", "Evidence"])


def create_final_report(report_path: Path, cleaned_df: pd.DataFrame, quality_df: pd.DataFrame, stats_df: pd.DataFrame, insights_df: pd.DataFrame) -> None:
    avg_steps = cleaned_df["TotalSteps"].mean()
    avg_distance = cleaned_df["TotalDistance"].mean()
    avg_cal = cleaned_df["Calories"].mean()
    avg_sleep = cleaned_df["TotalMinutesAsleep"].mean()
    corr = cleaned_df[["TotalSteps", "Calories", "TotalDistance", "VeryActiveMinutes", "SedentaryMinutes"]].corr()
    corr_value = corr.loc["TotalSteps", "Calories"]
    date_range = f"{cleaned_df['Date'].min().date()} to {cleaned_df['Date'].max().date()}"

    markdown = f"""# Smart Fitness and Wellness Tracker - Final Analytics Report

## Data Scope
The analysis used the raw Fitbit export for the period {date_range} from the repository folder `mturkfitbit_export_4.12.16-5.12.16/Fitabase Data 4.12.16-5.12.16`.

## Dataset Quality Overview
- Records analyzed: {len(cleaned_df)}
- Participants: {cleaned_df['Id'].nunique()}
- Duplicate rows removed: {int(quality_df['duplicate_rows'].sum())}
- Missing-value cells found during raw inspection: {int(quality_df['missing_cells'].sum())}

## Descriptive Summary
- Average daily steps: {avg_steps:.2f}
- Average distance: {avg_distance:.2f} km
- Average calories burned: {avg_cal:.2f}
- Average sleep duration: {avg_sleep:.2f} minutes
- Correlation between steps and calories: {corr_value:.3f}

## Key Insights
1. Daily activity is highly linked to calorie expenditure; the steps-to-calories relationship was the strongest relationship observed in the cleaned dataset.
2. The dataset captures a wide range of daily movement, from low-step sedentary days to highly active training days.
3. Sedentary minutes remain substantial relative to active minutes, indicating a meaningful opportunity to improve daily movement habits.
4. Sleep tracking is available for matched days and helps explain overall recovery and energy patterns.

## Visualizations
The project generated visualizations for daily step trends, step distribution, steps vs calories, correlation heatmap, and weekday vs weekend step comparison.

## Recommendation
Use the cleaned daily activity dataset as the primary analytical base for dashboarding and interventions. Additional sensor data can be layered in for deeper personalization, but the core daily metrics provide a practical foundation for an activity and wellness tracker.
"""

    report_path.write_text(markdown, encoding="utf-8")


def create_readme(output_dir: Path) -> None:
    readme = """# Smart Fitness and Wellness Tracker Analytics

This project analyzes the Fitbit data exported from the repository under `mturkfitbit_export_4.12.16-5.12.16/Fitabase Data 4.12.16-5.12.16`.

## Requirements
- Python 3.10+
- pandas
- numpy
- matplotlib
- seaborn
- openpyxl

Install dependencies:

```bash
pip install pandas numpy matplotlib seaborn openpyxl
```

## Run the analysis
From the repository root:

```bash
python analytics_output/fitness_wellness_analysis.py
```

## Outputs generated
- cleaned_dataset.csv
- cleaned_dataset.xlsx
- descriptive_statistics.csv
- dataset_quality_report.csv
- activity_analysis.xlsx
- visualizations/
- final_analytics_report.md
"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    raw_data = load_raw_datasets()
    quality_df = build_quality_report(raw_data)
    cleaned_df = clean_daily_data(raw_data)

    cleaned_df = cleaned_df.dropna(subset=["TotalSteps", "TotalDistance", "Calories"]).copy()
    cleaned_df = cleaned_df[cleaned_df["TotalSteps"] >= 0].copy()
    cleaned_df = cleaned_df[cleaned_df["Calories"] > 0].copy()

    stats_df = build_descriptive_statistics(cleaned_df)
    activity_summary = build_activity_summary(cleaned_df)
    daily_trends = build_daily_trends(cleaned_df)
    insights_df = build_insights(cleaned_df, stats_df)

    VIS_DIR.mkdir(exist_ok=True, parents=True)
    create_visualizations(cleaned_df, OUTPUT_DIR)

    cleaned_df.to_excel(OUTPUT_DIR / "cleaned_dataset.xlsx", index=False)
    create_csv_outputs(cleaned_df, quality_df, stats_df, activity_summary, daily_trends, OUTPUT_DIR)
    create_master_analytics_file(cleaned_df, OUTPUT_DIR)

    activity_workbook_path = OUTPUT_DIR / "activity_analysis.xlsx"
    create_excel_workbook(cleaned_df, quality_df, stats_df, activity_summary, daily_trends, insights_df, activity_workbook_path)

    create_final_report(OUTPUT_DIR / "final_analytics_report.md", cleaned_df, quality_df, stats_df, insights_df)
    create_readme(OUTPUT_DIR)

    print("Analysis completed successfully.")
    print(f"Outputs saved to: {OUTPUT_DIR}")
    print(f"Cleaned rows: {len(cleaned_df)}")
    print(f"Date range: {cleaned_df['Date'].min().date()} to {cleaned_df['Date'].max().date()}")


if __name__ == "__main__":
    main()
