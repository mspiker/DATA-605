
import csv
import re
import urllib.request
from html.parser import HTMLParser
from collections import defaultdict

# -----------------------------------------------------------------------------------
# Vose, R. S., Applequist, S., Squires, M., Durre, I., Menne, M. J., Williams, C. N., Jr.,
# Fenimore, C., Gleason, K., & Arndt, D. (2014). NOAA monthly U.S. climate divisional
# database (NClimDiv) [Data set: Monthly statewide average temperature, 1984–2025].
# NOAA National Climatic Data Center. https://doi.org/10.7289/V5M32STR
#
# In-text citation: (Vose et al., 2014)
#
# Monthly statewide average temperature data for 1984–2025 were obtained from the NOAA
# Monthly U.S. Climate Divisional Database (Vose et al., 2014). A Python script was used
# to calculate monthly temperature normals for 1991–2020.
# -----------------------------------------------------------------------------------

# --------------------------------------------------
# Configuration
# --------------------------------------------------

START_YEAR = 1984
END_YEAR = 2025

NORMAL_START_YEAR = 1991
NORMAL_END_YEAR = 2020

BASE_URL = (
    "https://www.ncei.noaa.gov/monitoring-content/"
    "data/us/climdiv/monthly/current/"
)

OUTPUT_FILE = "state_monthly_temperature_normals.csv"

STATE_NAMES = {
    "001": "Alabama", "002": "Arizona", "003": "Arkansas",
    "004": "California", "005": "Colorado",
    "006": "Connecticut", "007": "Delaware", "008": "Florida",
    "009": "Georgia", "010": "Idaho", "011": "Illinois",
    "012": "Indiana", "013": "Iowa", "014": "Kansas",
    "015": "Kentucky", "016": "Louisiana", "017": "Maine",
    "018": "Maryland", "019": "Massachusetts", "020": "Michigan",
    "021": "Minnesota", "022": "Mississippi", "023": "Missouri",
    "024": "Montana", "025": "Nebraska", "026": "Nevada",
    "027": "New Hampshire", "028": "New Jersey",
    "029": "New Mexico", "030": "New York",
    "031": "North Carolina", "032": "North Dakota",
    "033": "Ohio", "034": "Oklahoma", "035": "Oregon",
    "036": "Pennsylvania", "037": "Rhode Island",
    "038": "South Carolina", "039": "South Dakota",
    "040": "Tennessee", "041": "Texas", "042": "Utah",
    "043": "Vermont", "044": "Virginia", "045": "Washington",
    "046": "West Virginia", "047": "Wisconsin", "048": "Wyoming",
}


# --------------------------------------------------
# Locate the latest NOAA statewide temperature file
# --------------------------------------------------

class FileParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.files = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return

        for key, value in attrs:
            if key.lower() == "href" and value:
                filename = value.rstrip("/").split("/")[-1]

                if re.fullmatch(
                    r"climdiv-tmpcst-v1\.0\.0-\d{8}",
                    filename
                ):
                    self.files.append(filename)


