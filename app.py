import streamlit as st   
import geopandas as gpd
import pandas as pd
import pydeck as pdk
from living_wage import living_wage_table  # Ensure this module contains the living_wage_table variable or function
from breakdown import living_wage_breakdown  # Ensure this module contains the living_wage_breakdown function

st.set_page_config(page_title="Fort Worth Living Wage Explorer", layout="wide")
st.title("🏠 Fort Worth Living Wage Housing Affordability Explorer")

# ---------- Sidebar Inputs ----------
st.sidebar.header("User Inputs")
housing_cost = st.sidebar.slider(
    "Select your monthly housing budget ($)", min_value=800, max_value=4000, value=1600, step=50
)
family_type_options = [
    "1 Adult", "1 Adult 1 Child", "1 Adult 2 Children", "1 Adult 3 Children",
    "2 Adults (1 Working)", "2 Adults (1 Working) 1 Child", "2 Adults (1 Working) 2 Children", "2 Adults (1 Working) 3 Children",
    "2 Adults (2 Working)", "2 Adults (2 Working) 1 Child", "2 Adults (2 Working) 2 Children", "2 Adults (2 Working) 3 Children"
]
family_type = st.sidebar.selectbox("Select your family type", family_type_options)
bedroom_options = {
    "All Units": "median_rent_all",
    "Studio (0 BR)": "median_rent_0br",
    "1 Bedroom": "median_rent_1br",
    "2 Bedrooms": "median_rent_2br",
    "3 Bedrooms": "median_rent_3br",
    "4 Bedrooms": "median_rent_4br",
    "5+ Bedrooms": "median_rent_5pbr"
}
bedroom_label = st.sidebar.selectbox("Number of Bedrooms", list(bedroom_options.keys()))
bedroom_col = bedroom_options[bedroom_label]

# ---------- Data Loaders ----------
@st.cache_data
def load_housing_gdf():
    gdf = gpd.read_file("fort_worth_grid_pieces_bedrooms.geojson")
    gdf = gdf.to_crs(4326)
    return gdf

@st.cache_data
def get_city_boundary():
    city_gdf = gpd.read_file("fort_worth_city_boundary.geojson")  # Adjust filename if needed!
    city_gdf = city_gdf.to_crs(4326)
    return city_gdf

gdf = load_housing_gdf()
city_gdf = get_city_boundary()
gdf = gdf[gdf[bedroom_col] > 0].copy()

# ---------- Living Wage Data ----------
breakdown_df = living_wage_breakdown(q=0.40)
breakdown_df.columns = [col.strip().lower().replace('#', '').strip() for col in breakdown_df.columns]
filtered = breakdown_df.loc[[family_type]] if family_type in breakdown_df.index else None

st.markdown(f"### 👨‍👩‍👧 Selected Family Type: `{family_type}`")
if filtered is not None and not filtered.empty:
    total_living_wage = filtered["total"].values[0]
    st.success(f"**Required Living Wage** (with taxes, 40th percentile costs): **${total_living_wage:,.0f}/month**")
else:
    st.warning("No matching data found for this family type.")

# ---------- Color Coding ----------
def to_color(rent):
    if rent <= housing_cost:
        return [0, 185, 0, 120]  # green, semi-transparent
    else:
        return [212, 0, 0, 120]  # red, semi-transparent

gdf["fill_color"] = gdf[bedroom_col].apply(to_color)

def extract_coords(geom):
    if geom is None:
        return []
    if geom.geom_type == 'Polygon':
        return [list(geom.exterior.coords)]
    elif geom.geom_type == 'MultiPolygon':
        return [list(p.exterior.coords) for p in geom.geoms]
    else:
        return []

gdf["coordinates"] = gdf["geometry"].apply(extract_coords)
gdf["lon"] = gdf.geometry.centroid.x
gdf["lat"] = gdf.geometry.centroid.y

# ---------- City Boundary for pydeck ----------
city_gdf_flat = city_gdf.explode(index_parts=False).reset_index(drop=True)

def get_polygon_coords(geom):
    if geom.geom_type == "Polygon":
        return [list(geom.exterior.coords)] + [list(ring.coords) for ring in geom.interiors]
    return []

city_gdf_flat["coordinates"] = city_gdf_flat.geometry.apply(get_polygon_coords)

# For LineLayer: Each ring (exterior or hole) as separate path
all_boundary_lines = []
for geom in city_gdf_flat.geometry:
    if geom.geom_type == "Polygon":
        all_boundary_lines.append(list(geom.exterior.coords))
        for ring in geom.interiors:
            all_boundary_lines.append(list(ring.coords))
city_lines_df = pd.DataFrame({"path": all_boundary_lines})

# ---------- MAP ----------
st.subheader(f"🗺️ All Grid Cells in Fort Worth ({bedroom_label})\nGreen = Below Budget, Red = Above Budget")

tooltip = {
    "html": (
        f"<b>{bedroom_label}  Rent: ${{{bedroom_col}}}</b>"
    
    ),
    "style": {"color": "white"}
}

tract_layer = pdk.Layer(
    "PolygonLayer",
    data=gdf,
    get_polygon="coordinates",
    get_fill_color="fill_color",
    pickable=True,
    auto_highlight=True,
    stroked=True,
    get_line_color=[60, 60, 60, 90],   # light gray outline for tracts
    line_width_min_pixels=1,
)
city_boundary_layer = pdk.Layer(
    "PolygonLayer",
    data=city_gdf_flat,
    get_polygon="coordinates",
    get_fill_color=[0, 0, 0, 30],    # faint gray fill
    stroked=True,
    get_line_color=[0, 0, 0, 200],   # dark outline for fill
    line_width_min_pixels=1,
)
city_outline_layer = pdk.Layer(
    "LineLayer",
    data=city_lines_df,
    get_path="path",
    get_color=[0, 0, 0, 255],
    get_width=6,  # bold black
)
initial_view = pdk.ViewState(
    longitude=gdf["lon"].mean(),
    latitude=gdf["lat"].mean(),
    zoom=10,
    pitch=0,
)

st.pydeck_chart(
    pdk.Deck(
        layers=[tract_layer, city_boundary_layer, city_outline_layer],
        initial_view_state=initial_view,
        tooltip=tooltip,
        map_style="mapbox://styles/mapbox/light-v9"
    )
)

# ---------- Color legend ----------
st.markdown(
    """
    <div style="display: flex; align-items: center;">
        <div style="background: linear-gradient(to right, #00b900, #d40000); width: 160px; height: 18px; margin-right: 10px;"></div>
        <div>Affordable (Green) &larr; &rarr; Not Affordable (Red)</div>
    </div>
    """, unsafe_allow_html=True
)

# ---------- Data Table & Download ----------
st.subheader("📊 Living Wage Table")
st.dataframe(living_wage_table(q=0.40))

st.subheader("📉 Living Wage Breakdown")
st.dataframe(living_wage_breakdown(q=0.40))

# ---------- Footer ----------
st.markdown(
    """
    <div class="footer">
        Made in FwLab<br>
        Data: <a href="https://data.census.gov/profile/Fort_Worth_city,_Texas" target="_blank">Census Data</a>
    </div>
    """,
    unsafe_allow_html=True
)
