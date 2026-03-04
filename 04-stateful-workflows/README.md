# EDA Workflow

## Setup
- Python 3.14
- uv

## Understanding the baseline

The starter code had a LangGraph workflow that runs analysis tools sequentially, then uses an LLM to extract observations after each step and synthesize everything at the end.

Two tools were already implemented:
- `profile_dataset` — shape, dtypes, describe(), value counts
- `analyze_missingness` — missing counts/percentages per column

Two were left as TODOs:
- `compute_aggregates`
- `analyze_relationships`

The `extract_observations_system.txt` prompt was also empty.

## What I did

### 1. Wrote the observation extraction prompt

Used `synthesize_findings_system.txt` as reference. Kept it simple — role, task, instructions, constraints. Tells the LLM to extract 1-2 specific observations per step, referencing actual values from the results.

### 2. Implemented the two placeholder tools

**`compute_aggregates`** — groups by each categorical column (<50 unique values) and computes count/mean/sum for numerics.

**`analyze_relationships`** — correlation matrix + data integrity check. If it finds columns that look like quantity, price, and total, it checks whether `quantity * price == total`. Found that ~12% of rows in the cafe dataset fail this check.

### 3. Added 4 more analysis tools

Wanted a more complete first-pass EDA, so added:

- **`detect_duplicates`** — exact dupes + duplicates on ID columns
- **`detect_outliers`** — IQR method per numeric column, reports extreme values
- **`analyze_temporal`** — auto-detects date columns, computes time range, monthly counts, day-of-week, coverage gaps
- **`analyze_distributions`** — skewness, kurtosis, percentiles, flags columns that need transforms

### 4. Rewired the graph

Went from 4 tools to 8, each followed by observation extraction:

```
profile → missingness → duplicates → outliers → aggregates → relationships → temporal → distributions → synthesize
```

Used a loop to wire the graph instead of hardcoding 16 edges:

```python
analysis_steps = [
    ("profile_dataset", profile_dataset_node),
    ("analyze_missingness", analyze_missingness_node),
    ("detect_duplicates", detect_duplicates_node),
    ("detect_outliers", detect_outliers_node),
    ("compute_aggregates", compute_aggregates_node),
    ("analyze_relationships", analyze_relationships_node),
    ("analyze_temporal", analyze_temporal_node),
    ("analyze_distributions", analyze_distributions_node),
]

for i, (name, node_fn) in enumerate(analysis_steps, start=1):
    workflow.add_node(name, node_fn)
    workflow.add_node(f"extract_observations_{i}", extract_observations_node)
```

## Gotchas

- **pandas + Python 3.14**: String columns now use `StringDtype` instead of `"object"`. The temporal node's date detection was checking `df[col].dtype == "object"` which silently skipped all string columns. Fixed with `pd.api.types.is_string_dtype()`.


## Running

```bash
cp .env.example .env
# add your OpenAI key
.venv/bin/python example_usage.py
```

## Result

The workflow picked up some interesting stuff from the cafe dataset:
- 620 rows have `Item` set to "unknown" or "error" — dirty data that would mess up any downstream analysis
- ~12% of rows fail the `Quantity * Price Per Unit == Total Spent` integrity check, so there's clearly some bad data entry going on
- Mondays have way more transactions (1798) than other days, February is the busiest month
- No missing values, no duplicates, no IQR outliers — the numeric columns are clean, it's the categorical/integrity stuff that's messy

<details>
<summary>Full output (Click to expand)</summary>

