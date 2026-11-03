
import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# -----------------------------------------------------------------------------------
# U.S. Department of Agriculture, Forest Service. (n.d.). Fire occurrence (current
# edition) [Data set: State-by-month wildfire incident counts and acres burned,
# 1992–2024]. ArcGIS REST Services Directory.
# https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_FireOccurrenceCurrentEdition_01/MapServer/0
#
# In-text citation: (U.S. Department of Agriculture, Forest Service, n.d.)
#
# Wildfire occurrence records for 1992–2024 were obtained from the U.S. Department of
# Agriculture, Forest Service (n.d.). A Python script was used to aggregate incidents
# and recorded acres burned by state and month.
#
# Documentation for the ArcGIS REST Services Directory can be found at the following URLs:
# https://developers.arcgis.com/rest/services-reference/
# https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/
# https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_FireOccurrenceCurrentEdition_01/MapServer/0
#
# -----------------------------------------------------------------------------------

# --------------------------------------------------
# Configuration
# --------------------------------------------------

START_YEAR = 1992
END_YEAR = 2024

OUTPUT_FILE = "state_monthly_wildfire_incidents_acres.csv"

API_URL = (
    "https://apps.fs.usda.gov/arcx/rest/services/"
    "EDW/EDW_FireOccurrenceCurrentEdition_01/"
    "MapServer/0/query"
)

PAGE_SIZE = 2000
REQUEST_TIMEOUT = 120
MAX_REQUEST_ATTEMPTS = 4
INITIAL_RETRY_DELAY = 2

STATES = {
    "AL": ("001", "Alabama"),
    "AZ": ("002", "Arizona"),
    "AR": ("003", "Arkansas"),
    "CA": ("004", "California"),
    "CO": ("005", "Colorado"),
    "CT": ("006", "Connecticut"),
    "DE": ("007", "Delaware"),
    "FL": ("008", "Florida"),
    "GA": ("009", "Georgia"),
    "ID": ("010", "Idaho"),
    "IL": ("011", "Illinois"),
    "IN": ("012", "Indiana"),
    "IA": ("013", "Iowa"),
    "KS": ("014", "Kansas"),
    "KY": ("015", "Kentucky"),
    "LA": ("016", "Louisiana"),
    "ME": ("017", "Maine"),
    "MD": ("018", "Maryland"),
    "MA": ("019", "Massachusetts"),
    "MI": ("020", "Michigan"),
    "MN": ("021", "Minnesota"),
    "MS": ("022", "Mississippi"),
    "MO": ("023", "Missouri"),
    "MT": ("024", "Montana"),
    "NE": ("025", "Nebraska"),
    "NV": ("026", "Nevada"),
    "NH": ("027", "New Hampshire"),
    "NJ": ("028", "New Jersey"),
    "NM": ("029", "New Mexico"),
    "NY": ("030", "New York"),
    "NC": ("031", "North Carolina"),
    "ND": ("032", "North Dakota"),
    "OH": ("033", "Ohio"),
    "OK": ("034", "Oklahoma"),
    "OR": ("035", "Oregon"),
    "PA": ("036", "Pennsylvania"),
    "RI": ("037", "Rhode Island"),
    "SC": ("038", "South Carolina"),
    "SD": ("039", "South Dakota"),
    "TN": ("040", "Tennessee"),
    "TX": ("041", "Texas"),
    "UT": ("042", "Utah"),
    "VT": ("043", "Vermont"),
    "VA": ("044", "Virginia"),
    "WA": ("045", "Washington"),
    "WV": ("046", "West Virginia"),
    "WI": ("047", "Wisconsin"),
    "WY": ("048", "Wyoming"),
    "AK": ("049", "Alaska"),
    "HI": ("050", "Hawaii"),
}

STATE_LOOKUP = {}

for abbreviation, (code, name) in STATES.items():
    STATE_LOOKUP[abbreviation.upper()] = (code, name)
    STATE_LOOKUP[name.upper()] = (code, name)


# --------------------------------------------------
# Retrieve one page of wildfire records
# --------------------------------------------------

