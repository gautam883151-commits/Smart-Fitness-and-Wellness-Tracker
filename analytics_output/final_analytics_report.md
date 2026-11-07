# Smart Fitness and Wellness Tracker - Final Analytics Report

## Data Scope
The analysis used the raw Fitbit export for the period 2016-04-12 to 2016-05-12 from the repository folder `mturkfitbit_export_4.12.16-5.12.16/Fitabase Data 4.12.16-5.12.16`.

## Dataset Quality Overview
- Records analyzed: 936
- Participants: 33
- Duplicate rows removed: 3
- Missing-value cells found during raw inspection: 65

## Descriptive Summary
- Average daily steps: 7670.55
- Average distance: 5.51 km
- Average calories burned: 2313.45
- Average sleep duration: 419.17 minutes
- Correlation between steps and calories: 0.587

## Key Insights
1. Daily activity is highly linked to calorie expenditure; the steps-to-calories relationship was the strongest relationship observed in the cleaned dataset.
2. The dataset captures a wide range of daily movement, from low-step sedentary days to highly active training days.
3. Sedentary minutes remain substantial relative to active minutes, indicating a meaningful opportunity to improve daily movement habits.
4. Sleep tracking is available for matched days and helps explain overall recovery and energy patterns.

## Visualizations
The project generated visualizations for daily step trends, step distribution, steps vs calories, correlation heatmap, and weekday vs weekend step comparison.

## Recommendation
Use the cleaned daily activity dataset as the primary analytical base for dashboarding and interventions. Additional sensor data can be layered in for deeper personalization, but the core daily metrics provide a practical foundation for an activity and wellness tracker.
