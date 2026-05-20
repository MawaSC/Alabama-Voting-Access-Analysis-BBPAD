import geopandas as gpd
import pandas as pd
pd.set_option('display.max_columns', None)

file_path = "data/raw/polling_places/Al_Polls_Flood_SLED.shp"

# Load Alabama polling place shapefile provided by SPLC/client.
# Contains precinct names, addresses, counties, and geographic coordinates.

polls = gpd.read_file(file_path)

# Load Alabama Census Tracts (2020 Census TIGER/Line boundaries).
# Used for demographic analysis and spatial joins.

tracts = gpd.read_file("data/raw/Alabama_Census_Tracts_2020/Alabama_Census_Tracts%2C_2020.shp")

# Load hospital locations for comparative civic accessibility analysis.

hospitals = gpd.read_file("data/raw/Hospitals/Hospitals.shp")

print("Polls CRS:", polls.crs)
print("Tracts CRS:", tracts.crs)

#Results:
#Location: Longitude, Latitude
#Voting/Precinct: Precinct, PrecintNu, Country
#Address info: Address, City, Zip
#Flood/Haxard Metabada: FLD_ZONE, ZONE_SUBTY
#MatchType, NumMatch

#Focus on specific counties within Alabama, those included in the black belt
gdf_clean = polls[['County', 'Precinct', 'Address', 'geometry']]
black_belt = [
    "Montgomery", "Dallas", "Perry", "Lowndes", "Sumter",
    "Wilcox", "Greene", "Hale", "Bullock", "Macon"
]

#If county is in the black belt, print out the county and the count of polls
bb_data = polls[polls['County'].isin(black_belt)]
print(bb_data.head())
print(polls['County'].value_counts())


polls_clean = polls[['Precinct', 'Address', 'City', 'Zip', 'County', 'geometry']]

#Will be extracting specifically these variables - Converted to US National Albers

datasets = [polls_clean, tracts, hospitals]

for gdf in datasets:
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)

# Reproject all spatial datasets into a projected CRS (EPSG:5070).
# This is critical because distance calculations in latitude/longitude
# are inaccurate for measuring miles.

polls_clean = polls_clean.to_crs(epsg=5070)
tracts = tracts.to_crs(epsg=5070)
hospitals = hospitals.to_crs(epsg=5070)

print("Projected CRS:", polls_clean.crs)

print("Poll bounds:", polls_clean.total_bounds)
print("Tract bounds:", tracts.total_bounds)

# Remove invalid or null geometries to prevent spatial operation errors.

tracts = tracts[tracts.geometry.is_valid & tracts.geometry.notnull()].copy()
polls_clean = polls_clean[polls_clean.geometry.is_valid & polls_clean.geometry.notnull()].copy()


polls_clean = polls_clean[polls_clean["County"] == "Montgomery"].copy()
tracts = tracts[tracts["COUNTYFP20"] == "101"].copy()

if "County" in hospitals.columns:
    hospitals = hospitals[
        hospitals["County"] == "Montgomery"
    ].copy()


tract_centroids = tracts.copy()

# Convert census tract polygons into centroid points.
# Centroids act as representative population center points
# for tract-level accessibility calculations.
tract_centroids["centroid"] = tract_centroids.geometry.centroid

# Drop original polygon geometry completely
tract_centroids = tract_centroids.drop(columns=["geometry"])

# Now set centroid as only geometry
tract_centroids = gpd.GeoDataFrame(
    tract_centroids,
    geometry="centroid",
    crs=tracts.crs
)

if "GEOID20" in tract_centroids.columns:
    tract_centroids = tract_centroids.rename(columns={"GEOID20": "GEOID"})

polls_sindex = polls_clean.sindex

# Compute nearest polling location for each census tract centroid.
# Returns polling location metadata and Euclidean distance in meters.

def nearest_distance(point, gdf):
    nearest_geom = gdf.geometry.distance(point).min()
    return nearest_geom

def nearest_poll_info(point, polls_gdf):
    distances = polls_gdf.geometry.distance(point)
    nearest_idx = distances.idxmin()
    nearest_poll = polls_gdf.loc[nearest_idx]

    return pd.Series({
        "nearest_poll_name": nearest_poll["Precinct"],
        "nearest_poll_address": nearest_poll["Address"],
        "nearest_poll_city": nearest_poll["City"],
        "nearest_poll_m": distances.min()
    })

