
import csv
import re
import urllib.request
from html.parser import HTMLParser

# -----------------------------------------------------------------------------------
# Vose, R. S., Applequist, S., Squires, M., Durre, I., Menne, M. J., Williams, C. N., Jr.,
# Fenimore, C., Gleason, K., & Arndt, D. (2014). NOAA monthly U.S. climate divisional
# database (NClimDiv) [Data set: Monthly statewide Palmer Drought Severity Index (PDSI),
# 1984–2025]. NOAA National Climatic Data Center. https://doi.org/10.7289/V5M32STR
#
# In-text citation: (Vose et al., 2014)
#
# Monthly statewide PDSI data for 1984–2025 were obtained from the NOAA Monthly U.S.
# Climate Divisional Database (Vose et al., 2014). A Python script was used to extract
# the data and assign drought-category labels using the stated PDSI thresholds.
# -----------------------------------------------------------------------------------

# --------------------------------------------------
# Configuration
# --------------------------------------------------

START_YEAR = 1984
END_YEAR = 2025

BASE_URL = (
    "https://www.ncei.noaa.gov/monitoring-content/"
    "data/us/climdiv/monthly/current/"
)

OUTPUT_FILE = "state_monthly_drought_pdsi.csv"

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
# Find latest NOAA PDSI file
# --------------------------------------------------

class FileParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.files = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            for key, value in attrs:
                if key.lower() == "href" and value:
                    filename = value.rstrip("/").split("/")[-1]

                    if re.fullmatch(
                        r"climdiv-pdsist-v1\.0\.0-\d{8}",
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
        raise RuntimeError("Could not locate NOAA PDSI data file.")

    return max(parser.files, key=lambda name: name[-8:])


# --------------------------------------------------
# Download NOAA data
# --------------------------------------------------

def download_data(filename):
    url = BASE_URL + filename

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Python climate research"}
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8", errors="replace"), url


# --------------------------------------------------
# Classify drought severity
# --------------------------------------------------

def classify_pdsi(value):

    if value is None:
        return "Missing"

    if value <= -4.0:
        return "Extreme Drought"
    elif value <= -3.0:
        return "Severe Drought"
    elif value <= -2.0:
        return "Moderate Drought"
    elif value <= -1.0:
        return "Mild Drought"
    elif value <= -0.5:
        return "Incipient Drought"
    elif value < 0.5:
        return "Near Normal"
    elif value < 1.0:
        return "Slightly Wet"
    elif value < 2.0:
        return "Moderately Wet"
    elif value < 3.0:
        return "Very Wet"
    else:
        return "Extremely Wet"


# --------------------------------------------------
# Parse NOAA records
# --------------------------------------------------

def parse_data(source_text):

    records = []

    for line in source_text.splitlines():

        fields = line.split()

        if len(fields) < 13:
            continue

        record_id = fields[0]

        if not re.fullmatch(r"\d{10}", record_id):
            continue

        # NOAA record identifier:
        # First 3 characters = State code
        # Middle 3 characters = File-specific identifier
        # Last 4 characters = Year

        state_code = record_id[0:3]
        year = int(record_id[6:10])

        if state_code not in STATE_NAMES:
            continue

        if not START_YEAR <= year <= END_YEAR:
            continue

        try:
            monthly_values = [
                float(value) for value in fields[1:13]
            ]
        except ValueError:
            continue

        if len(monthly_values) != 12:
            continue

        for month_number, value in enumerate(monthly_values, 1):

            # Exclude NOAA missing-value markers.
            if value <= -99.0:
                pdsi = None
            else:
                pdsi = round(value, 2)

            records.append({
                "State": STATE_NAMES[state_code],
                "State Code": state_code,
                "Year": year,
                "Month": month_number,
                "PDSI": pdsi,
                "Drought Category": classify_pdsi(pdsi),
            })

    records.sort(
        key=lambda row: (
            row["State Code"],
            row["Year"],
            row["Month"]
        )
    )

    return records


# --------------------------------------------------
# Export CSV
# --------------------------------------------------

def save_csv(records):

    columns = [
        "State",
        "State Code",
        "Year",
        "Month",
        "PDSI",
        "Drought Category",
    ]

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as csvfile:

        writer = csv.DictWriter(
            csvfile,
            fieldnames=columns
        )

        writer.writeheader()
        writer.writerows(records)


# --------------------------------------------------
# Main program
# --------------------------------------------------

def main():

    print("Locating latest NOAA PDSI file...")

    filename = find_latest_file()

    print("Downloading:", filename)

    source_text, source_url = download_data(filename)

    print("Processing monthly drought data...")

    records = parse_data(source_text)

    if not records:
        raise RuntimeError("No PDSI records were generated.")

    save_csv(records)

    states = len({
        record["State Code"] for record in records
    })

    print("\nProcessing complete.")
    print("Source URL:", source_url)
    print("Output file:", OUTPUT_FILE)
    print("States represented:", states)
    print("Monthly records:", f"{len(records):,}")
    print(f"Years: {START_YEAR}-{END_YEAR}")

    print("\nFirst five records:")

    for record in records[:5]:
        print(record)


if __name__ == "__main__":
    main()
