# DATA-605
Scripts to help source data for DATA 605 Data Visualization Class.

## Flatten Monthly Records

From the repository root, run:

```powershell
python Scripts/flatten_monthly_records.py
```

This combines the four monthly drought, precipitation, temperature, and wildfire
CSVs into `Scripts/state_monthly_flattened.csv`, with one row per State Code,
Year, and Month. All measurements and a Tableau Common Key are included. Months
present in any source are retained; missing measurements are blank, not zero.
The original files are unchanged. No third-party packages are required.
