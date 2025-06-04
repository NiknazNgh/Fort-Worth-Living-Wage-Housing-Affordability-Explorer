import streamlit as st 
import geopandas as gpd
import pandas as pd
import pydeck as pdk
from breakdown import living_wage_breakdown
streamlit
geopandas
pandas
pydeck



st.set_page_config(page_title="Fort Worth Living Wage Explorer", layout="wide")
st.title("🏠 Fort Worth Living Wage Housing Affordability Explorer")

# ---------- Sidebar Inputs ----------
st.sidebar.header("User Inputs")
housing_cost = st.sidebar.slider(
    "Select your monthly housing budget ($)", min_value=500, max_value=3000, value=1600, step=50
)
family_type_options = [
    "1 Adult", "1 Adult 1 Child", "1 Adult 2 Children", "1 Adult 3 Children",
    "2 Adults (1 Working)", "2 Adults (1 Working) 1 Child", "2 Adults (1 Working) 2 Children", "2 Adults (1 Working) 3 Children",
    "2 Adults (2 Working)", "2 Adults (2 Working) 1 Child", "2 Adults (2 Working) 2 Children", "2 Adults (2 Working) 3 Children"
]
family_type = st.sidebar.selectbox("Select your family type", family_type_options)

# ---------- Data Loaders ----------
@st.cache_data
def load_housing_gdf():
    gdf = gpd.read_file("fort_worth_grid_pieces.geojson")
    gdf = gdf[gdf["monthly_rent"] > 0].copy()
    gdf = gdf.to_crs(4326)
    return gdf

@st.cache_data
def get_city_boundary():
    city_gdf = gpd.read_file("fort_worth_city_boundary.geojson")  # Make sure filename is correct!
    city_gdf = city_gdf.to_crs(4326)
    return city_gdf

gdf = load_housing_gdf()
city_gdf = get_city_boundary()

# ---------- CLIP TRACTS STRICTLY TO CITY BOUNDARY ----------
tracts_in_city = gdf.copy()

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

# ---------- Color Coding: Green if affordable, Red if not ----------
def to_color(rent):
    if rent <= housing_cost:
        return [0, 185, 0, 120]  # green, semi-transparent
    else:
        return [212, 0, 0, 120]  # red, semi-transparent

tracts_in_city["fill_color"] = tracts_in_city["monthly_rent"].apply(to_color)

def extract_coords(geom):
    if geom is None:
        return []
    if geom.geom_type == 'Polygon':
        return [list(geom.exterior.coords)]
    elif geom.geom_type == 'MultiPolygon':
        return [list(p.exterior.coords) for p in geom.geoms]
    else:
        return []

tracts_in_city["coordinates"] = tracts_in_city["geometry"].apply(extract_coords)
tracts_in_city["lon"] = tracts_in_city.geometry.centroid.x
tracts_in_city["lat"] = tracts_in_city.geometry.centroid.y

# ---------- City Boundary: Explode and prepare for pydeck ----------
city_gdf_flat = city_gdf.explode(index_parts=False).reset_index(drop=True)

def get_polygon_coords(geom):
    if geom.geom_type == "Polygon":
        # Exterior + any interior holes
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
st.subheader("🗺️ All Census Grid Cells in Fort Worth\nGreen = Below Budget, Red = Above Budget")

tract_layer = pdk.Layer(
    "PolygonLayer",
    data=tracts_in_city,
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
    longitude=tracts_in_city["lon"].mean(),
    latitude=tracts_in_city["lat"].mean(),
    zoom=10,
    pitch=0,
)

tooltip = {
    "html": "<b>Monthly Rent: ${monthly_rent}</b>",
    "style": {"color": "white"}
}

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
with st.expander("📋 View All Grid Data (clipped to city)"):
    display_df = tracts_in_city.copy()
display_df = display_df.sort_values("monthly_rent", ascending=True).reset_index(drop=True)
display_df.index += 1
pretty_df = display_df[['monthly_rent', 'lat', 'lon']].rename(columns={
    'monthly_rent': 'Monthly Rent ($)',
    'lat': 'Latitude',
    'lon': 'Longitude'
})
st.dataframe(pretty_df, use_container_width=True)
csv = pretty_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="Download All Grids as CSV (Sorted by Rent)",
    data=csv,
    file_name='all_grid_cells_fort_worth_sorted.csv',
    mime='text/csv',
)

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