def get_page(offset):

    parameters = {
        "where": (
            f"fire_year >= {START_YEAR} "
            f"AND fire_year <= {END_YEAR}"
        ),
        "outFields": "state,discovery_date,FIRE_SIZE",
        "returnGeometry": "false",
        "orderByFields": "OBJECTID ASC",
        "resultOffset": offset,
        "resultRecordCount": PAGE_SIZE,
        "f": "json",
    }

    url = API_URL + "?" + urllib.parse.urlencode(parameters)

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Climate Research Python Script"}
    )

    for attempt in range(1, MAX_REQUEST_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(
                request,
                timeout=REQUEST_TIMEOUT
            ) as response:
                result = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as error:
            if error.code != 429 and error.code < 500:
                raise
            last_error = error
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error

        if attempt == MAX_REQUEST_ATTEMPTS:
            raise RuntimeError(
                f"Could not retrieve wildfire data page at offset {offset} "
                f"after {MAX_REQUEST_ATTEMPTS} attempts."
            ) from last_error

        delay = INITIAL_RETRY_DELAY * (2 ** (attempt - 1))
        print(
            f"Request for offset {offset} failed ({last_error}); "
            f"retrying in {delay} seconds "
            f"(attempt {attempt + 1}/{MAX_REQUEST_ATTEMPTS})..."
        )
        time.sleep(delay)

    if "error" in result:
        raise RuntimeError(f"Forest Service API error: {result['error']}")

    return result


# --------------------------------------------------
# Retrieve and aggregate wildfire records
# --------------------------------------------------

def retrieve_wildfires():

    # Key: state abbreviation, year, month
    # Value: [incident count, total acres burned]

    totals = {}

    offset = 0
    total_records = 0
    missing_acres = 0

    print("Connecting to USDA Forest Service data service...")

    while True:

        result = get_page(offset)
        features = result.get("features", [])

        if not features:
            break

        for feature in features:

            attributes = feature.get("attributes", {})

            state_value = attributes.get("state")
            discovery_date = attributes.get("discovery_date")
            fire_size = attributes.get("fire_size")

            if not state_value or discovery_date is None:
                continue

            state_key = str(state_value).strip().upper()

            if state_key not in STATE_LOOKUP:
                continue

            fire_date = datetime.fromtimestamp(
                discovery_date / 1000,
                tz=timezone.utc
            )

            year = fire_date.year
            month = fire_date.month

            if not START_YEAR <= year <= END_YEAR:
                continue

            key = (state_key, year, month)

            if key not in totals:
                totals[key] = [0, 0.0]

            # Count the individual wildfire.
            totals[key][0] += 1

            # Add final recorded fire size in acres.
            if fire_size is not None:
                totals[key][1] += float(fire_size)
            else:
                missing_acres += 1

        total_records += len(features)
        offset += len(features)

        print(f"Retrieved {total_records:,} records...")

        if len(features) < PAGE_SIZE:
            break

        time.sleep(0.15)

    return totals, total_records, missing_acres


# --------------------------------------------------
# Create complete state/month/year output
# --------------------------------------------------

def create_output(totals):

    rows = []

    for abbreviation, (state_code, state_name) in STATES.items():

        for year in range(START_YEAR, END_YEAR + 1):

            for month in range(1, 13):

                key = (abbreviation, year, month)

                incidents, acres = totals.get(key, [0, 0.0])

                rows.append({
                    "State": state_name,
                    "State Code": state_code,
                    "Year": year,
                    "Month": month,
                    "Wildfire Incidents": incidents,
                    "Acres Burned": round(acres, 2),
                })

    return rows


# --------------------------------------------------
# Save CSV
# --------------------------------------------------

def save_csv(rows):

    columns = [
        "State",
        "State Code",
        "Year",
        "Month",
        "Wildfire Incidents",
        "Acres Burned",
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
        writer.writerows(rows)


# --------------------------------------------------
# Main program
# --------------------------------------------------

def main():

    print(
        f"Retrieving wildfire records from "
        f"{START_YEAR} through {END_YEAR}..."
    )

    totals, total_records, missing_acres = retrieve_wildfires()

    print("\nCreating monthly state totals...")

    rows = create_output(totals)

    save_csv(rows)

    total_incidents = sum(value[0] for value in totals.values())
    total_acres = sum(value[1] for value in totals.values())

    print("\nProcessing complete.")
    print("Source records retrieved:", f"{total_records:,}")
    print("Incidents counted:", f"{total_incidents:,}")
    print("Total recorded acres burned:", f"{total_acres:,.2f}")
    print("Records with missing fire size:", f"{missing_acres:,}")
    print("States represented:", len(STATES))
    print("Output rows:", f"{len(rows):,}")
    print("Output file:", OUTPUT_FILE)

    print("\nFirst five records:")

    for row in rows[:5]:
        print(row)


if __name__ == "__main__":
    main()
