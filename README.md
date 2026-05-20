# BB-PAD: Capstone Distance-Polling-Analysis

[ArcGIS Dashboard](https://www.arcgis.com/apps/dashboards/bbbb11d91f6144a2851b4e5a92d7ccad)

## Project Overview

**BB-PAD** is a comprehensive geospatial analysis project that examines polling place accessibility in Montgomery County, Alabama. The project calculates walking distances from population centers to polling locations, integrates demographic vulnerability indicators, analyzes voter turnout patterns, and produces actionable insights for improving electoral access. Multiple routing engines (Euclidean, Manhattan, OSRM network, OSRM pedestrian, Google Routes API) are employed alongside isochrone generation to provide a multi-faceted accessibility assessment.

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [Installation & Setup](#installation--setup)
3. [Data Pipeline Overview](#data-pipeline-overview)
4. [Package Dependencies](#package-dependencies)
5. [Script Documentation](#script-documentation)
   - [R Scripts](#r-scripts)
   - [Python Scripts](#python-scripts)
   - [SQL Scripts](#sql-scripts)
   - [Google Apps Script](#google-apps-script)
6. [Data Inventory](#data-inventory)
   - [Raw Data Sources](#raw-data-sources)
   - [Processed Data Outputs](#processed-data-outputs)
   - [Visualization Outputs](#visualization-outputs)
7. [Cloud Database & Live Dashboard Integration](#cloud-database--live-dashboard-integration)
8. [Deployment Deliverables](#deployment-deliverables)
9. [Additional Analytical Views](#additional-analytical-views)
10. [Key Findings](#key-findings)
11. [Configuration Requirements](#configuration-requirements)

---

## Project Structure

```
BB-PAD/
├── data/
│   ├── census/
│   │   ├── raw/                    # Raw Census Bureau downloads
│   │   └── processed/              # Cleaned demographic CSV and GeoJSON files
│   ├── shapefiles/
│   │   ├── precincts/              # Voting precinct boundaries (2020 and 2024)
│   │   ├── boundaries/             # County and census tract boundaries
│   │   └── infrastructure/         # Road network and paving project data
│   ├── polling/
│   │   ├── raw/                    # Client-provided polling place shapefiles
│   │   └── processed/              # Standardized polling location data
│   ├── elections/
│   │   ├── raw/                    # Raw election result files
│   │   └── processed/              # Cleaned and merged election data
│   └── outputs/                    # Intermediate analytical files
├── scripts/
│   ├── python/                     # Python processing scripts
│   ├── r/                          # R statistical analysis scripts
│   ├── sql/                        # PostgreSQL/PostGIS database scripts
│   └── arcgis/                     # ArcGIS Pro project files
├── outputs/
│   ├── maps/                       # Generated map images
│   ├── figures/                    # Charts and statistical visualizations
│   ├── tables/                     # Summary statistics and regression results
│   └── reports/                    # Final deliverables and documentation
└── README.md
```

---

## Installation & Setup

### Prerequisites

- **R** (≥ 4.0) with the following packages:
  - `tidycensus`, `tidyverse`, `sf`, `tigris`, `broom`
- **Python** (≥ 3.8) with the following packages:
  - `pandas`, `geopandas`, `numpy`, `shapely`, `scipy`, `matplotlib`, `contextily`, `requests`
- **PostgreSQL** (≥ 13) with **PostGIS** extension enabled
- **Docker** (for Valhalla isochrone generation)
- **OSRM** (for network-based distance calculations)

### Census API Key

A U.S. Census Bureau API key is required for `api_acs_data_pull.R`. Obtain one at [https://api.census.gov/data/key_signup.html](https://api.census.gov/data/key_signup.html) and configure using `tidycensus::census_api_key("YOUR_KEY")`.

### Google Routes API Key

Required for `google_walking_distance_calculations.py` and the corresponding fill scripts. Store separately and do not commit to the repository.

---

### OSRM Setup (Network Distance Calculations)

OSRM (Open Source Routing Machine) is a high-performance routing engine used to calculate actual road network distances for both driving and walking routes. Two separate OSRM instances are required: one for driving distances (port 5001) and one for pedestrian walking distances (port 5002).

#### Why Two Instances?

- **Driving profile (port 5001):** Calculates shortest routes using road networks, accounting for one-way streets, turn restrictions, and speed limits. Used to determine how far voters would actually need to drive.
- **Walking profile (port 5002):** Calculates pedestrian routes using sidewalks, footpaths, crosswalks, and pedestrian-accessible pathways. Used to determine realistic walking distances to polling places.

#### Step 1: Download Shared Data

```bash
# Create directories for OSRM data
mkdir -p ~/osrm_data

# Download Alabama OSM extract (approx 150MB)
wget -O ~/osrm_data/alabama-latest.osm.pbf \
  https://download.geofabrik.de/north-america/us/alabama-latest.osm.pbf
```

#### Step 2: Build Driving Profile (Port 5001)

```bash
# Extract road network with car profile
osrm-extract ~/osrm_data/alabama-latest.osm.pbf \
  -p /opt/osrm/profiles/car.lua

# Contract the graph for faster queries (5-10 minutes)
osrm-contract ~/osrm_data/alabama-latest.osrm

# Start driving server in background
osrm-routed ~/osrm_data/alabama-latest.osrm \
  --port 5001 \
  --algorithm=MLD \
  --max-table-size 10000 &
```

#### Step 3: Build Walking Profile (Port 5002)

```bash
# Extract pedestrian network with foot profile
osrm-extract ~/osrm_data/alabama-latest.osm.pbf \
  -p /opt/osrm/profiles/foot.lua

# Contract using Multi-Level Dijkstra for faster performance
osrm-contract ~/osrm_data/alabama-latest.osrm

# Start walking server in background
osrm-routed ~/osrm_data/alabama-latest.osrm \
  --port 5002 \
  --algorithm=MLD \
  --max-table-size 10000 &
```

#### Step 4: Verify Both Instances

```bash
# Test driving route
curl "http://localhost:5001/route/v1/driving/-86.3077,32.3792;-86.2993,32.3669?overview=false"

# Test walking route
curl "http://localhost:5002/route/v1/walking/-86.3077,32.3792;-86.2993,32.3669?overview=false"
```

#### Configuration Flags

| Flag | Purpose |
|------|---------|
| `--port` | Specifies which port the server listens on |
| `--max-table-size` | Maximum number of coordinates in a single request (set to 10000 for batch processing) |
| `--algorithm=MLD` | Uses Multi-Level Dijkstra algorithm (faster for pedestrian routing) |
| `-p` | Specifies the routing profile (car.lua or foot.lua) |

#### Installation

**macOS:**
```bash
brew install osrm-backend
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install osrm-backend
```

**From Source:**
```bash
git clone https://github.com/Project-OSRM/osrm-backend.git
cd osrm-backend
mkdir build && cd build
cmake ..
make -j4
sudo make install
```

#### Troubleshooting

| Issue | Solution |
|-------|----------|
| Port already in use | Kill existing process: `lsof -ti:5001 \| xargs kill` |
| Memory errors during contraction | Use `osrm-customize` instead of `osrm-contract` for limited memory environments |
| Slow query performance | Ensure you ran `osrm-contract` after `osrm-extract` |
| Segmentation fault | Check that OSM file is not corrupted; re-download if needed |

#### Stopping OSRM

```bash
# Find and kill OSRM processes
ps aux | grep osrm-routed
kill -9 [PID]
```

---

### Valhalla Setup (Isochrones)

Valhalla is an open source routing engine used to generate walking isochrones (walkable area polygons) around polling places.

#### Prerequisites

- Docker installed and running
- At least 4GB RAM available for the container
- Alabama OpenStreetMap data extract

#### Step 1: Download OpenStreetMap Data

```bash
# Create a directory for Valhalla data
mkdir -p ~/valhalla_data

# Download Alabama OSM extract (approx 150MB)
wget -O ~/valhalla_data/alabama-latest.osm.pbf \
  https://download.geofabrik.de/north-america/us/alabama-latest.osm.pbf
```

#### Step 2: Build Valhalla Routing Tiles

```bash
# Pull the Valhalla image
docker pull valhalla/valhalla:latest

# Create a temporary container to build tiles
docker run -it --rm \
  -v ~/valhalla_data:/data \
  valhalla/valhalla:latest \
  valhalla_build_config --mjolnir-tile-dir /data/valhalla_tiles --mjolnir-tile-extract /data/valhalla_tiles.tar

# Build the routing tiles (this takes 10-20 minutes)
docker run -it --rm \
  -v ~/valhalla_data:/data \
  valhalla/valhalla:latest \
  valhalla_build_tiles -c /data/valhalla.json /data/alabama-latest.osm.pbf
```

#### Step 3: Start the Valhalla Server

```bash
# Start Valhalla server on port 8002
docker run -d \
  --name valhalla \
  -p 8002:8002 \
  -v ~/valhalla_data:/data \
  valhalla/valhalla:latest \
  valhalla_service /data/valhalla.json 1
```

#### Step 4: Verify Installation

```bash
# Test the server with a simple isochrone request
curl http://localhost:8002/isochrone \
  --data '{"locations":[{"lat":32.3792,"lon":-86.3077}],
           "costing":"pedestrian",
           "contours":[{"time":15,"color":"ff0000"}]}' \
  | python -m json.tool
```

#### Troubleshooting

| Issue | Solution |
|-------|----------|
| Port 8002 already in use | Change `-p 8002:8002` to another port, e.g., `-p 8003:8002` |
| Container exits immediately | Run without `-d` flag to see error logs |
| Out of memory | Increase Docker memory limit in Docker Desktop settings |
| Permission denied on data directory | Run `chmod -R 755 ~/valhalla_data` |
| Slow tile building | Use a machine with SSD storage and at least 8GB RAM |

#### Stopping and Restarting

```bash
# Stop the container
docker stop valhalla

# Restart the container
docker start valhalla

# Remove the container (data persists in ~/valhalla_data)
docker rm valhalla
```

#### Manual Configuration (Optional)

If you need custom routing profiles, create `~/valhalla_data/valhalla.json`:

```json
{
  "mjolnir": {
    "tile_dir": "/data/valhalla_tiles",
    "tile_extract": "/data/valhalla_tiles.tar",
    "timezone": "/data/valhalla_tiles/timezones.sqlite",
    "admin": "/data/valhalla_tiles/admins.sqlite"
  },
  "loki": {
    "actions": ["locate", "route", "height", "isochrone"],
    "logging": {"type": "std_out"},
    "service": {"proxy": "ipc:///tmp/loki"}
  },
  "thor": {
    "logging": {"type": "std_out"},
    "service": {"proxy": "ipc:///tmp/thor"}
  },
  "httpd": {
    "service": {
      "loopback": "ipc:///tmp/valhalla",
      "interrupt": "ipc:///tmp/valhalla"
    }
  },
  "service_limits": {
    "auto": {"max_distance": 5000000},
    "pedestrian": {"max_distance": 250000}
  }
}
```

---

### PostgreSQL Setup

Install PostgreSQL with PostGIS, then create the database and enable spatial extensions all from terminal. PostgreSQL is an open-source relational database that stores all the project's processed data — census demographics, election results, polling locations, distance calculations, and accessibility scores. The PostGIS extension adds support for geographic objects, enabling spatial queries like "which block groups are within a 15-minute walk of this polling place?" directly in SQL.

**macOS:**
```bash
brew install postgresql@15 postgis
brew services start postgresql@15
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install postgresql postgis postgresql-15-postgis-3
sudo systemctl start postgresql
```

**Windows:**
1. Download the installer from [postgresql.org/download/windows](https://www.postgresql.org/download/windows)
2. During installation, check the box for PostGIS when prompted
3. Open **SQL Shell (psql)** from the Start menu to access the terminal

#### Create and Configure the Database

```bash
# Open PostgreSQL terminal
psql -U postgres

# Inside psql, run these commands:
CREATE DATABASE montgomery_voter_access;
\c montgomery_voter_access
CREATE EXTENSION postgis;
```

Verify it worked:
```sql
SELECT PostGIS_Version();
```

If you see a version number, you're done. Exit with `\q`.

#### Connection Details

When scripts ask for a database connection, use:
- **Host:** `localhost`
- **Port:** `5432`
- **Database:** `montgomery_voter_access`
- **User:** `postgres`
- **Password:** whatever you set during installation

---

### Supabase Cloud Database Setup

The project includes a cloud-hosted PostgreSQL database on Supabase for live client access and automated reporting. This migrates the local database to a 24/7 accessible cloud instance.

1. Create a Supabase account at [supabase.com](https://supabase.com)
2. Create a new project (us-west-2 region)
3. Export local database: `pg_dump -U sartorm -d montgomery_voter_access -F c -f montgomery_voter_access.dump`
4. Convert to SQL: `pg_restore -f montgomery_voter_access.sql montgomery_voter_access.dump`
5. Run the SQL file in the Supabase SQL Editor
6. Create all views using `create_views.sql` and the additional analytical views documented below
7. Deploy the Edge Function (`query` function) for secure HTTPS API access to database views

---

## Data Pipeline Overview

The project follows a sequential data processing pipeline:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RAW DATA INGESTION                           │
├─────────────────┬──────────────┬─────────────────┬─────────────────┤
│ Census ACS Data │Election Data │ Polling Places  │ Infrastructure  │
│  (tidycensus)   │ (Shapefiles) │   (Shapefile)   │ (OSM + Paving)  │
└────────┬────────┴──────┬───────┴────────┬────────┴────────┬────────┘
         │               │                │                 │
         ▼               ▼                ▼                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       DATA PROCESSING                               │
├─────────────────┬──────────────┬─────────────────┬─────────────────┤
│ Vulnerability   │ Precinct     │ Coordinate      │ Road Network    │
│ Index (R)       │ Merging (Py) │ Extraction (Py) │ Tagging (Py)    │
└────────┬────────┴──────┬───────┴────────┬────────┴────────┬────────┘
         │               │                │                 │
         ▼               ▼                ▼                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DISTANCE CALCULATIONS                            │
├──────────┬──────────┬──────────┬──────────┬──────────┬─────────────┤
│Euclidean │Manhattan │  OSRM    │  OSRM    │  Google  │  Valhalla   │
│ Straight │ Grid     │ Network  │ Walking  │ Walking  │ Isochrones  │
│  Line    │ Distance │ Driving  │ Distance │ Distance │  (Polygons) │
└────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┴──────┬──────┘
     │          │          │          │          │            │
     ▼          ▼          ▼          ▼          ▼            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     DATA INTEGRATION                                │
├─────────────────┬──────────────────┬───────────────────────────────┤
│ Distance Merge  │ Walkability      │ PostgreSQL Import              │
│ (Complete CSV)  │ Enhancement (Py) │ (Schema + Views)              │
└────────┬────────┴────────┬─────────┴───────────────┬───────────────┘
         │                 │                         │
         ▼                 ▼                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                ANALYSIS & VISUALIZATION                             │
├─────────────────┬──────────────────┬───────────────────────────────┤
│ Turnout         │ Correlation      │ Maps, Choropleths,             │
│ Regression (R)  │ Analysis (R)     │ Isochrone Visuals (Py/R)       │
└─────────────────┴──────────────────┴───────────────────────────────┘
```

---

## Package Dependencies

### R Packages

| Package | Version | Purpose |
|---------|---------|---------|
| `tidycensus` | ≥ 1.2 | Census ACS data retrieval via API |
| `tidyverse` | ≥ 1.3 | Data manipulation and visualization |
| `sf` | ≥ 1.0 | Spatial data handling |
| `tigris` | ≥ 1.6 | Census geographic boundary data |
| `broom` | ≥ 0.7 | Tidy model output formatting |
| `ggplot2` | ≥ 3.4 | Static visualization and choropleth maps |
| `ggspatial` | ≥ 1.1 | Basemap tiles for maps |
| `patchwork` | ≥ 1.1 | Combining multiple ggplot figures |
| `pheatmap` | ≥ 1.0 | Correlation heatmap generation |
| `rosm` | ≥ 0.2 | OpenStreetMap tile downloading |

### Python Packages

| Package | Version | Purpose |
|---------|---------|---------|
| `pandas` | ≥ 1.3 | Tabular data manipulation |
| `geopandas` | ≥ 0.10 | Spatial data operations |
| `numpy` | ≥ 1.21 | Numerical computation |
| `shapely` | ≥ 1.8 | Geometric operations (Point, LineString) |
| `scipy` | ≥ 1.7 | Distance matrix computation (cdist) |
| `requests` | ≥ 2.26 | HTTP API calls (OSRM, Google, Valhalla) |
| `matplotlib` | ≥ 3.4 | Static visualization |
| `contextily` | ≥ 1.2 | Basemap tiles for maps |
| `pathlib` | stdlib | Cross-platform file path handling |
| `json` | stdlib | JSON serialization/deserialization |
| `time` | stdlib | Rate limiting delays |
| `warnings` | stdlib | Warning suppression |

---

## Script Documentation

### R Scripts

#### `api_acs_data_pull.R`

**Purpose:** Retrieves American Community Survey (ACS) demographic data from the U.S. Census Bureau for Montgomery County, Alabama, at both tract and block group geographic levels.

**Key Functions:**

- `get_montgomery_tract_data()` — Queries the Census API for tract-level data (71 tracts) with spatial geometries, calculating derived percentages for race, poverty, vehicle access, and educational attainment.
- `get_montgomery_bg_data()` — Retrieves block group-level data (203 block groups) for finer spatial resolution analysis.
- `calculate_vulnerability_index()` — Creates a composite vulnerability score using z-score normalization of three indicators: percent Black population, percent below poverty, and percent households without vehicle access. Communities are categorized as "High," "Moderate," "Low," or "Very Low" vulnerability based on their composite score.

**Outputs:**

| File | Description |
|------|-------------|
| `data/census/processed/montgomery_demographics_tract.csv` | Non-spatial tract-level demographics |
| `data/census/processed/montgomery_demographics_bg.csv` | Non-spatial block group-level demographics |
| `data/census/processed/montgomery_demographics_tract.geojson` | Spatial tract-level data for GIS integration |
| `data/census/processed/montgomery_demographics_bg.geojson` | Spatial block group-level data for GIS integration |

**Dependencies:** `tidycensus`, `tidyverse`, `sf`, `tigris`

**Note:** A Census API key must be configured. Block group poverty estimates are suppressed by the Census Bureau and return `NA` values; tract-level data should be used for poverty analysis.

---

#### `turnout_modeling.R`

**Purpose:** Performs statistical analysis of voter turnout and polling place accessibility in Montgomery County, Alabama, using tract-level demographic data with complete poverty metrics. Generates descriptive statistics, regression models, correlation analysis, and client-ready summary outputs.

**Key Functions:**

- `load_analysis_data()` — Loads all prepared datasets from previous processing steps, including 2024 and 2020 precinct election results, tract-level demographics (71 tracts with complete poverty data), enhanced accessibility scores (203 records), and isochrone summary statistics.
- `generate_descriptive_stats()` — Calculates county-level summary statistics including total presidential votes, Democratic and Republican vote shares, turnout change between 2020 and 2024, walking distance metrics, walkability category distributions, and 15-minute walkable area coverage.
- `merge_accessibility_tract_demographics()` — Joins accessibility scores with tract-level demographic data by constructing proper 11-digit tract GEOIDs from the TRACTCE field (zero-padded to 6 digits) and merging with the tract demographics table. Reports merge success rate and NA counts for poverty data.
- `run_turnout_regression()` — Executes three linear regression models:
  - **Model 1:** Walkability Score ~ % Black + % Poverty
  - **Model 2:** Walking Distance ~ % Black + % Poverty + % No Vehicle
  - **Model 3:** Walking Distance ~ Vulnerability Index
  - Also performs group comparisons by vulnerability category and conducts t-tests between high (>50%) and low (<50%) percent Black areas.
- `run_correlation_analysis()` — Calculates Pearson correlation coefficients between walking distance and all other numeric variables (walkability score, Euclidean distance, driving distance, demographic percentages, and vulnerability index), with p-values and strength classifications (strong/moderate/weak).
- `generate_client_summary()` — Produces a formatted executive summary of key findings, including voting accessibility metrics, turnout patterns, demographic disparities, vulnerability index findings, and actionable recommendations.
- `save_outputs()` — Exports all results to the `outputs/tables/` directory.

**Outputs:**

| File | Description |
|------|-------------|
| `outputs/tables/turnout_change_2020_2024.csv` | Precinct-level turnout comparison between 2020 and 2024 |
| `outputs/tables/walkability_summary.csv` | Count and percentage of areas by walkability category |
| `outputs/tables/merged_analysis_tract_level.csv` | Combined accessibility and demographic dataset (201 rows) |
| `outputs/tables/correlation_data_tract.csv` | Correlation matrix data for distance and demographic variables |
| `outputs/tables/regression_results_tract_level.txt` | Full regression model outputs with coefficients and R-squared values |

**Key Findings:**

- High vulnerability areas (greater % Black, higher poverty) have shorter walking distances to polling places (1.22 miles vs. 2.52 miles for low % Black areas)
- Vulnerability index is negatively correlated with walking distance (r = -0.308, p < 0.001)
- 28% of areas have "Poor" or "Very Poor" walkability despite equitable distribution

**Dependencies:** `tidyverse`, `broom`

**Note:** Tract-level demographics are used because poverty data at the block group level is suppressed by the Census Bureau (all `NA` values). The merge process uses tract GEOIDs constructed from the accessibility file's TRACTCE field.

---

#### `choropleth_map.R, correlation_heatmap.R, isochrone_final.R, vulnerability_bar_chart.R`

**Purpose:** These small-scale R scripts create publication-quality static visualizations in R using ggplot2, including correlation heatmaps, choropleth maps, vulnerability bar charts, and faceted isochrone maps. These complement the early Python visualizations with more polished formatting suitable for reports and presentations.

**Key Visualizations:**

- **Correlation heatmap (pheatmap):** Clustered heatmap showing correlations between walking distance, walkability score, and demographic variables with annotated correlation coefficients and significance stars.
- **Choropleth maps (ggplot2 + sf):** Tract-level maps colored by walking distance, walkability score, % Black, % poverty, and vulnerability score using viridis color scales for accessibility interpretation.
- **Vulnerability bar chart:** Walking distance by vulnerability category with standard deviation error bars, colored by category (Very Low/Low/Moderate/High).
- **Faceted isochrone map:** Five-panel faceted figure showing 5, 10, 15, 20, and 30-minute walking isochrones with polling places on an OpenStreetMap basemap, using smaller point markers and darker isochrone borders for improved visibility.

**Dependencies:** `ggplot2`, `sf`, `ggspatial`, `patchwork`, `pheatmap`, `tidyverse`, `rosm`

**Note:** The faceted isochrone map uses `annotation_map_tile(type = "osm")` for basemap rendering and transforms all layers to EPSG:3857 for compatibility. Polling place markers are sized at 1.2 with red-orange fill for contrast against the basemap and isochrone polygons.

---

### Python Scripts

#### `distance_calculations.py`

**Purpose:** Calculates baseline distance metrics from each population center to polling places and civic infrastructure reference points, producing a composite accessibility score for comparative analysis.

**Key Functions:**

- `load_population_centers()` — Reads the Census 2020 population-weighted centroids file, constructs 12-digit GEOIDs from component parts, and filters to Montgomery County block groups (203 centers). Returns a GeoDataFrame with point geometries.
- `load_polling_places()` — Loads the processed Montgomery County polling places GeoJSON file (49 locations).
- `calculate_euclidean_distances()` — Computes straight-line ("as the crow flies") distances from each population center to all polling places using `scipy.spatial.distance.cdist`. Returns the minimum distance and index of the nearest polling place for each center. Distances are converted from degrees to miles using the approximation 1° ≈ 69 miles.
- `calculate_manhattan_distances()` — Computes grid-based (taxicab) distances using the cityblock metric, more appropriate for urban areas with rectilinear street networks.
- `calculate_distances_to_reference_points()` — Measures proximity to six civic infrastructure locations (City Hall and five community centers) as a proxy for neighborhood accessibility.
- `calculate_accessibility_score()` — Creates a composite 0-1 score by normalizing and weighting the three distance components:
  - Euclidean distance to polling place (40%)
  - Manhattan distance to polling place (30%)
  - Distance to civic center (30%)
  - Categories: Excellent (0-0.25), Good (0.25-0.50), Fair (0.50-0.75), Poor (0.75-1.0).
- `create_distance_matrix()` — Generates and saves a full pairwise distance matrix (203 centers × 49 polling places) for detailed spatial analysis.

**Outputs:**

| File | Description |
|------|-------------|
| `data/outputs/accessibility_scores_by_tract.csv` | Population centers with all distance metrics and accessibility categories |
| `data/outputs/distance_matrix_montgomery.csv` | Full pairwise distance matrix (centers × polling places) |

**Dependencies:** `pandas`, `geopandas`, `numpy`, `shapely`, `scipy`

**Note:** Distance calculations use degree-to-mile conversion (1° ≈ 69 miles) which is appropriate for small geographic areas but introduces minor distortion. For production use, projecting to a state plane coordinate system is recommended.

---

#### `election_data_processing.py`

**Purpose:** Processes and merges 2020 and 2024 precinct-level election results for Montgomery County, Alabama, enabling comparative turnout analysis across election cycles despite precinct boundary and naming changes due to redistricting.

**Key Functions:**

- `load_2024_election_data()` — Reads the 2024 precinct shapefile from the Redistricting Data Hub, filters to Montgomery County (51 precincts), standardizes vote column names, and calculates total presidential votes and Democratic vote share.
- `load_2020_election_data()` — Reads the 2020 precinct shapefile from the UFL Election Lab, filters to Montgomery County (49 precincts), and calculates equivalent metrics for the 2020 general election.
- `load_county_registration_data()` — Extracts county-level registered voter counts from the Alabama Secretary of State ballot report, providing the denominator for accurate turnout rate calculations.
- `merge_election_years()` — Performs a manual name-based merge of 2020 and 2024 precincts using a curated mapping dictionary (41 matched pairs) that accounts for precinct renaming, consolidation, and new precinct creation between election cycles. Calculates absolute and percentage turnout change for each matched precinct.

**Outputs:**

| File | Description |
|------|-------------|
| `data/elections/processed/montgomery_precinct_results_2024.csv` | Cleaned 2024 election results (non-spatial) |
| `data/elections/processed/montgomery_precincts_2024.geojson` | 2024 precinct boundaries with results (spatial) |
| `data/elections/processed/montgomery_precinct_results_2020.csv` | Cleaned 2020 election results (non-spatial) |
| `data/elections/processed/montgomery_precincts_2020.geojson` | 2020 precinct boundaries with results (spatial) |
| `data/elections/processed/election_data_combined_2020_2024.csv` | Merged dataset with turnout change metrics |
| `data/elections/processed/montgomery_precincts_combined_2020_2024.geojson` | Merged spatial dataset |

**Dependencies:** `pandas`, `geopandas`, `numpy`, `pathlib`

**Note:** The precinct mapping dictionary contains 41 matched pairs; approximately 10 precincts from 2024 have no direct 2020 equivalent due to new construction or precinct consolidation. These are documented in the script output for transparency.

---

#### `fill_missing_google.py`

**Purpose:** Fills missing Google walking distance values for population centers that failed during the initial batch processing run (centers 157-162). Uses the Google Routes API to compute pedestrian distances and updates the existing accessibility scores file.

**Key Functions:**

- `load_population_centers()` — Reads the Census 2020 population-weighted centroids file, constructs 12-digit GEOIDs from component parts, and filters to Montgomery County block groups. Returns a GeoDataFrame with point geometries for coordinate extraction.
- `load_polling_places()` — Loads the processed Montgomery County polling places GeoJSON file (49 locations) for destination coordinates.
- `compute_route_matrix()` — Sends batch requests to the Google Routes API for walking distances between origin and destination points. Implements exponential backoff (3s, 6s, 12s, 24s, 48s) for rate limiting and retries on failure. Distances are returned in miles (converted from meters).
- `main()` — Identifies centers with missing Google walking distances from the existing CSV file, converts short-format GEOIDs (e.g., `11010026002`) to full 12-digit format (e.g., `011010026002`) for coordinate lookup, fetches distances in batches of 3 origins to respect API rate limits, and updates the CSV with new values.

**Inputs:**

| File | Description |
|------|-------------|
| `data/outputs/accessibility_scores_google_walking.csv` | Existing accessibility scores with some missing Google walking distances |
| `data/census/raw/CenPop2020_Mean_BG01.txt` | Census population centers for coordinate lookup |
| `data/polling/processed/polling_places_montgomery_2020.geojson` | Polling place locations |

**Outputs:**

| File | Description |
|------|-------------|
| `data/outputs/accessibility_scores_google_walking.csv` | Updated file with previously missing Google walking distances filled |

**Configuration:**

| Parameter | Value |
|-----------|-------|
| `API_KEY` | Google Routes API key (stored separately, not committed to repository) |
| `BATCH_SIZE` | 3 origins per request |
| `ROUTES_URL` | Google Routes API endpoint for distance matrix computation |

**Dependencies:** `pandas`, `geopandas`, `numpy`, `requests`, `shapely`

**Note:** The GEOID format conversion is required because the accessibility scores CSV uses short-format GEOIDs missing the leading zero (e.g., `11010026002` instead of `011010026002`). When successful, all 203 centers will have complete Google walking distance data.

---

#### `fill_missing_matrix_google.py`

**Purpose:** Fills missing values in the full Google walking distance matrix for rows that failed during the initial batch processing run. Unlike the summary file filler, this script updates the complete pairwise distance matrix (203 centers × 49 polling places).

**Key Functions:**

- `load_population_centers()` — Reads the Census 2020 population-weighted centroids file, constructs 12-digit GEOIDs, and filters to Montgomery County block groups. Returns a GeoDataFrame with point geometries for coordinate extraction.
- `load_polling_places()` — Loads the processed Montgomery County polling places GeoJSON file (49 locations) for destination coordinates.
- `compute_route_matrix()` — Sends batch requests to the Google Routes API for walking distances between origin and destination points. Implements exponential backoff (3s, 6s, 12s, 24s, 48s) for rate limiting and retries on failure. Distances are returned in miles (converted from meters).
- `main()` — Loads the existing distance matrix CSV, identifies rows containing NaN values, maps short-format GEOID indices (e.g., `11010026002`) to full 12-digit format (e.g., `011010026002`) for coordinate lookup, fetches complete distance rows in batches of 3 origins, and updates the matrix with new values.

**Inputs:**

| File | Description |
|------|-------------|
| `data/outputs/distance_matrix_google_walking.csv` | Full pairwise distance matrix (203 rows × 49 columns) with some missing rows |
| `data/census/raw/CenPop2020_Mean_BG01.txt` | Census population centers for coordinate lookup |
| `data/polling/processed/polling_places_montgomery_2020.geojson` | Polling place locations |

**Outputs:**

| File | Description |
|------|-------------|
| `data/outputs/distance_matrix_google_walking.csv` | Updated matrix with previously missing rows filled |

**Configuration:**

| Parameter | Value |
|-----------|-------|
| `API_KEY` | Google Routes API key (stored separately) |
| `BATCH_SIZE` | 3 origins per request |
| `ROUTES_URL` | Google Routes API endpoint for distance matrix computation |

**Dependencies:** `pandas`, `geopandas`, `numpy`, `requests`, `shapely`

**Note:** This script differs from `fill_missing_google.py` in that it operates on the full distance matrix (all pairwise distances) rather than just the summary file (minimum distances only). When successful, all 203 rows will have complete distance data for all 49 polling places (9,947 total distance values).

---

#### `generate_polling_isochrones.py`

**Purpose:** Generates walking isochrones (walkable area polygons) for all polling places in Montgomery County using the Valhalla routing engine. Creates polygons for 5, 10, 15, 20, and 30-minute walking times and calculates the area and population served by each isochrone.

**Key Functions:**

- `load_polling_places()` — Loads polling place locations from GeoJSON file. Attempts to load the 2020 version first, falling back to the generic Montgomery polling places file if not found.
- `load_population_centers()` — Reads the Census 2020 population-weighted centroids file and filters to Montgomery County.
- `get_isochrone()` — Sends requests to the local Valhalla instance for pedestrian isochrones around specified coordinates. Implements retry logic for transient failures and returns a GeoDataFrame with the isochrone polygon.
- `calculate_population_served()` — Performs spatial join between an isochrone polygon and population centers to calculate total population within the walkable area. Sums the POPULATION column for all enclosed points.
- `main()` — Verifies Valhalla connection, generates isochrones for all 49 polling places across 5 time intervals (245 total isochrones), calculates area in square miles (projected to UTM Zone 16N for accuracy), computes population served, and exports results.

**Configuration:**

| Parameter | Value |
|-----------|-------|
| `VALHALLA_URL` | Local Valhalla instance running on port 8002 |
| Time intervals | 5, 10, 15, 20, and 30 minutes |
| Travel mode | pedestrian (walking) |

**Outputs:**

| File | Description |
|------|-------------|
| `data/outputs/polling_isochrones_all.geojson` | Combined GeoJSON with all 245 isochrone polygons |
| `data/outputs/polling_isochrone_summary.csv` | Summary table with area and population served for each isochrone |

**Coverage Statistics (15-minute walk):**

| Metric | Value |
|--------|-------|
| Average walkable area | 0.74 sq miles |
| Total walkable area (all polling places) | 36.16 sq miles |
| Average population within 15-min walk | 1,408 people |

**Dependencies:** `pandas`, `geopandas`, `requests`, `shapely`

**Note:** Requires Valhalla routing engine running locally with Alabama OpenStreetMap data. The denoise parameter (0.11) smooths jagged edges from network analysis for cleaner polygon output. Area calculations use UTM Zone 16N projection (EPSG:32616) for accurate square mileage measurements.

---

#### `google_walking_distance_calculations.py`

**Purpose:** Primary batch processing script for calculating Google walking distances from all population centers to all polling places using the Google Routes API. Computes pedestrian distances for 203 population centers × 49 polling places (9,947 total routes) and produces both summary minimum distances and a full pairwise distance matrix.

**Key Functions:**

- `load_population_centers()` — Reads the Census 2020 population-weighted centroids file, constructs 12-digit GEOIDs from component parts, and filters to Montgomery County block groups (203 centers). Returns a GeoDataFrame with point geometries.
- `load_polling_places()` — Loads the processed Montgomery County polling places GeoJSON file (49 locations) for destination coordinates.
- `compute_route_matrix()` — Sends batch requests to the Google Routes API for walking distances between origin and destination points. Implements exponential backoff (2s, 4s, 8s, 16s, 32s, 64s, 128s, 256s, 512s) for rate limiting with up to 9 retry attempts. Distances are returned in miles (converted from meters).
- `calculate_google_walking_distances()` — Orchestrates the full distance calculation by processing origins in batches of 6 (294 elements per request, safely under the 625 element API limit). Calculates minimum distance to nearest polling place for each center and generates a full distance matrix. Includes a `sample_size` parameter for testing with a subset of centers.

**Configuration:**

| Parameter | Value |
|-----------|-------|
| `API_KEY` | Google Routes API key (stored separately) |
| `MAX_ORIGINS_PER_BATCH` | 6 origins per request (6 × 49 = 294 elements) |
| `ROUTES_URL` | Google Routes API endpoint for distance matrix computation |
| `travelMode` | WALK (pedestrian routing) |

**Outputs:**

| File | Description |
|------|-------------|
| `data/outputs/accessibility_scores_google_walking.csv` | Minimum walking distance to nearest polling place for each of the 203 centers |
| `data/outputs/distance_matrix_google_walking.csv` | Full pairwise distance matrix (203 rows × 49 columns) |

**Performance:**

| Metric | Value |
|--------|-------|
| Total routes calculated | 9,947 |
| Batch size | 6 origins × 49 destinations |
| Number of batches | 34 |
| Approximate runtime | 5-10 minutes |
| Rate limit delay | 2.5 seconds between batches |

**Dependencies:** `pandas`, `geopandas`, `numpy`, `requests`, `shapely`

**Note:** This script uses the Google Routes API Compute Route Matrix endpoint which has a limit of 625 elements per request. Processing is intentionally throttled with 2.5 second delays between batches to stay within free tier rate limits. Failed batches can be retried using `fill_missing_google.py` for summary data or `fill_missing_matrix_google.py` for matrix data.

---

#### `merge_distance_calculations.py`

**Purpose:** Combines accessibility scores from all distance calculation methods into a single comprehensive dataset. Merges Euclidean, Manhattan, OSRM driving, OSRM walking, and Google walking results into one master file with cross-comparison metrics between routing methods.

**Key Functions:**

- `merge_distance_results()` — Loads the Euclidean distance results as the base dataset, then sequentially merges OSRM driving, OSRM walking, and Google walking results on the GEOID field using left joins. Creates cross-comparison ratio metrics between different routing methods and saves the combined dataset.

**Input Files:**

| File | Description |
|------|-------------|
| `data/outputs/accessibility_scores_by_tract.csv` | Base Euclidean and Manhattan distance results |
| `data/outputs/accessibility_scores_network.csv` | OSRM driving distance results |
| `data/outputs/accessibility_scores_walking.csv` | OSRM walking distance results |
| `data/outputs/accessibility_scores_google_walking.csv` | Google walking distance results |

**Output File:**

| File | Description |
|------|-------------|
| `data/outputs/accessibility_scores_complete.csv` | Combined dataset with all distance metrics (203 rows × 38 columns) |

**Cross-Comparison Metrics:**

| Metric | Formula | Purpose |
|--------|---------|---------|
| `driving_to_euclidean_ratio` | network ÷ straight-line | Compares actual road distance to direct distance |
| `driving_euclidean_diff_miles` | network − straight-line | Absolute additional distance from road network |
| `osrm_walking_to_euclidean_ratio` | walking ÷ straight-line | Pedestrian network efficiency |
| `google_walking_to_euclidean_ratio` | Google walking ÷ straight-line | Google pedestrian routing efficiency |
| `osrm_walking_to_driving_ratio` | walking ÷ driving | Walkability proxy (closer to 1.0 = more direct walking routes) |
| `google_to_osrm_walking_ratio` | Google walking ÷ OSRM walking | Comparison between routing engines |
| `google_walking_to_driving_ratio` | Google walking ÷ driving | Pedestrian vs vehicle routing efficiency |

**Summary Statistics:**

| Metric | Values |
|--------|---------------|
| Euclidean distance | 1.02 miles (average) |
| Manhattan distance | 1.27 miles (average) |
| OSRM driving | 1.44 miles (average) |
| OSRM walking | 1.40 miles (average) |
| Google walking | 1.58 miles (average) |

**Dependencies:** `pandas`, `pathlib`

**Note:** This script is typically run after all individual distance calculation scripts have completed. The merged output file serves as the primary input for statistical analysis and visualization. Cross-comparison ratios provide insight into routing efficiency and can identify areas where pedestrian access is circuitous compared to driving routes.

---

#### `network_distance_calculations.py`

**Purpose:** Calculates actual road network driving distances from all population centers to all polling places using the OSRM (Open Source Routing Machine) routing engine. Computes driving distances for 203 population centers × 49 polling places (9,947 total routes) and produces both summary minimum distances and a full pairwise distance matrix.

**Key Functions:**

- `load_population_centers()` — Reads the Census 2020 population-weighted centroids file, constructs 12-digit GEOIDs, and filters to Montgomery County block groups (203 centers). Returns a GeoDataFrame with point geometries.
- `load_polling_places()` — Loads the processed Montgomery County polling places GeoJSON file (49 locations) for destination coordinates.
- `get_osrm_distance()` — Sends individual routing requests to the local OSRM server for the shortest driving route between origin and destination coordinates. Returns distance in miles (converted from meters) or `None` if routing fails.
- `calculate_network_distances()` — Orchestrates the full distance calculation by iterating through all origin-destination pairs with a 50ms delay between requests to avoid overwhelming the server. Tracks progress every 100 routes and includes a `sample_size` parameter for testing.

**Configuration:**

| Parameter | Value |
|-----------|-------|
| `OSRM_URL` | Local OSRM instance running on port 5001 with driving profile |
| Request delay | 0.05 seconds between individual routes |
| Sample size | Can be set to a small number (e.g., 10) for testing |

**Outputs:**

| File | Description |
|------|-------------|
| `data/outputs/accessibility_scores_network.csv` | Minimum driving distance to nearest polling place for each of the 203 centers |
| `data/outputs/distance_matrix_network.csv` | Full pairwise driving distance matrix (203 rows × 49 columns) |

**Performance:**

| Metric | Value |
|--------|-------|
| Total routes calculated | 9,947 |
| Approximate runtime | 10-20 minutes |
| Request rate | ~20 requests per second |
| Network/Euclidean ratio | ~0.86x (driving routes are typically shorter than straight-line) |

**Dependencies:** `pandas`, `geopandas`, `numpy`, `requests`, `shapely`

**Note:** OSRM must be running locally with the Alabama OpenStreetMap extract before executing this script. The driving profile uses actual road networks and accounts for one-way streets, turn restrictions, and speed limits.

---

#### `network_walking_distance_calculations.py`

**Purpose:** Calculates actual pedestrian network walking distances from all population centers to all polling places using the OSRM routing engine with foot profile. Computes walking distances for 203 population centers × 49 polling places (9,947 total routes) and produces both summary minimum distances and a full pairwise distance matrix.

**Key Functions:**

- `load_population_centers()` — Reads the Census 2020 population-weighted centroids file, constructs 12-digit GEOIDs, and filters to Montgomery County block groups (203 centers). Returns a GeoDataFrame with point geometries.
- `load_polling_places()` — Loads the processed Montgomery County polling places GeoJSON file (49 locations) for destination coordinates.
- `get_osrm_walking_distance()` — Sends individual routing requests to the local OSRM server using the foot profile for pedestrian pathways. Returns distance in miles (converted from meters) or `None` if routing fails.
- `calculate_walking_distances()` — Orchestrates the full distance calculation by iterating through all origin-destination pairs with a 50ms delay between requests. Tracks progress every 100 routes and includes a `sample_size` parameter for testing.

**Configuration:**

| Parameter | Value |
|-----------|-------|
| `OSRM_URL` | Local OSRM instance running on port 5002 with foot profile |
| Request delay | 0.05 seconds between individual routes |
| Sample size | Can be set to a small number (e.g., 10) for testing |

**Outputs:**

| File | Description |
|------|-------------|
| `data/outputs/accessibility_scores_walking.csv` | Minimum walking distance to nearest polling place for each of the 203 centers |
| `data/outputs/distance_matrix_walking.csv` | Full pairwise walking distance matrix (203 rows × 49 columns) |

**Performance:**

| Metric | Value |
|--------|-------|
| Total routes calculated | 9,947 |
| Approximate runtime | 5-10 minutes |
| Request rate | ~20 requests per second |
| Walking/Euclidean ratio | ~1.21x (pedestrian routes typically longer than straight-line) |

**Dependencies:** `pandas`, `geopandas`, `numpy`, `requests`, `shapely`

**Note:** OSRM must be running locally with the Alabama OpenStreetMap extract before executing this script. The foot profile uses pedestrian-accessible pathways including sidewalks, footpaths, and pedestrian crossings. The `--algorithm=MLD` flag enables Multi-Level Dijkstra for faster routing performance.

---

#### `polling_place_processing.py`

**Purpose:** Processes and validates the client-provided statewide Alabama polling places shapefile, filtering to Montgomery County only and exporting standardized data in multiple formats for downstream analysis and visualization.

**Key Functions:**

- `load_client_polling_places()` — Reads the statewide Alabama polling places shapefile containing point geometries and attribute data for all voting locations across the state. Displays the coordinate reference system and available columns for verification.
- `filter_to_montgomery()` — Searches for the county column using common naming conventions (`COUNTY`, `County`, `COUNTY_NAME`, etc.) and filters records where the county name contains "MONTGOMERY" (case-insensitive). Reports the number of polling places before and after filtering.
- `standardize_polling_place_fields()` — Adds standardized fields including a zero-padded unique identifier (`polling_place_id`) and extracted longitude/latitude coordinates from point geometries while preserving all original attribute data.
- `create_polling_place_database()` — Exports the processed data to both CSV (non-spatial, geometry dropped) and GeoJSON (spatial, web-friendly) formats for use in analysis and visualization.
- `export_to_shapefile()` — Exports the filtered Montgomery County data to shapefile format for compatibility with ArcGIS and traditional GIS software.

**Input:**

| File | Description |
|------|-------------|
| `data/polling/raw/Polling-Places-Alabama/Al_Polls_Flood_SLED.shp` | Statewide Alabama polling places shapefile |

**Outputs:**

| File | Description |
|------|-------------|
| `data/polling/processed/polling_places_montgomery_clean_2020.csv` | Non-spatial CSV with standardized fields |
| `data/polling/processed/polling_places_montgomery_2020.geojson` | Spatial GeoJSON for web mapping and analysis |
| `data/shapefiles/precincts/montgomery_polling_places_2020.shp` | Shapefile for ArcGIS compatibility |

**Summary Statistics:**

| Metric | Value |
|--------|-------|
| Total Alabama polling places | ~2,800 |
| Montgomery County polling places | 49 |
| Coordinate reference system | EPSG:4326 (WGS84) |

**Dependencies:** `geopandas`, `pandas`, `pathlib`

**Note:** This script is typically the first step in the data processing pipeline. The county column detection is robust to multiple naming conventions, but if no county column is found, the script will display available columns and return unfiltered data as a fallback. The output GeoJSON serves as the primary input for all subsequent distance calculation scripts.

---

#### `poor_polling_place_access_bg.py`

**Purpose:** Provides a quick diagnostic view of block groups categorized as having "Poor" polling place accessibility based on the composite accessibility score. Useful for rapidly identifying priority areas for intervention without running the full statistical analysis pipeline.

**Functionality:**

- Loads the accessibility scores dataset generated by `distance_calculations.py`
- Filters the data to only block groups where `accessibility_category` equals "Poor"
- Displays the GEOID, distance to nearest polling place (miles), and population for each poor-access area
- Reports summary statistics including total block groups analyzed and percentage with poor access

**Input:**

| File | Description |
|------|-------------|
| `data/outputs/accessibility_scores_by_tract.csv` | Accessibility scores with composite categories for each block group |

**Accessibility Categories:**

| Category | Score Range | Interpretation |
|----------|-------------|-----------------|
| Excellent | 0.00 - 0.25 | Shortest distances, best access |
| Good | 0.25 - 0.50 | Above average access |
| Fair | 0.50 - 0.75 | Moderate access |
| Poor | 0.75 - 1.00 | Longest distances, worst access |

**Dependencies:** `pandas`, `pathlib`

**Note:** This is a lightweight utility script for rapid assessment. The composite accessibility score is calculated from three weighted components: Euclidean distance to polling place (40%), Manhattan distance to polling place (30%), and distance to civic infrastructure (30%). For comprehensive demographic analysis, use the R statistical scripts in `scripts/r/`.

---

#### `pop_centers_conversion.py`

**Purpose:** Converts the Census 2020 population-weighted centroids dataset from text format to a spatial GeoJSON file for mapping and visualization. Filters to Montgomery County block groups and creates point geometries for each population center.

**Functionality:**

- Reads the Census Bureau's population centers text file (comma-delimited with UTF-8 BOM encoding)
- Constructs 12-digit GEOIDs from component state, county, tract, and block group identifiers
- Filters to Montgomery County only using the FIPS code prefix `01101` (state 01 + county 101)
- Creates point geometries from longitude and latitude coordinates
- Exports as GeoJSON for web mapping and spatial analysis

**Input:**

| File | Description |
|------|-------------|
| `data/census/raw/CenPop2020_Mean_BG01.txt` | Census 2020 population-weighted centroids for all block groups |

**Output:**

| File | Description |
|------|-------------|
| `data/outputs/population_centers_montgomery.geojson` | Spatial GeoJSON with point geometries for 203 Montgomery County block groups |

**Output Statistics:**

| Metric | Value |
|--------|-------|
| Population centers | 203 block groups |
| Total population | 226,718 |
| Coordinate reference system | EPSG:4326 (WGS84) |

**GEOID Construction:**

| Component | Length | Example | Description |
|-----------|--------|---------|-------------|
| STATEFP | 2 digits | 01 | State FIPS code (Alabama) |
| COUNTYFP | 3 digits | 101 | County FIPS code (Montgomery) |
| TRACTCE | 6 digits | 002600 | Census tract number |
| BLKGRPCE | 1 digit | 2 | Block group number |
| Full GEOID | 12 digits | 011010026002 | Unique block group identifier |

**Dependencies:** `pandas`, `geopandas`, `shapely`, `pathlib`

**Note:** Population-weighted centroids are scientifically superior to geometric centroids because they account for where people actually live within each block group, producing more realistic accessibility estimates.

---

#### `visual_preview.py`

**Purpose:** Creates a publication-quality visualization of 15-minute walking isochrones overlaid with population centers and polling places on an OpenStreetMap basemap. This map serves as a key deliverable for communicating walkable access to polling locations across Montgomery County.

**Functionality:**

- Loads three spatial datasets: Valhalla walking isochrones, population-weighted centroids, and polling place locations
- Projects all layers to Web Mercator (EPSG:3857) for compatibility with the `contextily` basemap
- Filters isochrones to 15-minute walking distance for standardized comparison
- Plots isochrones as semi-transparent blue polygons
- Adds OpenStreetMap basemap for geographic context (roads, landmarks, neighborhoods)
- Plots population centers as red circles sized proportionally to population (log scale)
- Plots polling places as prominent navy star markers
- Labels the top 5 polling places with largest walkable coverage area
- Creates custom legend explaining all map elements
- Exports as high-resolution PNG (300 DPI) for reports and presentations

**Inputs:**

| File | Description |
|------|-------------|
| `data/outputs/polling_isochrones_all.geojson` | Combined isochrones for all time intervals |
| `data/outputs/population_centers_montgomery.geojson` | Population-weighted centroids |
| `data/polling/processed/polling_places_montgomery_2020.geojson` | Polling place locations |

**Output:**

| File | Description |
|------|-------------|
| `outputs/figures/isochrones_enhanced.png` | High-resolution annotated map (16×14 inches, 300 DPI) |

**Visualization Elements:**

| Element | Color | Representation |
|---------|-------|-----------------|
| 15-minute isochrones | Light blue (#a6cee3) | Walkable area polygons (30% opacity) |
| Population centers | Red (#e31a1c) | Circles sized by population (log scale) |
| Polling places | Navy (#2c3e50) | Star markers (size 120) |
| Basemap | OpenStreetMap | Roads, landmarks, and neighborhood context |

**Dependencies:** `geopandas`, `matplotlib`, `contextily`, `numpy`, `pathlib`

**Note:** Requires internet connection to fetch OpenStreetMap basemap tiles on first run. The log-scale sizing for population centers (`np.log1p(population) * 15`) improves visibility across the wide range of block group populations (from ~500 to ~5,000). The top 5 polling places by walkable area are automatically labeled to highlight best-performing locations.

---

#### `walkability_analysis.py`

**Purpose:** Enhances the base accessibility scores by incorporating OpenStreetMap sidewalk data and Montgomery County paving project information. Calculates a composite walkability score (0-100) for each population center's route to its nearest polling place, combining distance, infrastructure quality, and pedestrian safety metrics.

**Key Functions:**

- `load_complete_distances()` — Loads the merged distance results from previous calculations (falls back to Google walking data if complete file unavailable).
- `load_paving_data()` — Loads Montgomery County paving project data containing road quality and construction status information.
- `load_or_download_osm_data()` — Loads cached OpenStreetMap road network data, or downloads it using `osmnx` if not available. Tags road segments with `sidewalk_present` boolean based on sidewalk and footway attributes.
- `analyze_osm_sidewalk_coverage()` — Creates a 0.05-mile buffer corridor along the straight-line route and calculates the percentage of intersecting road segments that have explicit sidewalk tags.
- `analyze_paving_coverage()` — Scores intersecting road segments based on road classification (arterial/highway/collector/local), width, and construction status. Returns an average quality score from 0-100.
- `calculate_composite_walkability()` — Combines three weighted components into a final 0-100 walkability score:
  - Distance score (0-40 points): Based on walking distance thresholds
  - Road quality score (0-30 points): Derived from paving data analysis
  - Sidewalk score (0-30 points): Based on sidewalk presence and coverage percentage

**Composite Score Categories:**

| Category | Score Range | Interpretation |
|----------|-------------|-----------------|
| Excellent | 80-100 | Short distance, good infrastructure, sidewalks present |
| Good | 60-79 | Above average walkability |
| Fair | 40-59 | Moderate walkability |
| Poor | 20-39 | Below average walkability |
| Very Poor | 0-19 | Long distance, poor infrastructure, no sidewalks |

**Inputs:**

| File | Description |
|------|-------------|
| `data/outputs/accessibility_scores_complete.csv` | Merged distance results |
| `data/infrastructure/osm_roads_montgomery_enhanced.geojson` | OSM road network with sidewalk tags |
| `data/infrastructure/*paving*.geojson` | Paving project data (optional) |

**Output:**

| File | Description |
|------|-------------|
| `data/outputs/accessibility_scores_enhanced_complete.csv` | Enhanced dataset with walkability scores and categories |

**Dependencies:** `pandas`, `geopandas`, `numpy`, `shapely`, `osmnx` (optional, for downloading OSM data)

**Note:** This script is the final step in the accessibility analysis pipeline. The composite walkability score provides a more nuanced assessment than distance alone by accounting for pedestrian infrastructure quality. Critical priority areas (Very Poor walkability) are automatically identified for intervention planning. OSM data is cached locally after first download to avoid repeated API calls.

---

#### `walking_distance_matrix_fix_check.py`

**Purpose:** Verifies the completeness of Google walking distance calculations after batch processing. Identifies any gaps or missing values in both the full distance matrix and summary file, helping determine whether rate-limiting caused batch failures that require retry.

**Functionality:**

- Loads the full pairwise distance matrix (`distance_matrix_google_walking.csv`) generated by the Google Routes API batch processing
- Loads the summary minimum distances file (`accessibility_scores_google_walking.csv`)
- Reports matrix dimensions and total count of NaN values
- Verifies that the summary file contains all 203 expected population centers
- Counts the number of valid (non-NaN) minimum distance values

**Inputs:**

| File | Description |
|------|-------------|
| `data/outputs/distance_matrix_google_walking.csv` | Full pairwise distance matrix (203 rows × 49 columns) |
| `data/outputs/accessibility_scores_google_walking.csv` | Summary file with minimum distances for each center |

**Interpretation Guide:**

| Output | Meaning | Action Needed |
|--------|---------|---------------|
| NaN values = 0 | All distances calculated successfully | None - data is complete |
| NaN values > 0 | Some routes failed | Run `fill_missing_google.py` for summary or `fill_missing_matrix_google.py` for matrix |
| Summary rows < 203 | Missing population centers | Check GEOID matching in batch processing script |
| Valid distances < 203 | Some centers have no valid polling place | Run fill scripts to patch missing values |

**Dependencies:** `pandas`, `numpy`, `pathlib`

**Note:** This is a diagnostic utility script run after `google_walking_distance_calculations.py` to verify successful completion. A fully successful run will show 203 summary rows with 203 valid distances and 0 NaN values in the matrix. If gaps exist, use the companion fill scripts to patch missing data without reprocessing the entire batch.

---

---

#### `arcgis.py`

**Purpose:** Exports processed database query results from PostgreSQL to GeoJSON format for direct upload to ArcGIS Online as feature layers. Handles the conversion of Well-Known Text (WKT) geometry representations from SQL exports into shapely geometry objects suitable for spatial file formats.

**Functionality:**

- Reads two CSV files generated by the ArcGIS export queries in `useful_queries.sql`: the block group accessibility dataset and the polling places coverage dataset
- Converts the `wkt_geometry` column from WKT string format to shapely geometry objects using `shapely.wkt.loads()`
- Creates GeoDataFrames with EPSG:4326 (WGS84) coordinate reference system
- Exports as GeoJSON files ready for direct upload to ArcGIS Online as feature layers

**Inputs:**

| File | Description |
|------|-------------|
| `/tmp/arcgis_export.csv` | Block group accessibility data with WKT geometry (203 rows) |
| `/tmp/polling_places_export.csv` | Polling place coverage data with WKT geometry (49 rows) |

**Outputs:**

| File | Description |
|------|-------------|
| `/tmp/montgomery_accessibility.geojson` | Spatial GeoJSON of 203 block groups with all accessibility and demographic metrics |
| `/tmp/montgomery_polling_places.geojson` | Spatial GeoJSON of 49 polling places with coverage statistics |

**WKT Geometry Conversion:**

The SQL export queries use `ST_AsText(geom)` to serialize PostGIS geometries to WKT format. This script reverses that process, converting the text representation back into usable geometry objects:

```python
df['geometry'] = df['wkt_geometry'].apply(wkt.loads)
```

This produces valid POINT geometries for both population centers and polling places, which are then written to GeoJSON with proper coordinate reference system metadata.

**ArcGIS Online Integration:**

The output GeoJSON files are uploaded as feature layers in ArcGIS Online, where they serve as the data foundation for:
- The Montgomery County Voter Access Dashboard (block group layer with pop-up configurations)
- The Polling Location Finder (polling places layer with coverage statistics)
- The Directional/Routing Application (map-centered GPS system returning time, distance, and directions between two given places)
- The Walkability Isochrones Viewer (population centers layer with accessibility symbology)

**Dependencies:** `pandas`, `geopandas`, `shapely`

**Note:** This script is a bridge between the SQL-based analysis pipeline and the ArcGIS-based visualization deliverables. It should be run after executing the export queries in `useful_queries.sql` and before uploading the resulting GeoJSON files to ArcGIS Online. The input CSV files are expected in `/tmp/`, which is where the SQL `\copy` commands write them. Follow the same process and import/upload the polling_isochrones_all.geojson as a feature layer as well for the map content that deals with that layer/application. 

### SQL Scripts

#### `create_tables.sql`

**Purpose:** Creates the complete PostgreSQL/PostGIS database schema for the Montgomery County voter access analysis. Defines all tables, spatial indexes, primary/foreign key relationships, and generated columns for derived demographic percentages.

**Tables Created:**

| Table | Rows | Description |
|-------|------|-------------|
| `demographics_bg` | 203 | Census ACS data at block group level with generated percentage columns |
| `population_centers` | 203 | Census 2020 population-weighted centroids with point geometries |
| `polling_places` | 49 | Physical locations of Montgomery County polling places |
| `accessibility_scores` | 203 | Comprehensive distance metrics and walkability scores for each center |
| `precincts_2020` | 49 | Spatial boundaries of voting precincts (2020 election) |
| `precincts_2024` | 51 | Spatial boundaries of voting precincts after redistricting (2024 election) |
| `election_results_2020` | 49 | Vote counts by precinct for 2020 general election |
| `election_results_2024` | 51 | Vote counts by precinct for 2024 general election |
| `vulnerability_index` | 203 | Composite vulnerability scores at block group level |
| `isochrone_summary` | 245 | Walkable area metrics for each polling place by time interval |
| `county_turnout` | 1 | County-level registration and participation statistics |
| `precinct_name_mapping` | 41 | Crosswalk between 2024 and 2020 precinct names |
| `precinct_polling_map` | 41 | Connects precincts to physical polling locations |
| `demographics_tract` | 71 | Raw tract-level demographics import (all text fields) |
| `demographics_tract_clean` | 71 | Cleaned tract-level demographics with proper data types |
| `vulnerability_index_tract` | 71 | Vulnerability scores calculated using complete tract-level poverty data |

**Key Features:**

- **PostGIS spatial indexes:** GiST indexes on all geometry columns for efficient spatial queries
- **Generated columns:** `pct_black`, `pct_poverty`, and `pct_no_vehicle` automatically calculated from raw counts
- **Foreign key relationships:** `population_centers` references `demographics_bg`, `accessibility_scores` references `polling_places`
- **Cascade drops:** Tables dropped with `CASCADE` to handle dependencies cleanly

**Tract-Level vs Block Group-Level Data:**

| Level | Units | Poverty Data | Use Case |
|-------|-------|--------------|----------|
| Block Group | 203 | Suppressed (all NULL) | Fine-grained distance calculations |
| Tract | 71 | Complete (0 NULLs) | Demographic and vulnerability analysis |

**Dependencies:** PostgreSQL with PostGIS extension enabled.

**Usage:**

```bash
psql -d montgomery_voter_access -f scripts/sql/create_tables.sql
```

**Note:** This schema is normalized to Third Normal Form (3NF) per project requirements. The tract-level tables were added after discovering that Census Bureau suppresses block group poverty data.

---

#### `import_data.sql`

**Purpose:** Populates all PostgreSQL tables with data from CSV files generated by the Python processing scripts. Handles type conversion, NULL value normalization, spatial geometry creation, and calculated field generation. Includes verification queries to confirm successful imports.

**Tables Populated:**

| Table | Source CSV | Rows | Key Operations |
|-------|-----------|------|----------------|
| `population_centers` | `accessibility_scores_enhanced_complete.csv` | 203 | Creates point geometries from latitude/longitude; filters to GEOIDs starting with `1101` |
| `accessibility_scores` | `accessibility_scores_enhanced_complete.csv` | 203 | Converts 38 text columns to appropriate data types; handles `NA` string conversion to NULL |
| `isochrone_summary` | `polling_isochrone_summary.csv` | 245 | Imports walkable area metrics for 5 time intervals × 49 polling places |
| `county_turnout` | (hardcoded) | 1 | Inserts Montgomery County 2020 registration and turnout statistics |
| `precincts_2020` | `montgomery_precinct_results_2020.csv` | 49 | Imports 2020 precinct boundaries and identifiers |
| `precincts_2024` | `montgomery_precinct_results_2024.csv` | 51 | Imports 2024 precinct boundaries after redistricting |
| `election_results_2020` | `montgomery_precinct_results_2020.csv` | 49 | Presidential and Senate vote counts by precinct |
| `election_results_2024` | `montgomery_precinct_results_2024.csv` | 51 | Presidential vote counts including third-party candidates |
| `vulnerability_index` | (calculated) | 203 | Calculates z-scores and vulnerability categories from `demographics_bg` |

**Key Data Transformations:**

- `NULLIF(column, 'NA')` — Converts Python NaN string representations to SQL NULL values
- `ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)` — Creates PostGIS point geometries from coordinates
- `GEOID LIKE '1101%'` — Filters to Montgomery County block groups only
- Window functions for z-score calculation: `(pct_black - AVG(pct_black) OVER()) / NULLIF(STDDEV(pct_black) OVER(), 0)`

**Verification Output:**

| Table | Expected Count |
|-------|---------------|
| `demographics_bg` | 203 |
| `population_centers` | 203 |
| `accessibility_scores` | 203 |
| `isochrone_summary` | 245 |
| `county_turnout` | 1 |
| `precincts_2020` | 49 |
| `precincts_2024` | 51 |
| `election_results_2020` | 49 |
| `election_results_2024` | 51 |
| `vulnerability_index` | 203 |

**Usage:**

```bash
# Copy CSV files to /tmp/ (or update paths in script)
cp data/outputs/*.csv /tmp/
cp data/elections/processed/*.csv /tmp/

# Run import script
psql -d montgomery_voter_access -f scripts/sql/import_data.sql
```

**Prerequisites:** Database schema must be created first (`create_tables.sql`). PostgreSQL server must have read access to the CSV file locations.

---

#### `create_mappings.sql`

**Purpose:** Populates the PostgreSQL database with precinct name crosswalk tables that enable accurate year-over-year turnout comparisons and connect precincts to their physical polling locations. These mappings are essential for spatial analysis and distance calculations.

**Tables Populated:**

**`precinct_name_mapping`** — Establishes the relationship between 2024 and 2020 precinct naming conventions (41 matched pairs).

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key (auto-generated) |
| `name_2024` | VARCHAR(200) | Precinct name as it appears in 2024 election data |
| `name_2020` | VARCHAR(200) | Corresponding precinct name from 2020 election data |

**`precinct_polling_map`** — Connects 2020 precinct names to specific polling place facilities with their unique identifiers.

| Column | Type | Description |
|--------|------|-------------|
| `precinct_2020_name` | VARCHAR(200) | Primary key - 2020 precinct name |
| `polling_place_id` | INTEGER | Foreign key referencing `polling_places(ogc_fid)` |
| `polling_name` | VARCHAR(200) | Human-readable polling place name |

**Sample Mappings:**

| 2024 Precinct | 2020 Precinct | Polling Place |
|--------------|---------------|---------------|
| 101 WILSON COMM & ATHLETIC CTR | AFED Conference Ctr | AFED Conference Center |
| 404 ASU ACADOME | AL State University Acadome | Alabama State University / Acadome |
| 305 FRAZER CHURCH | Frazer UMC | Frazer United Methodist Church |

**Unmatched Precincts:** Approximately 10 precincts from 2024 have no direct 2020 equivalent due to new construction or precinct consolidation. These are documented in the Python election processing script output.

**Dependencies:** Must be run after `create_tables.sql` and `import_data.sql` (specifically after `polling_places` table is populated).

**Usage:**

```bash
psql -d montgomery_voter_access -f scripts/sql/create_mappings.sql
```

**Note:** The mappings in this file were derived from manual comparison of precinct boundaries, polling location addresses, and facility names. The `polling_place_id` values correspond to the `ogc_fid` field in the `polling_places` table.

---

#### `create_views.sql`

**Purpose:** Creates analytical views that pre-join multiple tables for common query patterns, simplifying downstream analysis and providing ready-to-use datasets for visualization, reporting, and client deliverables.

**Views Created:**

| View | Purpose | Key Columns |
|------|---------|-------------|
| `priority_areas` | Identifies block groups with both high vulnerability and poor walkability—highest priority for intervention | GEOID, population, vulnerability category, walkability category, walking distance |
| `polling_coverage` | Aggregates statistics by polling place showing how many residents each location serves | Polling place name, centers served, average walking distance, total population served |
| `turnout_comparison` | Compares 2020 and 2024 vote totals for each matched precinct | Precinct names, 2020 votes, 2024 votes, vote change |
| `full_analysis` | Comprehensive view joining all demographic, accessibility, and vulnerability metrics | 25+ columns including all distance metrics, demographics, and walkability scores |
| `walkability_demographics` | Aggregates demographic characteristics by walkability category | Walkability category, block group count, total population, average demographic percentages |
| `turnout_accessibility_correlation` | Examines relationship between voting participation and polling place accessibility | Precinct name, vote change, percentage change, average walking distance, walkability score |
| `accessibility_analysis_complete` | Joins accessibility scores with tract-level demographics for complete poverty data | Block group GEOID, tract GEOID, walking distances, tract-level poverty and vulnerability scores |

**Key Use Cases:**

| View | Use Case |
|------|----------|
| `priority_areas` | Generate list of GEOIDs requiring immediate intervention; export for ArcGIS mapping |
| `polling_coverage` | Identify polling places serving the most residents; evaluate facility placement efficiency |
| `turnout_comparison` | Analyze precinct-level turnout changes between elections; identify areas with declining participation |
| `full_analysis` | Export complete dataset for external analysis tools (R, Python, Tableau) |
| `walkability_demographics` | Generate summary statistics for client presentations and reports |
| `turnout_accessibility_correlation` | Statistical analysis of relationship between accessibility and voter participation |
| `accessibility_analysis_complete` | Primary data source for R statistical scripts requiring complete poverty data |

**Sample Queries:**

```sql
-- Export priority areas for ArcGIS
SELECT * FROM priority_areas;

-- Find polling places with highest average walking distance
SELECT name, avg_walking_miles, total_population_served 
FROM polling_coverage 
ORDER BY avg_walking_miles DESC 
LIMIT 10;

-- Analyze turnout change by precinct
SELECT precinct_name, votes_2020, votes_2024, pct_change 
FROM turnout_accessibility_correlation 
ORDER BY pct_change ASC;
```

**Dependencies:** All base tables must be populated before creating views. Requires `create_tables.sql` and `import_data.sql` to be executed first.

**Note:** The `accessibility_analysis_complete` view uses tract-level demographics (`demographics_tract_clean` and `vulnerability_index_tract`) because poverty data at the block group level is suppressed by the Census Bureau. This view is the primary input for the R statistical analysis scripts.

---

#### `useful_queries.sql`

**Purpose:** Provides a collection of pre-built analytical queries for rapid insight generation, client reporting, and data export. These queries leverage the analytical views to answer common questions about voting accessibility, turnout patterns, and demographic disparities.

**Query Categories:**

| Query | Purpose | Typical Output |
|-------|---------|---------------|
| Summary Statistics | Overall project metrics at a glance | 6 rows with key counts and averages |
| Most Walkable Polling Places | Identify best-performing locations (top 10) | Polling place names with average walking distance |
| Least Walkable Polling Places | Identify locations needing improvement (bottom 10) | Polling place names with longest average walking distance |
| Largest Turnout Drop | Precincts with greatest voting decline (2020-2024) | Precinct names with vote change and accessibility metrics |
| Turnout Increase | Precincts with improved voter participation | Precinct names with positive vote change |
| Correlation Analysis | Statistical relationship between turnout and accessibility | Correlation coefficients (r) and sample size |
| Walkability Demographics | Demographic breakdown by walkability category | Average % Black, % poverty, and % no vehicle per category |
| Priority Areas | Block groups with high vulnerability and poor walkability | GEOIDs with demographic and distance metrics |
| Export Query | Complete dataset for ArcGIS and Data Studio integration | All key metrics with WKT geometry for external tools |

**Key Insights Available:**

- High vulnerability areas (greater % Black, higher poverty) have shorter walking distances to polling places
- Only 35% of precincts saw increased turnout from 2020 to 2024
- 28% of areas have "Poor" or "Very Poor" walkability

**Usage Examples:**

```sql
-- Quick project overview
\i scripts/sql/useful_queries.sql

-- Export data for ArcGIS
\copy (SELECT ... export query ...) TO '/tmp/arcgis_export.csv' CSV HEADER;
```

**Dependencies:** All analytical views must be created first (`create_views.sql`). Requires populated base tables from `import_data.sql`.

---

### Google Apps Script

#### `refreshData.gs`

**Purpose:** Automated hourly pipeline that fetches live data from the Supabase cloud database via the Edge Function REST API and populates a Google Sheet with one sheet per analytical view. This serves as the data cache for Google Data Studio reporting.

**Architecture:**
```
Supabase Edge Function (HTTPS)
    ↓ POST request with view name
Google Apps Script (Time Trigger: Every Hour)
    ↓
Google Sheets (One sheet per view, auto-refreshing)
    ↓ (future)
Google Data Studio
```

**Key Features:**

- Queries 11 analytical views: `polling_coverage`, `turnout_accessibility_correlation`, `walkability_demographics`, `full_analysis`, `dashboard_summary`, `dashboard_turnout_timeline`, `distance_method_comparison`, `isochrone_vulnerability_coverage`, `sidewalk_equity_analysis`, `routing_outliers`, `distance_tier_demographics`
- Service role key authentication for secure API access
- Automatic column header generation from JSON response keys
- Nested object flattening for Data Studio compatibility
- Hourly time-based trigger for continuous data freshness

**Dependencies:** Supabase Edge Function (`query`), Google Sheets, Google Apps Script time trigger

---

## Data Inventory

### Raw Data Sources

#### Census and Demographic Data

| File | Source | Description |
|------|--------|-------------|
| `CenPop2020_Mean_BG01.txt` | U.S. Census Bureau | Population-weighted centroids for all census block groups in the United States. Contains coordinates (latitude/longitude), population counts, and component GEOID parts (state, county, tract, block group). |
| ACS 5-Year Estimates (2020-2024) | U.S. Census Bureau (via tidycensus API) | American Community Survey demographic data retrieved programmatically. Includes total population, race/ethnicity counts, median household income, poverty status, vehicle access, and educational attainment at tract and block group levels. |

#### Election Data

| File | Source | Description |
|------|--------|-------------|
| `al_2024_gen_all_prec.shp` | Redistricting Data Hub | Shapefile containing 2024 precinct boundaries joined with general election results for presidential, judicial, and congressional races. Column naming follows pattern `G[YEAR][OFFICE][PARTY][CANDIDATE]`. |
| `al_2020.shp` | UFL Election Lab / AL Secretary of State | Shapefile containing 2020 precinct boundaries with election results for presidential and Senate races. |
| `2020_General_Total_Ballots_Cast_Report.csv` | Alabama Secretary of State | County-level registration and turnout statistics. Contains registered voters, total ballots cast, absentee ballots, and provisional ballots for each Alabama county. |

#### Polling Place Data

| File | Source | Description |
|------|--------|-------------|
| `Al_Polls_Flood_SLED.shp` (+ associated files) | Client-provided (SPLC) | Statewide Alabama polling places shapefile. Contains point geometries for all voting locations with attributes including polling place name, address, county, and precinct assignment. |

#### Infrastructure Data

| File | Source | Description |
|------|--------|-------------|
| OpenStreetMap Alabama Extract | OpenStreetMap (via osmnx) | Road network with sidewalk tags. Downloaded programmatically and cached locally. Contains highway classifications, sidewalk presence indicators, footway information, and street names. |
| Paving Project Data | City of Montgomery Open Data Portal | Road quality and construction status information. Contains road classification, width, and project status for paving initiatives. |

#### Routing Engine Data

| File | Source | Description |
|------|--------|-------------|
| `alabama-latest.osrm` | OpenStreetMap (processed via OSRM) | Pre-processed routing graph for Alabama used by OSRM routing engine. Enables network distance calculations for driving and walking. |
| Valhalla Routing Tiles | OpenStreetMap (processed via Valhalla) | Pre-processed routing tiles for pedestrian isochrone generation. Used for walkable area polygon creation. |

---

### Processed Data Outputs

#### Census and Demographic Outputs

| File | Generating Script | Description |
|------|-------------------|-------------|
| `montgomery_demographics_tract.csv` | `scripts/r/api_acs_data_pull.R` | Tract-level demographic data (71 rows) with calculated percentages for race, poverty, vehicle access, and educational attainment. Includes vulnerability index scores and categories. Non-spatial. |
| `montgomery_demographics_bg.csv` | `scripts/r/api_acs_data_pull.R` | Block group-level demographic data (203 rows) with calculated percentages. Poverty data is largely NULL due to Census suppression. Non-spatial. |
| `montgomery_demographics_tract.geojson` | `scripts/r/api_acs_data_pull.R` | Tract-level demographic data with spatial geometries for GIS integration. Spatial. |
| `montgomery_demographics_bg.geojson` | `scripts/r/api_acs_data_pull.R` | Block group-level demographic data with spatial geometries. Spatial. |
| `population_centers_montgomery.geojson` | `Downloaded from Census Website (Block Groups)` | Population-weighted centroids for 203 Montgomery County block groups. Contains point geometries, population counts, and GEOIDs. Spatial. |

#### Election Outputs

| File | Generating Script | Description |
|------|-------------------|-------------|
| `montgomery_precinct_results_2024.csv` | `scripts/python/election_data_processing.py` | Cleaned 2024 election results for 51 Montgomery County precincts. Contains total presidential votes and Democratic vote share. Non-spatial. |
| `montgomery_precinct_results_2020.csv` | `scripts/python/election_data_processing.py` | Cleaned 2020 election results for 49 Montgomery County precincts. Non-spatial. |
| `montgomery_precincts_2024.geojson` | `scripts/python/election_data_processing.py` | 2024 precinct boundaries with election results attached. Spatial. |
| `montgomery_precincts_2020.geojson` | `scripts/python/election_data_processing.py` | 2020 precinct boundaries with election results attached. Spatial. |
| `election_data_combined_2020_2024.csv` | `scripts/python/election_data_processing.py` | Merged dataset with 2020 and 2024 results for matched precincts. Contains turnout change metrics (absolute and percentage). Non-spatial. |
| `montgomery_precincts_combined_2020_2024.geojson` | `scripts/python/election_data_processing.py` | Merged spatial dataset with both election years. Spatial. |

#### Polling Place Outputs

| File | Generating Script | Description |
|------|-------------------|-------------|
| `polling_places_montgomery_clean_2020.csv` | `scripts/python/polling_place_processing.py` | Standardized polling place data for 49 Montgomery County locations. Contains unique IDs, addresses, and extracted coordinates. Non-spatial. |
| `polling_places_montgomery_2020.geojson` | `scripts/python/polling_place_processing.py` | Spatial version of polling place data with point geometries. Primary input for all distance calculations. Spatial. |
| `montgomery_polling_places_2020.shp` | `scripts/python/polling_place_processing.py` | Shapefile format for ArcGIS compatibility. Spatial. |

#### Distance Calculation Outputs

| File | Generating Script | Description |
|------|-------------------|-------------|
| `accessibility_scores_by_tract.csv` | `scripts/python/distance_calculations.py` | Euclidean and Manhattan distance metrics for 203 population centers. Contains minimum distances to polling places and civic infrastructure, plus composite accessibility scores and categories. |
| `distance_matrix_montgomery.csv` | `scripts/python/distance_calculations.py` | Full pairwise Euclidean distance matrix (203 centers × 49 polling places). |
| `accessibility_scores_network.csv` | `scripts/python/networking_distance_calculations.py` | OSRM driving distance metrics. Contains minimum network distance to nearest polling place for each center. |
| `distance_matrix_network.csv` | `scripts/python/network_distance_calculations.py` | Full pairwise OSRM driving distance matrix (203 × 49). |
| `accessibility_scores_walking.csv` | `scripts/python/network_walking_distance_calculations.py` | OSRM walking distance metrics. Contains minimum pedestrian network distance to nearest polling place. |
| `distance_matrix_walking.csv` | `scripts/python/network_walking_distance_calculations.py` | Full pairwise OSRM walking distance matrix (203 × 49). |
| `accessibility_scores_google_walking.csv` | `scripts/python/google_walking_distance_calculations.py` | Google Routes API walking distance metrics. Contains minimum pedestrian distance and nearest polling place index. |
| `distance_matrix_google_walking.csv` | `scripts/python/google_walking_distance_calculations.py` | Full pairwise Google walking distance matrix (203 × 49). |

#### Isochrone Outputs

| File | Generating Script | Description |
|------|-------------------|-------------|
| `polling_isochrones_all.geojson` | `scripts/python/generating_polling_isochrones.py` | Combined isochrone polygons for 5 time intervals (5, 10, 15, 20, 30 minutes) across all 49 polling places (245 total polygons). Contains area calculations and population served metrics. Spatial. |
| `polling_isochrone_summary.csv` | `scripts/python/generating_polling_isochrones.py` | Summary table with area (square miles) and population served for each isochrone. Non-spatial. |

#### Infrastructure Outputs

| File | Generating Script | Description |
|------|-------------------|-------------|
| `osm_roads_montgomery_enhanced.geojson` | `scripts/python/walkability_analysis.py` | OpenStreetMap road network for Montgomery County with sidewalk presence tags. Downloaded programmatically and cached locally. Spatial. |

#### Merged and Enhanced Outputs

| File | Generating Script | Description |
|------|-------------------|-------------|
| `accessibility_scores_complete.csv` | `scripts/python/merge_distance_calculations.py` | Combined dataset with all distance metrics (Euclidean, Manhattan, OSRM driving, OSRM walking, Google walking). Contains cross-comparison ratios and 38 columns total. |
| `accessibility_scores_enhanced_complete.csv` | `scripts/python/walkability_analysis.py` | Final enhanced dataset adding OSM sidewalk coverage, paving quality scores, and composite walkability scores (0-100) with categories. Primary input for statistical analysis. |

#### Statistical Analysis Outputs

| File | Generating Script | Description |
|------|-------------------|-------------|
| `turnout_change_2020_2024.csv` | `scripts/r/turnout_modeling.R` | Precinct-level turnout comparison with vote change and percentage change metrics. |
| `walkability_summary.csv` | `scripts/r/turnout_modeling.R` | Count and percentage distribution of walkability categories across all block groups. |
| `merged_analysis_tract_level.csv` | `scripts/r/turnout_modeling.R` | Combined accessibility and tract-level demographic dataset (201 rows). Used for regression modeling. |
| `correlation_data_tract.csv` | `scripts/r/turnout_modeling.R` | Correlation matrix data for distance metrics and demographic variables. |
| `regression_results_tract_level.txt` | `scripts/r/turnout_modeling.R` | Full regression model outputs with coefficients, p-values, R-squared values, and vulnerability category summaries. |

---

### Visualization Outputs

| File | Generating Script | Description |
|------|-------------------|-------------|
| `isochrones_enhanced.png` | `scripts/python/visual_preview.py` | Publication-quality map with 15-minute walking isochrones, population centers, and polling places on OpenStreetMap basemap. |
| `isochrone_panel_r.png` | `scripts/r/isochrone_final.R` | Faceted five-panel figure showing 5/10/15/20/30-minute walking isochrones with polling places on basemap. |
| `walking_distance_choropleth_r.png` | `scripts/r/choropleth_map.R` | Tract-level choropleth map colored by Google walking distance using viridis color scale. |
| `vulnerability_bar_chart_r.png` | `scripts/r/vulnerability_bar_chart.R` | Bar chart comparing walking distances across vulnerability categories with standard deviation error bars. |
| `correlation_heatmap_r.png` | `scripts/r/correlation_heatmap.R` | Clustered correlation heatmap with annotated coefficients and significance stars for all numeric variables. |

---

## Cloud Database & Live Dashboard Integration

This project includes a fully automated cloud database pipeline built on Supabase (PostgreSQL). The local database was migrated to the cloud to enable live querying from any internet-connected tool without requiring the original development environment.

### Architecture

```
Supabase PostgreSQL (Cloud)
    ↓ Edge Function (REST API over HTTPS)
Google Apps Script (Hourly Refresh via Time Trigger)
    ↓
Google Sheets (Data Cache - One Sheet Per View)
    ↓
Google Data Studio (Interactive Dashboard - Planned)
```

### Why This Pipeline Exists

- **Network Restrictions:** Direct Data Studio-to-PostgreSQL connections are blocked on many university and institutional networks due to port blocking (5432, 6543)
- **HTTPS Bypass:** Supabase's Edge Functions serve database queries over standard HTTPS (port 443), which is universally accessible
- **Reliable Cache:** Google Sheets acts as a reliable intermediary that Data Studio can always reach
- **Automation:** Hourly refresh via Apps Script time triggers ensures data stays current without manual intervention
- **Scalability:** The pipeline can be reconfigured to point at new data sources or additional views without changing the front-end

### Current Status

| Component | Status |
|-----------|--------|
| Supabase Cloud Database | Deployed and populated with all tables and views |
| Edge Function (`query`) | Deployed, tested, and serving data via HTTPS |
| Google Apps Script | Deployed with hourly time trigger, creating one sheet per view |
| Google Sheets | Populated with 11 analytical views, auto-refreshing hourly |
| Data Studio Report | Planned for future development phase |

---

## Deployment Deliverables

Three interactive applications were built for client delivery, integrating walking distance analysis, isochrone visualization, and street-level routing capabilities:

### Montgomery County Voter Access Dashboard (ArcGIS Dashboard)

A comprehensive monitoring dashboard featuring:
- **Live indicator elements:** Total block groups, average walking distance, average walkability score, and walkability distribution percentages
- **Interactive block group map:** Color-coded by accessibility category (Excellent to Very Poor) with pop-up details showing GEOID, demographics, walking distance, and nearest polling place for each of the 203 population centers
- **Polling place coverage layer:** 49 polling locations with pop-ups showing address, average walking distance, population served, and number of centers assigned
- **Walkability isochrones layer:** Time-sorted walkable area polygons (5/10/15/20/30 minutes) for visual assessment of coverage
- **Demographic filters:** Dropdown selectors for vulnerability category and walkability category to focus on specific community subsets
- **Legend and layer controls:** Toggle between population centers, polling places, and isochrone layers

### Directional Routing Widget (ArcGIS Experience Builder, Embedded)

An interactive routing tool embedded within the dashboard application that provides street-level directions from any user-specified address to nearby polling places. Features include:
- **Address search bar:** Users enter any address as a starting point
- **Multi-modal routing:** Supports walking time, walking distance, driving time, driving distance, trucking time, and trucking distance
- **Route visualization:** Turn-by-turn directions displayed on the map with highlighted route path
- **Polling place selection:** Users can click any locations as their destination
- **Real-time distance calculation:** Displays precise walking/driving distance and estimated travel time (proper routing)
- **Integration with accessibility data:** Polling place pop-ups show walkability scores and demographic context alongside routing information

### Nearby Polling Location Finder (ArcGIS Instant Apps - Nearby Template, Embedded)

A public-facing tool embedded within the dashboard application and built with the Nearby template that allows constituents to:
- Enter/Click any address in Montgomery County map
- See the closest polling places and population centers within a 0-5 mile radius (base value on distance slider starting at 2.5 miles)
- Get walking and driving directions with distance and time estimates
- View accessibility ratings for each nearby polling location
- Filter results by travel mode (walking or driving)

### Walkability Isochrones Viewer (ArcGIS Experience Builder, Embedded)

An interactive application embedded within the dashboard that features:
- **Time-sorted isochrone layer:** 245 walkable area polygons across 5 time intervals (5, 10, 15, 20, 30 minutes)
- **Population center overlay:** 203 block group centroids colored by accessibility score, sized by population
- **Directional/routing widget (embedded):** Users can search an address and get walking directions to any polling place directly within the isochrone viewer
- **Layer visibility controls:** Toggle between time intervals to visualize how walkable coverage expands

---

## Additional Analytical Views

Beyond the first few core views documented in `create_views.sql`, I decided to add more to the same script and place them within the cloud database. This includes specialized views for equity analysis, infrastructure assessment, and dashboard integration:

| View | Purpose | Key Metrics |
|------|---------|-------------|
| `distance_method_comparison` | Side-by-side comparison of all five distance calculation methods for each block group | Euclidean, Manhattan, OSRM driving, OSRM walking, Google walking distances with cross-comparison ratios |
| `isochrone_vulnerability_coverage` | Walkable area coverage metrics joined with demographic vulnerability data | Polling place name, time interval, area served, population covered, vulnerability category, average demographics |
| `sidewalk_equity_analysis` | Quantifies how sidewalk infrastructure varies across vulnerability categories | Block groups per category, blocks with sidewalks, average sidewalk coverage percentage, average walkability score |
| `routing_outliers` | Identifies block groups where pedestrian routes are significantly longer than straight-line distances | Google/Euclidean ratio, routing quality classification (Severe detour/Moderate detour/Direct route/Normal), sidewalk presence |
| `distance_tier_demographics` | Buckets block groups by walking distance and shows demographic composition for each tier | Distance tier (Under 0.5 mi to Over 5 mi), block group count, total population, average demographics |
| `dashboard_summary` | Single-row summary for executive dashboards | Total block groups, total population, total polling places, matched precincts, average walking distance, average walkability score |
| `dashboard_turnout_timeline` | Turnout data formatted for line charts and scatter plots | Precinct name, 2020 votes, 2024 votes, vote change, percentage change, walking distance, walkability score |

### Cross-Comparison Ratios

Between the five distance calculation methods, cross-comparison ratios provide insight into routing efficiency:

| Ratio | Formula | Average | Interpretation |
|-------|---------|---------|----------------|
| Driving / Euclidean | network ÷ straight-line | 0.86x | Driving routes are ~14% shorter than straight-line |
| Walking / Euclidean | OSRM walking ÷ straight-line | 0.84x | Pedestrian routes are ~16% shorter than straight-line |
| Google / OSRM Walking | Google ÷ OSRM | 1.19x | Google estimates ~19% longer walking distances |
| Walking / Driving | OSRM walking ÷ driving | 0.97x | Pedestrian routes nearly match driving routes |

**Note:** The `priority_areas` view and a now deleted `dashboard_priority_map` view return zero rows. This is a legitimate finding: no block groups in Montgomery County simultaneously meet the criteria for both high vulnerability AND poor/very poor walkability. High-vulnerability areas actually have shorter walking distances and better walkability, as confirmed by the regression analysis.

---

## Key Findings

### Voting Accessibility

- **Average walking distance to polling places:** 1.02 miles (Euclidean), 1.40 miles (OSRM walking), 1.58 miles (Google walking)
- **15-minute walkable coverage:** Average 0.74 sq miles per polling place, serving approximately 1,408 people
- **Total walkable area (all polling places):** 36.16 sq miles
- **Accessibility distribution:** 28% of areas have "Poor" or "Very Poor" walkability
- **Walkability distribution:** 45.2% of walking routes have documented city maintenance (actively paved/maintained, the rest are unknown/older). 54.6/100 Montgomery road quality score, meaning road segments or walking routes are in fair to decent condition (road width, classification, and status are all not excellent or not too dangerous)

### Demographic Disparities

- **Paradoxical finding:** High vulnerability areas (greater % Black, higher poverty) have *shorter* walking distances to polling places (1.22 miles vs. 2.52 miles for low % Black areas) --> likely due to inner-city areas being highly connected by sidewalks and various infrastructure, which are areas where many marginalized people tend to congregate or live in
- **Vulnerability index is negatively correlated with walking distance:** r = -0.308, p < 0.001
- **Poverty data suppression:** Block group-level poverty data is unavailable from the Census Bureau; tract-level analysis reveals complete poverty metrics

### Turnout Patterns

- Only **35% of precincts** saw increased turnout from 2020 to 2024
- Accessibility metrics show **weak correlation** with turnout change (r = -0.142 for distance, r = 0.089 for walkability score)
- Equitable physical placement of polling places does not translate to equitable voter participation

### Recommendations

1. **Target infrastructure improvements** in Very Poor walkability areas with high vulnerability scores
2. **Investigate non-distance barriers** to voting (transportation availability, voter education, registration processes)
3. **Deploy mobile polling units** in the 22% of block groups with Poor accessibility
4. **Monitor turnout trends** in precincts showing significant decline (2020-2024)

---

## Configuration Requirements

| Service | Parameter | Location |
|---------|-----------|----------|
| Census API | API Key | `scripts/r/api_acs_data_pull.R` |
| Google Routes API | API Key | `scripts/python/google_walking_distance_calculations.py` |
| OSRM (Driving) | URL: `http://localhost:5001` | `scripts/python/network_distance_calculations.py` |
| OSRM (Walking) | URL: `http://localhost:5002` | `scripts/python/network_walking_distance_calculations.py` |
| Valhalla | URL: `http://localhost:8002` | `scripts/python/generate_polling_isochrones.py` |
| PostgreSQL (Local) | Connection string | `scripts/sql/create_tables.sql` |
| Supabase (Cloud) | Connection string | Google Apps Script, Google Data Studio |
| ArcGIS Online | Feature layers, web maps | Dashboard and Instant Apps |

---

## API Integration & Polling Lookup System

### Python Scripts

#### `polling_access_analysis.py`

**Purpose:**

Computes polling place accessibility metrics for Montgomery County census tracts through spatial analysis and demographic integration. The script identifies nearest polling locations, measures tract-level accessibility, integrates demographic indicators, generates visualization outputs, and creates API-style polling lookup functionality for future dashboard or frontend integration.

---

### Core Analytical Workflow

#### 1. Spatial Data Loading

Loads:

- Polling place shapefile (`Al_Polls_Flood_SLED.shp`)
- Census tract polygons (`Alabama_Census_Tracts_2020.shp`)
- Hospital infrastructure shapefile (`Hospitals.shp`)

All datasets are validated and reprojected into:

```
EPSG:5070 (NAD83 / Conus Albers)
```

Projected coordinates are required because geographic latitude/longitude systems produce inaccurate distance calculations.

---

#### 2. Census Tract Centroid Generation

Census tract polygons are converted into centroid points:

```python
tract_centroids["centroid"] = tract_centroids.geometry.centroid
```

Centroids serve as representative tract population locations for accessibility calculations.

---

#### 3. Polling Accessibility Computation

For every census tract centroid:

- Calculate nearest polling location
- Compute Euclidean distance
- Convert meters to miles
- Attach nearest precinct metadata

Outputs:

| Variable | Description |
|-----------|-------------|
| nearest_poll_name | Closest polling location |
| nearest_poll_address | Polling place address |
| nearest_poll_city | Polling place city |
| nearest_poll_miles | Distance to polling location |

---

#### 4. Infrastructure Accessibility Comparison

Additional civic infrastructure accessibility metrics:

- Distance to nearest hospital
- Comparative accessibility relationships

Output variable:

| Variable | Description |
|-----------|-------------|
| nearest_hospital_distance_miles | Distance to nearest hospital |

---

#### 5. Demographic Integration

Accessibility metrics are merged with Census demographics:

Integrated variables:

- Total population
- Black population
- White population
- Hispanic population
- Asian population
- American Indian population
- Native Hawaiian / Pacific Islander population
- Multi-racial population

Demographic integration enables equity-oriented accessibility assessment.

---

#### 6. Accessibility Classification

Polling accessibility is categorized:

| Distance Threshold | Category |
|--------------------|-----------|
| < 1 mile | Very Close |
| 1–3 miles | Moderate |
| 3–5 miles | Limited |
| > 5 miles | Poor Access |

Classification supports dashboard visualization and policy interpretation.

---

#### 7. User Query System

Frontend/API-compatible lookup system:

Example:

```python
get_nearest_poll("36104 Montgomery AL")
```

Accepts:

- ZIP code
- Address
- Precinct name

Returns:

```json
{
 "nearest_polling_location": {},
 "distance_miles": 0.82,
 "access_level": "Very Close",
 "census_tract": "01001020100",
 "race_breakdown": {}
}
```

Designed for future web application deployment.

---

### Raw Data Requirements

Required directory structure:

```
data/
└── raw/
    ├── polling_places/
    │   └── Al_Polls_Flood_SLED.shp
    ├── Alabama_Census_Tracts_2020/
    │   └── Alabama_Census_Tracts_2020.shp
    └── Hospitals/
        └── Hospitals.shp
```

If file paths differ, modify:

```python
file_path =
gpd.read_file()
```

statements accordingly.

Cross-platform path handling may alternatively use:

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

poll_path = BASE_DIR / "data" / "raw" / "polling_places"
```

This prevents hardcoded directory failures.

---

### Processed Outputs

Generated outputs:

| File | Description |
|-------|-------------|
| tract_polling_distances.csv | Census tract polling distances |
| tract_polling_distances.geojson | Spatial accessibility output |
| final_polling_access_table.csv | Final merged analytical table |
| polling_api_output.json | API testing responses |

---

### Visualization Outputs

Generated figures:

| File | Description |
|-------|-------------|
| alabama_polling_access_map.png | Polling accessibility choropleth |
| distance_distribution.png | Poll distance histogram |
| access_levels.png | Accessibility category counts |
| race_vs_distance_black.png | Black population vs polling distance |
| race_vs_distance_hisp.png | Hispanic population vs polling distance |
| black_population_map.png | Black population census tract map |
| WHITE_x_map.png | White population map |
| ASIAN_x_map.png | Asian population map |
| HISP_x_map.png | Hispanic population map |
| poll_vs_hospital.png | Polling access vs hospital access |

---

### Configuration Requirements

Modify county filtering:

```python
polls_clean = polls_clean[
    polls_clean["County"] == "Montgomery"
]
```

Change Census county FIPS:

```python
tracts = tracts[
    tracts["COUNTYFP20"] == "101"
]
```

County FIPS updates allow expansion beyond Montgomery County.

Examples:

| County | FIPS |
|---------|------|
| Montgomery | 101 |
| Dallas | 047 |
| Perry | 105 |
| Lowndes | 085 |

---

### Future Expansion Notes

The accessibility framework was designed for county scalability.

Future extensions may include:

- Sidewalk network integration
- School accessibility comparisons
- Public transportation routing
- Additional healthcare infrastructure layers
- Multi-county Black Belt deployment
- Network routing engines replacing Euclidean distance measurements
- Frontend deployment of polling lookup API functionality

## License

This project is produced for the Southern Poverty Law Center (SPLC) as a capstone project. All rights reserved.