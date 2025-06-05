import streamlit as st 
import geopandas as gpd
import pandas as pd
import pydeck as pdk
from breakdown import living_wage_breakdown

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
    gdf["tract_id"] = gdf.index.astype(str)  # tract_id as string
    return gdf

@st.cache_data
def get_city_boundary():
    city_gdf = gpd.read_file("fort_worth_city_boundary.geojson")
    city_gdf = city_gdf.to_crs(4326)
    return city_gdf

gdf = load_housing_gdf()
city_gdf = get_city_boundary()

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

# ---------- Geometry: Add coordinates for pydeck ----------
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

# ---------- City Boundary: Explode and prepare for pydeck ----------
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

# ---------- Data Table ----------
st.subheader("🗺️ All Census Grid Cells in Fort Worth\nGreen = Below Budget, Red = Above Budget")

table_df = gdf[["tract_id", "monthly_rent", "lat", "lon"]].copy()
table_df_display = table_df.rename(columns={
    'tract_id': 'Tract ID',
    'monthly_rent': 'Monthly Rent ($)',
    'lat': 'Latitude',
    'lon': 'Longitude'
})

with st.expander("📋 View All Grid Data (clipped to city)"):
    st.dataframe(table_df_display, use_container_width=True)

# ---------- Select tract for highlight ----------
tract_ids = table_df_display['Tract ID'].tolist()
tract_labels = [
    f"{tid}: Rent ${row['Monthly Rent ($)']} ({row['Latitude']:.4f}, {row['Longitude']:.4f})"
    for tid, row in zip(tract_ids, table_df_display.to_dict(orient='records'))
]
tract_label_map = dict(zip(tract_labels, tract_ids))
selected_tract_label = st.selectbox(
    "Select a tract to highlight on the map:",
    options=["None"] + tract_labels,
    index=0
)
selected_tract_id = tract_label_map[selected_tract_label] if selected_tract_label != "None" else None

# ---------- Color coding: Green/Red/Blue for map polygons ----------
def to_color(row):
    if selected_tract_id is not None and str(row['tract_id']) == str(selected_tract_id):
        return [0, 0, 255, 220]  # blue, more opaque for highlight
    elif row['monthly_rent'] <= housing_cost:
        return [0, 185, 0, 120]  # green
    else:
        return [212, 0, 0, 120]  # red

gdf["fill_color"] = gdf.apply(to_color, axis=1)

# ---------- MAP ----------
tract_layer = pdk.Layer(
    "PolygonLayer",
    data=gdf,
    get_polygon="coordinates",
    get_fill_color="fill_color",
    pickable=True,
    auto_highlight=True,
    stroked=True,
    get_line_color=[60, 60, 60, 90],
    line_width_min_pixels=1,
)

city_boundary_layer = pdk.Layer(
    "PolygonLayer",
    data=city_gdf_flat,
    get_polygon="coordinates",
    get_fill_color=[0, 0, 0, 30],
    stroked=True,
    get_line_color=[0, 0, 0, 200],
    line_width_min_pixels=1,
)

city_outline_layer = pdk.Layer(
    "LineLayer",
    data=city_lines_df,
    get_path="path",
    get_color=[0, 0, 0, 255],
    get_width=6,
)

initial_view = pdk.ViewState(
    longitude=gdf["lon"].mean(),
    latitude=gdf["lat"].mean(),
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
        <div>Affordable (Green) &larr; &rarr; Not Affordable (Red), <span style="color: #0000FF; font-weight:bold;">Blue = Selected</span></div>
    </div>
    """, unsafe_allow_html=True
)

# ---------- Download ----------
csv = table_df_display.to_csv(index=False).encode('utf-8')
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
