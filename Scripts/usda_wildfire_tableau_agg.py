# -----------------------------------------------------------------------------------------
# Purpose:
#     Prepare the wildfire incident dataset for analysis and visualization in Tableau.
#     The script reads the source CSV, cleans state abbreviations and discovery dates,
#     converts fire sizes to numeric values, and excludes records without a usable state
#     or discovery date. It then groups the remaining incidents by state, year, and month.

# Expected output:
#     Writes state_monthly_wildfire_incidents_tableau.csv in the current working
#     directory. Each row represents one state and calendar month with at least one
#     usable incident record. The output includes State, Year, Month, Wildfire Incidents,
#     Acres Burned, and Records Missing Fire Size. Acreage is summed from available fire
#     sizes and rounded to two decimal places; records with missing fire sizes are still
#     counted as incidents, but do not contribute to Acres Burned. Rows are sorted by
#     state, year, and month. The script also prints load and aggregation totals.

# Input:
#     Expects state_monthly_wildfire_incidents_acres.csv in the current working
#     directory, with STATE, DISCOVERY_DATE (Unix milliseconds), and FIRE_SIZE columns.
# -----------------------------------------------------------------------------------------

import pandas as pd
from pathlib import Path

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

# Change this to the location of your downloaded file
INPUT_FILE = Path("state_monthly_wildfire_incidents_acres.csv")

OUTPUT_FILE = Path("state_monthly_wildfire_incidents_tableau.csv")

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

print("Loading wildfire dataset...")

df = pd.read_csv(
    INPUT_FILE,
    usecols=["STATE", "DISCOVERY_DATE", "FIRE_SIZE"],
    low_memory=False
)

print(f"Records loaded: {len(df):,}")

# --------------------------------------------------
# CLEAN AND PREPARE DATA
# --------------------------------------------------

# Standardize state abbreviations
df["STATE"] = df["STATE"].astype("string").str.strip().str.upper()

# Convert discovery date from Unix milliseconds
df["DISCOVERY_DATE"] = pd.to_datetime(
    df["DISCOVERY_DATE"],
    unit="ms",
    errors="coerce",
    utc=True
)

# Convert fire size to numeric
df["FIRE_SIZE"] = pd.to_numeric(
    df["FIRE_SIZE"],
    errors="coerce"
)

# Remove records without usable state or discovery date
df = df.dropna(subset=["STATE", "DISCOVERY_DATE"])

# Extract year and month
df["Year"] = df["DISCOVERY_DATE"].dt.year
df["Month"] = df["DISCOVERY_DATE"].dt.month

# --------------------------------------------------
# AGGREGATE
# --------------------------------------------------

monthly = (
    df.groupby(["STATE", "Year", "Month"], as_index=False)
      .agg(
          **{
              "Wildfire Incidents": ("STATE", "size"),
              "Acres Burned": ("FIRE_SIZE", "sum"),
              "Records Missing Fire Size": ("FIRE_SIZE", "count")
          }
      )
)

# Calculate missing fire-size records correctly
monthly["Records Missing Fire Size"] = (
    monthly["Wildfire Incidents"] -
    monthly["Records Missing Fire Size"]
)

# Rename state column
monthly = monthly.rename(columns={"STATE": "State"})

# Round acreage to two decimal places
monthly["Acres Burned"] = monthly["Acres Burned"].round(2)

# Sort for Tableau
monthly = monthly.sort_values(
    ["State", "Year", "Month"]
)

# --------------------------------------------------
# EXPORT
# --------------------------------------------------

monthly.to_csv(OUTPUT_FILE, index=False)

print("\nAggregation complete!")
print(f"Output file: {OUTPUT_FILE.resolve()}")
print(f"Aggregated rows: {len(monthly):,}")
print(
    f"Total wildfire incidents: "
    f"{monthly['Wildfire Incidents'].sum():,}"
)
print(
    f"Total acres recorded: "
    f"{monthly['Acres Burned'].sum():,.2f}"
)
print(
    f"Fire records missing size: "
    f"{monthly['Records Missing Fire Size'].sum():,}"
)
