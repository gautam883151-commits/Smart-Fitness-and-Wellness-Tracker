# Smart Fitness and Wellness Tracker Analytics

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