def find_latest_file():
    request = urllib.request.Request(
        BASE_URL,
        headers={"User-Agent": "Python climate research"}
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        html = response.read().decode("utf-8", errors="replace")

    parser = FileParser()
    parser.feed(html)

    if not parser.files:
        raise RuntimeError(
            "Unable to find the NOAA statewide temperature file."
        )

    return max(parser.files, key=lambda name: name[-8:])


def download_data(filename):
    url = BASE_URL + filename

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Python climate research"}
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8", errors="replace"), url


# --------------------------------------------------
# Parse monthly statewide average temperatures
# --------------------------------------------------

def parse_temperature_data(source_text):
    # Key: (state code, year)
    # Value: list of 12 monthly temperatures
    data = {}

    for line in source_text.splitlines():
        fields = line.split()

        if len(fields) < 13:
            continue

        record_id = fields[0]

        if not re.fullmatch(r"\d{10}", record_id):
            continue

        state_code = record_id[0:3]
        geographic_level = record_id[3]
        element_code = record_id[4:6]
        year = int(record_id[6:10])

        # Statewide records use geographic level 0.
        # NOAA element 02 represents average temperature.
        if geographic_level != "0" or element_code != "02":
            continue

        if state_code not in STATE_NAMES:
            continue

        try:
            values = [float(value) for value in fields[1:13]]
        except ValueError:
            continue

        # NOAA uses -99.9 to indicate missing temperatures.
        values = [
            None if value <= -99.0 else value
            for value in values
        ]

        data[(state_code, year)] = values

    return data


# --------------------------------------------------
# Calculate monthly normals from 1991 through 2020
# --------------------------------------------------

def calculate_normals(data):
    # Key: (state code, month number)
    # Value: list of observed temperatures across normal years
    observations = defaultdict(list)

    for (state_code, year), monthly_values in data.items():
        if not NORMAL_START_YEAR <= year <= NORMAL_END_YEAR:
            continue

        for month_index, temperature in enumerate(monthly_values):
            if temperature is not None:
                month_number = month_index + 1
                observations[(state_code, month_number)].append(
                    temperature
                )

    normals = {}

    for key, values in observations.items():
        normals[key] = sum(values) / len(values)

    return normals


# --------------------------------------------------
# Create long-format output
# --------------------------------------------------

def create_output_rows(data, normals):
    rows = []

    for (state_code, year), monthly_values in data.items():
        if not START_YEAR <= year <= END_YEAR:
            continue

        for month_index, actual in enumerate(monthly_values):
            month_number = month_index + 1
            normal = normals.get((state_code, month_number))

            if actual is None or normal is None:
                difference = None
            else:
                difference = actual - normal

            rows.append({
                "State": STATE_NAMES[state_code],
                "State Code": state_code,
                "Year": year,
                "Month": month_number,
                "Average Temperature (F)": actual,
                "Normal Temperature (F)": normal,
                "Difference from Normal (F)": difference,
            })

    rows.sort(
        key=lambda row: (
            row["State Code"],
            row["Year"],
            row["Month"]
        )
    )

    return rows


# --------------------------------------------------
# Write CSV
# --------------------------------------------------

def write_csv(rows, filename):
    columns = [
        "State",
        "State Code",
        "Year",
        "Month",
        "Average Temperature (F)",
        "Normal Temperature (F)",
        "Difference from Normal (F)",
    ]

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as csvfile:
        writer = csv.DictWriter(
            csvfile,
            fieldnames=columns
        )
        writer.writeheader()

        for row in rows:
            formatted = row.copy()

            for column in columns[4:]:
                value = formatted[column]

                if value is not None:
                    formatted[column] = f"{value:.2f}"

            writer.writerow(formatted)


# --------------------------------------------------
# Main program
# --------------------------------------------------

def main():
    print("Finding the latest NOAA temperature file...")
    source_filename = find_latest_file()

    print("Downloading:", source_filename)
    source_text, source_url = download_data(source_filename)

    print("Parsing statewide monthly temperatures...")
    data = parse_temperature_data(source_text)

    if not data:
        raise RuntimeError(
            "No statewide temperature records found. "
            "Check the NOAA file format and record codes."
        )

    print("Calculating 1991-2020 monthly normals...")
    normals = calculate_normals(data)

    print("Preparing output...")
    rows = create_output_rows(data, normals)

    if not rows:
        raise RuntimeError("No output records were generated.")

    write_csv(rows, OUTPUT_FILE)

    print("\nCompleted successfully.")
    print("Source URL:", source_url)
    print("Output file:", OUTPUT_FILE)
    print("States represented:", len({
        row["State Code"] for row in rows
    }))
    print("Monthly rows:", f"{len(rows):,}")
    print(
        f"Observation years: {START_YEAR}-{END_YEAR}"
    )
    print(
        f"Normal baseline: {NORMAL_START_YEAR}-"
        f"{NORMAL_END_YEAR}"
    )

    print("\nFirst five records:")
    for row in rows[:5]:
        print(row)


if __name__ == "__main__":
    main()