nearest_info = tract_centroids.geometry.apply(
    lambda x: nearest_poll_info(x, polls_clean)
)

def nearest_school_info(point, schools_gdf):

    distances = schools_gdf.geometry.distance(point)

    nearest_idx = distances.idxmin()

    nearest_school = schools_gdf.loc[nearest_idx]

    return pd.Series({
        "nearest_school_distance_miles":
            distances.min() / 1609.34
    })


def nearest_hospital_info(point, hospitals_gdf):

    distances = hospitals_gdf.geometry.distance(point)

    nearest_idx = distances.idxmin()

    nearest_hospital = hospitals_gdf.loc[nearest_idx]

    return pd.Series({
        "nearest_hospital_distance_miles":
            distances.min() / 1609.34
    })

tract_centroids = pd.concat([tract_centroids, nearest_info], axis=1)

hospital_info = tract_centroids.geometry.apply(
    lambda x: nearest_hospital_info(x, hospitals)
)

tract_centroids = pd.concat([
    tract_centroids,
    hospital_info
], axis=1)

tract_centroids["nearest_poll_miles"] = tract_centroids["nearest_poll_m"] / 1609.34


print(tract_centroids[["GEOID", "nearest_poll_miles"]].head())
print(tract_centroids["nearest_poll_miles"].describe())


tract_centroids.to_csv("tract_polling_distances.csv", index = False)

#Analysis Based Questions
#How many communities are more than 5 miles from a polling place?

far_tracts = tract_centroids[tract_centroids["nearest_poll_miles"] > 5]
print("Number of tracts > 5 miles:", len(far_tracts))

print(tracts.columns)

tract_info = tracts[[
    "GEOID",
    "NAMELSAD20",
    "COUNTYFP20",
    "POP20",
    "WHITE",
    "BLACK",
    "ASIAN",
    "AIAN",
    "NHPI",
    "OTHER",
    "TWOPLUS",
    "HISP"
]].copy()

# Make sure GEOID is clean in tables
tract_centroids["GEOID"] = tract_centroids["GEOID"].astype(str)
tract_info["GEOID"] = tract_info["GEOID"].astype(str)

# Drop duplicate GEOID columns if they exist
tract_centroids = tract_centroids.loc[:, ~tract_centroids.columns.duplicated()]
tract_info = tract_info.loc[:, ~tract_info.columns.duplicated()]

# Merge
final_df = pd.merge(
    tract_centroids,
    tract_info,
    on="GEOID",
    how="left",
    suffixes=("", "_drop")
)

final_df = final_df.loc[:, ~final_df.columns.duplicated()]

final_df = final_df[[c for c in final_df.columns if not c.endswith("_drop")]]

final_df = final_df[[
    "GEOID",
    "NAMELSAD20",
    "COUNTYFP20",
    "POP20",
    "WHITE",
    "BLACK",
    "ASIAN",
    "AIAN",
    "NHPI",
    "OTHER",
    "TWOPLUS",
    "HISP",
    "nearest_poll_miles",
    "nearest_hospital_distance_miles",

    "centroid"
]].copy()


# Make sure geometry column is clean and single
final_gdf = final_df.copy()

# Ensure correct geometry column
final_gdf = gpd.GeoDataFrame(
    final_gdf,
    geometry="centroid",
    crs=tracts.crs
)

# Drop duplicate column names
final_gdf = final_gdf.loc[:, ~final_gdf.columns.duplicated()]

# Make sure no leftover geometry conflicts exist
final_gdf = final_gdf.drop(columns=[
    col for col in final_gdf.columns
    if col != "centroid" and "geom" in col.lower()
], errors="ignore")

# Export
final_gdf.to_file("tract_polling_distances.geojson", driver="GeoJSON")

# Categorize polling accessibility into qualitative levels.
# Used later for visualization and dashboard display.

def access_level(miles):
    if miles < 1:
        return "Very Close"
    elif miles < 3:
        return "Moderate"
    elif miles < 5:
        return "Limited"
    else:
        return "Poor Access"

tract_centroids["Access_Level"] = tract_centroids["nearest_poll_miles"].apply(access_level)

final_df["Access_Level"] = final_df["nearest_poll_miles"].apply(access_level)

final_df.drop(columns=["centroid"]).to_csv(
    "final_polling_access_table.csv",
    index=False
)