```
============================================================
DATASET PROFILE
============================================================
shape: {'rows': 9741, 'columns': 6}
columns: ['Transaction ID', 'Item', 'Quantity', 'Price Per Unit', 'Total Spent', 'Transaction Date']
dtypes: {'Transaction ID': 'object', 'Item': 'object', 'Quantity': 'float64', 'Price Per Unit': 'float64', 'Total Spent': 'float64', 'Transaction Date': 'object'}
numeric_columns: ['Quantity', 'Price Per Unit', 'Total Spent']
categorical_columns: ['Transaction ID', 'Item', 'Transaction Date']
numeric_summary: dict with 3 items
categorical_summary: dict with 3 items

Observations:
  • The 'Item' column contains 337 entries labeled as 'unknown' and 283 as 'error', indicating potential data quality issues that should be addressed to ensure accurate analysis.
  • The maximum 'Total Spent' is 20, which is significantly lower than the mean of 8.45, suggesting that there may be outliers or misreported transactions that warrant further investigation.

============================================================
MISSINGNESS ANALYSIS
============================================================
total_rows: 9741
missing_count: {'Transaction ID': 0, 'Item': 0, 'Quantity': 0, 'Price Per Unit': 0, 'Total Spent': 0, 'Transaction Date': 0}
missing_percentage: {'Transaction ID': 0.0, 'Item': 0.0, 'Quantity': 0.0, 'Price Per Unit': 0.0, 'Total Spent': 0.0, 'Transaction Date': 0.0}
high_missing_columns: {}
complete_rows: 9741
complete_rows_pct: 100.0

Observations:
  • All columns in the dataset have 0% missing values, indicating high data quality and completeness, which allows for robust analysis without the need for imputation.
  • With 100% complete rows, the dataset is ready for immediate modeling, but it is advisable to verify the accuracy of the data entries to ensure reliability in insights.

============================================================
DUPLICATE DETECTION
============================================================
exact_duplicate_rows: 0
exact_duplicate_pct: 0.0
id_column_duplicates: {}

Observations:
  • There are no exact duplicate rows in the dataset, indicating a clean dataset in terms of row uniqueness, which allows for reliable analysis without the need for deduplication.
  • The absence of duplicates in the 'id' column suggests that each entry is uniquely identifiable, reinforcing the integrity of the dataset for further modeling.

============================================================
OUTLIER DETECTION
============================================================
Quantity: {'q1': 2.0, 'q3': 4.0, 'iqr': 2.0, 'lower_bound': -1.0, 'upper_bound': 7.0, 'outlier_count': 0, 'outlier_pct': 0.0, 'min_value': 1.0, 'max_value': 5.0}
Price Per Unit: {'q1': 2.0, 'q3': 4.0, 'iqr': 2.0, 'lower_bound': -1.0, 'upper_bound': 7.0, 'outlier_count': 0, 'outlier_pct': 0.0, 'min_value': 1.0, 'max_value': 5.0}
Total Spent: {'q1': 4.0, 'q3': 12.0, 'iqr': 8.0, 'lower_bound': -8.0, 'upper_bound': 24.0, 'outlier_count': 0, 'outlier_pct': 0.0, 'min_value': 1.0, 'max_value': 20.0}

Observations:
  • Both 'Quantity' and 'Price Per Unit' show no outliers, with values strictly ranging from 1.0 to 5.0, indicating a consistent data distribution that may simplify modeling efforts.
  • In contrast, 'Total Spent' has a wider range with a maximum of 20.0 and an upper bound of 24.0, suggesting potential for further investigation into high spending behaviors or data entry errors, despite no detected outliers.

============================================================
AGGREGATES ANALYSIS
============================================================
Item: dict with 2 items

Observations:
  • The 'unknown' and 'error' categories account for a significant 620 entries combined, indicating potential data quality issues that should be investigated to ensure accurate analysis.
  • The average price per unit for 'cookie' at 1.12 is notably lower than other items, suggesting a possible pricing strategy that may need to be reviewed for profitability.

============================================================
RELATIONSHIPS ANALYSIS
============================================================
correlation_matrix: dict with 3 items
strong_correlations: {}
data_integrity: dict with 5 items

Observations:
  • The correlation between 'Total Spent' and 'Quantity' is relatively strong at 0.655, indicating that higher quantities are associated with increased spending, which may warrant further investigation into pricing strategies.
  • Data integrity checks reveal that only 88.03% of records match the expected calculation of 'Quantity * Price Per Unit == Total Spent', suggesting potential data quality issues that need to be addressed before further analysis.

============================================================
TEMPORAL ANALYSIS
============================================================
Transaction Date: dict with 6 items

Observations:
  • The dataset shows a consistent monthly transaction count, with February having the highest at 1164, suggesting potential seasonal trends or promotional activities that should be investigated further.
  • Transaction activity is highest on Mondays (1798 transactions), indicating a possible pattern in consumer behavior that could inform marketing strategies or resource allocation.

============================================================
DISTRIBUTION ANALYSIS
============================================================
Quantity: dict with 6 items
Price Per Unit: dict with 6 items
Total Spent: dict with 6 items

Observations:
  • The 'Total Spent' variable shows moderate right skewness (0.696), indicating potential outliers or a long tail that could affect modeling; further investigation into high-value transactions is recommended.
  • Both 'Quantity' and 'Price Per Unit' are approximately symmetric with low skewness, suggesting they may not require transformation for analysis, but their relationship with 'Total Spent' should be explored to understand spending patterns.

============================================================
FINAL SYNTHESIS
============================================================

Summary:
The analysis reveals significant data quality concerns, particularly with the 'Item' column containing a high number of 'unknown' and 'error' entries, which could skew insights. Additionally, while the dataset is complete and free of duplicates, the relationship between 'Total Spent' and other variables suggests potential misreporting or outlier issues that warrant further investigation.

Recommendations:
  • Investigate and clean the 'Item' column to address the high number of 'unknown' and 'error' entries, ensuring accurate categorization for analysis.
  • Conduct a detailed review of transactions with 'Total Spent' values that deviate significantly from the mean to identify potential data entry errors or outlier behaviors.
  • Analyze pricing strategies for items, particularly the 'cookie', to assess profitability and competitiveness in the market based on the average price per unit.
  • Explore seasonal trends and consumer behavior patterns, especially focusing on peak transaction days and months, to inform targeted marketing strategies and resource allocation.
  • Implement data integrity checks to ensure that the calculation of 'Quantity * Price Per Unit' consistently matches 'Total Spent', addressing discrepancies to enhance data reliability.
```

</details>