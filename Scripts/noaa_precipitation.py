
import csv
import re
import urllib.request
from html.parser import HTMLParser

# -----------------------------------------------------------------------------------
# Vose, R. S., Applequist, S., Squires, M., Durre, I., Menne, M. J., Williams, C. N., Jr.,
# Fenimore, C., Gleason, K., & Arndt, D. (2014). NOAA monthly U.S. climate divisional
# database (NClimDiv) [Data set: Monthly statewide precipitation, 1984–2025].
# NOAA National Climatic Data Center. https://doi.org/10.7289/V5M32STR
#
# In-text citation: (Vose et al., 2014)
#
# Monthly statewide precipitation data for 1984–2025 were obtained from the NOAA Monthly
# U.S. Climate Divisional Database (Vose et al., 2014). A Python script was used to
# extract and process the data.
# -----------------------------------------------------------------------------------

# --------------------------------------------------
# Configuration
# --------------------------------------------------

START_YEAR = 1984
END_YEAR = 2025
NORMAL_PERIOD_CODE = "0010"  # NOAA's 1991-2020 normal

BASE_URL = (
    "https://www.ncei.noaa.gov/monitoring-content/"
    "data/us/climdiv/monthly/current/"
)

OUTPUT_FILE = "state_monthly_precipitation.csv"

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
# Find the latest matching NOAA files
# --------------------------------------------------

class FileParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.names = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return

        for key, value in attrs:
            if key.lower() == "href" and value:
                name = value.rstrip("/").split("/")[-1]
                self.names.append(name)


def latest_file(pattern):
    request = urllib.request.Request(
        BASE_URL,
        headers={"User-Agent": "Python climate research"}
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        html = response.read().decode("utf-8", errors="replace")

    parser = FileParser()
    parser.feed(html)

    matches = [
        name for name in parser.names
        if re.fullmatch(pattern, name)
    ]

    if not matches:
        raise RuntimeError(
            f"Could not find a NOAA file matching: {pattern}"
        )

    return max(matches, key=lambda name: name[-8:])


def download_file(filename):
    request = urllib.request.Request(
        BASE_URL + filename,
        headers={"User-Agent": "Python climate research"}
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8", errors="replace")


# --------------------------------------------------
# Parse NOAA records
# --------------------------------------------------

def parse_records(text, expected_element, allowed_years=None):
    result = {}

    for line in text.splitlines():
        fields = line.split()

        if len(fields) < 13:
            continue

        record_id = fields[0]

        if not re.fullmatch(r"\d{10}", record_id):
            continue

        state_code = record_id[0:3]
        area_code = record_id[3]
        element_code = record_id[4:6]
        year_code = record_id[6:10]

        # Statewide records use area code 0.
        if area_code != "0":
            continue

        # NOAA element code 01 means precipitation.
        if element_code != expected_element:
            continue

        if state_code not in STATE_NAMES:
            continue

        if allowed_years is not None:
            if year_code not in allowed_years:
                continue

        try:
            values = [float(value) for value in fields[1:13]]
        except ValueError:
            continue

        result[(state_code, year_code)] = values

    return result


# --------------------------------------------------
# Build monthly output
# --------------------------------------------------

def main():
    actual_name = latest_file(
        r"climdiv-pcpnst-v1\.0\.0-\d{8}"
    )

    normal_name = latest_file(
        r"climdiv-norm-pcpnst-v1\.0\.0-\d{8}"
    )

    print("Downloading actual precipitation:", actual_name)
    actual_text = download_file(actual_name)

    print("Downloading precipitation normals:", normal_name)
    normal_text = download_file(normal_name)

    actual_data = parse_records(
        actual_text,
        expected_element="01",
        allowed_years={
            f"{year:04d}"
            for year in range(START_YEAR, END_YEAR + 1)
        }
    )

    normal_data = parse_records(
        normal_text,
        expected_element="01",
        allowed_years={NORMAL_PERIOD_CODE}
    )

    rows = []
    missing_normals = set()

    for (state_code, year_code), monthly_actual in actual_data.items():
        year = int(year_code)
        normal_values = normal_data.get(
            (state_code, NORMAL_PERIOD_CODE)
        )

        if normal_values is None:
            missing_normals.add(state_code)

        for month_index, actual in enumerate(monthly_actual):
            normal = (
                normal_values[month_index]
                if normal_values is not None
                else None
            )

            # NOAA's missing precipitation marker is -9.99.
            if actual <= -9.0:
                actual = None

            if normal is not None and normal <= -9.0:
                normal = None

            if actual is None or normal is None:
                difference = None
            else:
                difference = round(actual - normal, 2)

            rows.append({
                "State": STATE_NAMES[state_code],
                "State Code": state_code,
                "Year": year,
                "Month": month_index + 1,
                "Actual Precipitation (inches)": actual,
                "Normal Precipitation (inches)": normal,
                "Difference from Normal (inches)": difference,
            })

    rows.sort(
        key=lambda row: (
            row["State Code"],
            row["Year"],
            row["Month"]
        )
    )

    columns = [
        "State",
        "State Code",
        "Year",
        "Month",
        "Actual Precipitation (inches)",
        "Normal Precipitation (inches)",
        "Difference from Normal (inches)",
    ]

    with open(
        OUTPUT_FILE, "w", newline="", encoding="utf-8-sig"
    ) as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=columns)
        writer.writeheader()

        for row in rows:
            # Preserve two decimal places in precipitation values.
            formatted = row.copy()

            for column in columns[4:]:
                value = formatted[column]
                if value is not None:
                    formatted[column] = f"{value:.2f}"

            writer.writerow(formatted)

    print("\nCompleted.")
    print("Output:", OUTPUT_FILE)
    print("States represented:", len({
        row["State Code"] for row in rows
    }))
    print("Monthly records:", len(rows))
    print("Year range:", START_YEAR, "to", END_YEAR)
    print("Normal period: 1991-2020")
    print("Missing normal state codes:", sorted(missing_normals))


if __name__ == "__main__":
    main()
