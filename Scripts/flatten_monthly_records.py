"""Combine monthly CSVs into one record per state/year/month.

All source records are retained (a full outer join). Missing measurements stay
blank rather than becoming zero. Source files are never modified.
"""

import csv
from pathlib import Path

from create_tableau_files import (
    COMMON_KEY_COLUMN,
    INPUT_FILES,
    KEY_COLUMNS,
    SCRIPT_DIRECTORY,
)


OUTPUT_FILENAME = "state_monthly_flattened.csv"
IDENTITY_COLUMNS = ("State", *KEY_COLUMNS)


def flatten_records(input_directory: Path, output_path: Path) -> int:
    """Write the combined CSV and return the number of state-month records."""
    input_paths = [input_directory / filename for filename in INPUT_FILES]
    if output_path.resolve() in {path.resolve() for path in input_paths}:
        raise ValueError("The output path must not overwrite an input CSV.")

    records: dict[tuple[str, int, int], dict[str, str]] = {}
    output_fields = list(IDENTITY_COLUMNS)

    for input_path in input_paths:
        with input_path.open("r", newline="", encoding="utf-8-sig") as source:
            reader = csv.DictReader(source)
            fieldnames = reader.fieldnames
            if not fieldnames:
                raise ValueError(f"{input_path} has no CSV header.")
            if len(fieldnames) != len(set(fieldnames)):
                raise ValueError(f"{input_path} has duplicate column names.")
            missing_columns = set(IDENTITY_COLUMNS) - set(fieldnames)
            if missing_columns:
                raise ValueError(
                    f"{input_path} is missing required columns: "
                    f"{', '.join(sorted(missing_columns))}"
                )

            measurement_columns = [
                column for column in fieldnames if column not in IDENTITY_COLUMNS
            ]
            duplicate_columns = set(measurement_columns) & set(
                [*output_fields, COMMON_KEY_COLUMN]
            )
            if duplicate_columns:
                raise ValueError(
                    f"{input_path} has conflicting measurement columns: "
                    f"{', '.join(sorted(duplicate_columns))}"
                )
            output_fields.extend(measurement_columns)
            seen_keys: set[tuple[str, int, int]] = set()

            for row_number, row in enumerate(reader, start=2):
                location = f"{input_path}, row {row_number}"
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"{location} has a mismatched column count.")

                state = row["State"].strip()
                state_code = row["State Code"].strip()
                if not state or not state_code:
                    raise ValueError(f"{location} has a blank State or State Code.")
                try:
                    year = int(row["Year"])
                    month = int(row["Month"])
                except ValueError as error:
                    raise ValueError(
                        f"{location} has a non-integer Year or Month."
                    ) from error
                if year < 1 or not 1 <= month <= 12:
                    raise ValueError(f"{location} has an invalid Year or Month.")

                key = (state_code, year, month)
                if key in seen_keys:
                    raise ValueError(f"{location} has a duplicate state/year/month.")
                seen_keys.add(key)

                if key not in records:
                    records[key] = {
                        "State": state,
                        "State Code": state_code,
                        "Year": str(year),
                        "Month": str(month),
                        COMMON_KEY_COLUMN: f"{state_code}-{year:04d}-{month:02d}",
                    }
                record = records[key]
                if record["State"] != state:
                    raise ValueError(f"{location} has a conflicting State name.")
                record.update({column: row[column] for column in measurement_columns})

    output_fields.append(COMMON_KEY_COLUMN)
    with output_path.open("w", newline="", encoding="utf-8-sig") as destination:
        writer = csv.DictWriter(destination, fieldnames=output_fields)
        writer.writeheader()
        for key in sorted(records):
            writer.writerow(records[key])

    return len(records)


def main() -> None:
    output_path = SCRIPT_DIRECTORY / OUTPUT_FILENAME
    record_count = flatten_records(SCRIPT_DIRECTORY, output_path)
    print(f"Created: {output_path} ({record_count:,} records)")


if __name__ == "__main__":
    main()