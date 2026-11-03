"""
Create Tableau-ready copies of configured monthly data files with a shared join key.

The key is built from State Code, Year, and Month in the format
STATECODE-YYYY-MM (for example, 001-1984-01). Original files are left unchanged;
each output is written beside its input with "tableau_" added to the filename.
Update INPUT_FILES to change which CSV files are processed.
"""

import csv
from pathlib import Path


INPUT_FILES = [
    "state_monthly_drought_pdsi.csv",
    "state_monthly_precipitation.csv",
    "state_monthly_temperature_normals.csv",
    "state_monthly_wildfire_incidents_acres.csv",
]

KEY_COLUMNS = ("State Code", "Year", "Month")
COMMON_KEY_COLUMN = "Common Key"
SCRIPT_DIRECTORY = Path(__file__).resolve().parent


def create_tableau_copy(input_path: Path) -> Path:
    """Write one CSV copy with a common state/year/month key and return its path."""
    output_path = input_path.with_name(f"tableau_{input_path.name}")

    with input_path.open("r", newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise ValueError(f"{input_path} has no CSV header.")

        missing_columns = [column for column in KEY_COLUMNS if column not in fieldnames]
        if missing_columns:
            raise ValueError(
                f"{input_path} is missing required column(s): "
                f"{', '.join(missing_columns)}"
            )

        output_fields = list(fieldnames)
        if COMMON_KEY_COLUMN not in output_fields:
            output_fields.append(COMMON_KEY_COLUMN)

        with output_path.open("w", newline="", encoding="utf-8-sig") as destination:
            writer = csv.DictWriter(destination, fieldnames=output_fields)
            writer.writeheader()

            for row_number, row in enumerate(reader, start=2):
                if None in row:
                    raise ValueError(
                        f"{input_path}, row {row_number}, has more values than headers."
                    )

                state_code = (row.get("State Code") or "").strip()
                year_text = (row.get("Year") or "").strip()
                month_text = (row.get("Month") or "").strip()
                if not state_code or not year_text or not month_text:
                    raise ValueError(
                        f"{input_path}, row {row_number}, has a blank State Code, "
                        "Year, or Month."
                    )

                try:
                    year = int(year_text)
                    month = int(month_text)
                except ValueError as error:
                    raise ValueError(
                        f"{input_path}, row {row_number}, has a non-integer Year or Month."
                    ) from error

                if year < 1 or not 1 <= month <= 12:
                    raise ValueError(
                        f"{input_path}, row {row_number}, has an invalid Year or Month."
                    )

                row[COMMON_KEY_COLUMN] = f"{state_code}-{year:04d}-{month:02d}"
                writer.writerow(row)

    return output_path


def main() -> None:
    for filename in INPUT_FILES:
        input_path = SCRIPT_DIRECTORY / filename
        if not input_path.is_file():
            raise FileNotFoundError(f"Input CSV not found: {input_path}")

        output_path = create_tableau_copy(input_path)
        print(f"Created: {output_path}")


if __name__ == "__main__":
    main()