import matplotlib.pyplot as plt
import geopandas as gpd

map_gdf = gpd.GeoDataFrame(
    final_df,
    geometry="centroid",
    crs=tracts.crs
)

fig, ax = plt.subplots(1, 1, figsize=(12, 10))

final_gdf.plot(
    column="nearest_poll_miles",
    cmap="YlOrRd",
    legend=True,
    ax=ax
)

ax.set_title("Polling Accessibility by Census Tract (Alabama)", fontsize=14)
ax.set_axis_off()

plt.savefig(
    "alabama_polling_access_map.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

far = map_gdf[map_gdf["nearest_poll_miles"] > 5]

for idx, row in far.iterrows():
    ax.annotate(
        text=row["GEOID"],
        xy=(row.centroid.x, row.centroid.y),
        fontsize=8,
        color="black"
    )

plt.show()

#USER INPUT SYSTEM:
# 1. A precinct name
# 2. An address or ZIP code
#
# The system geocodes the input and returns:
# - Nearest polling place
# - Accessibility level
# - Census tract
# - Racial demographic breakdown

from geopy.geocoders import Nominatim
from shapely.geometry import Point

# Geocode user-entered addresses using OpenStreetMap Nominatim.
# Converts text input into geographic coordinates.

geolocator = Nominatim(user_agent="polling_app")

def get_point_from_input(user_input):
    # Try precinct first
    match = polls_clean[polls_clean["Precinct"].str.lower() == user_input.lower()]

    if not match.empty:
        return match.geometry.iloc[0], "precinct"

    # Otherwise treat as address
    location = geolocator.geocode(user_input + ", Montgomery, Alabama")

    if location is None:
        return None, None

    point = Point(location.longitude, location.latitude)

    gdf_point = gpd.GeoDataFrame(
        {"input": [user_input]},
        geometry=[point],
        crs="EPSG:4326"
    ).to_crs(polls_clean.crs)

    return gdf_point.geometry.iloc[0], "address"

def find_tract_for_point(point, tracts_gdf):
    match = tracts_gdf[tracts_gdf.contains(point)]
    if match.empty:
        return None
    return match.iloc[0]


def get_race_breakdown(tract_row):
    total = tract_row["POP20"]

    if total == 0:
        return {}

    def pct(val):
        return round((val / total) * 100, 2)

    return {
        "total_population": int(total),
        "white_pct": pct(tract_row["WHITE"]),
        "black_pct": pct(tract_row["BLACK"]),
        "asian_pct": pct(tract_row["ASIAN"]),
        "aian_pct": pct(tract_row["AIAN"]),
        "nhpi_pct": pct(tract_row["NHPI"]),
        "other_pct": pct(tract_row["OTHER"]),
        "two_plus_pct": pct(tract_row["TWOPLUS"]),
        "hispanic_pct": pct(tract_row["HISP"])
    }

# Core API-style function used for frontend/dashboard integration.
# Returns structured JSON output containing polling accessibility
# and demographic information for a user-entered location.

def get_nearest_poll(user_input):

    point, input_type = get_point_from_input(user_input)

    if point is None:
        return {"error": "Input not found"}

    temp = polls_clean.copy()
    temp["distance_m"] = temp.geometry.distance(point)

    nearest = temp.loc[temp["distance_m"].idxmin()]

    miles = float(nearest["distance_m"] / 1609.34)

    tract_row = find_tract_for_point(point, tracts)

    if tract_row is not None:
        race_data = get_race_breakdown(tract_row)
        tract_id = tract_row["GEOID"]
    else:
        race_data = {}
        tract_id = None

    return {
        "input_type": input_type,
        "input": user_input,

        "nearest_polling_location": {
            "precinct": nearest["Precinct"],
            "address": nearest["Address"],
            "city": nearest["City"],
            "distance_miles": round(miles, 2),
            "access_level": access_level(miles)
        },

        "census_tract": tract_id,
        "race_breakdown": race_data
    }

# Test Input

print(get_nearest_poll("Whitfield Community Center"))
print(get_nearest_poll("36104 Montgomery AL"))

# Export


final_gdf = gpd.GeoDataFrame(
    tract_centroids,
    geometry="centroid",
    crs=tracts.crs
)

final_gdf.to_file("tract_polling_distances.geojson", driver="GeoJSON")

import json

# Example inputs
results = [
    get_nearest_poll("36104 Montgomery AL"),
    get_nearest_poll("36106 Montgomery AL"),
    get_nearest_poll("36109 Montgomery AL"),
    get_nearest_poll("36116 Montgomery AL"),
    get_nearest_poll("36117 Montgomery AL"),
    get_nearest_poll("Alabama State University"),
    get_nearest_poll("Houston Hills Community Center"),
    get_nearest_poll("Whitfield Community Center"),
    get_nearest_poll("Dalraida Elementary School"),
    get_nearest_poll("Carver High School"),
    get_nearest_poll("Baptist Medical Center East"),
    get_nearest_poll("Baptist Medical Center South"),
    get_nearest_poll("Jackson Hospital")
]

# Convert numpy floats to normal floats
def clean_result(r):
    return {
        k: float(v) if hasattr(v, "item") else v
        for k, v in r.items()
    }

results_clean = [clean_result(r) for r in results]

# Save sample API outputs to JSON.
# This file can later be consumed directly by a frontend application.

with open("polling_api_output.json", "w") as f:
    json.dump(results_clean, f, indent=4)

print("JSON file saved!")

# VISUALIZATION SECTION
# Generates exploratory analysis figures for:
# - polling accessibility
# - racial disparities
# - healthcare proximity
# - infrastructure comparisons

import matplotlib.pyplot as plt

# Distance distribution
plt.figure()
final_df["nearest_poll_miles"].hist(bins=20)
plt.title("Distribution of Distance to Polling Locations")
plt.xlabel("Miles")
plt.ylabel("Number of Tracts")
plt.savefig("distance_distribution.png")
plt.show()

# Access levels
plt.figure(figsize=(8,5))
final_df["Access_Level"].value_counts().plot(kind="bar")
plt.title("Polling Access Levels")
plt.xlabel("Access Level")
plt.ylabel("Number of Tracts")
plt.xticks(fontsize=9)
plt.xticks(rotation=20)
plt.tight_layout()

plt.savefig(
    "access_levels.png",
    dpi=300,
    bbox_inches="tight"
)
plt.savefig("access_levels.png")
plt.show()

# Race vs distance black
plt.figure()
final_df["pct_black"] = final_df["BLACK"] / final_df["POP20"]

plt.scatter(final_df["pct_black"], final_df["nearest_poll_miles"])
plt.title("Distance vs % Black Population")
plt.xlabel("% Black Population")
plt.ylabel("Distance (miles)")
plt.savefig("race_vs_distance_black.png")
plt.show()

# Race vs distance black
plt.figure()
final_df["pct_hisp"] = final_df["HISP"] / final_df["POP20"]

plt.scatter(final_df["pct_hisp"], final_df["nearest_poll_miles"])
plt.title("Distance vs % Hispanic Population")
plt.xlabel("% Hispanic Population")
plt.ylabel("Distance (miles)")
plt.savefig("race_vs_distance_hisp.png")
plt.show()

# Colored by Race
plt.figure(figsize=(12, 10))

tracts_plot = tracts.merge(
    final_df,
    on="GEOID",
    how="left"
)

print("tracts_plot.columns")
print(tracts_plot.columns)

tracts_plot.plot(
    column="BLACK_x",
    cmap="Blues",
    legend=True
)

plt.title("Black Population by Census Tract")
plt.axis("off")

plt.savefig("black_population_map.png")

plt.show()

race_cols = {
    "BLACK_x": "Black Population",
    "WHITE_x": "White Population",
    "HISP_x": "Hispanic Population",
    "ASIAN_x": "Asian Population"
}

for col, title in race_cols.items():

    plt.figure(figsize=(12,10))

    tracts_plot.plot(
        column=col,
        cmap="Blues",
        legend=True
    )

    plt.title(f"{title} by Census Tract")
    plt.axis("off")

    plt.savefig(
        f"{col}_map.png",
        dpi=300,
        bbox_inches="tight"
    )

    plt.show()

plt.figure()

plt.scatter(
    final_df["nearest_hospital_distance_miles"],
    final_df["nearest_poll_miles"]
)

plt.xlabel("Distance to Hospital")
plt.ylabel("Distance to Polling Location")

plt.title(
    "Polling Access vs Hospital Access"
)

plt.savefig("poll_vs_hospital.png")

plt.show()