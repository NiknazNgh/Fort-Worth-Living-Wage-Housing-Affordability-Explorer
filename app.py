import streamlit as st   
import geopandas as gpd
import pandas as pd
import pydeck as pdk
from living_wage import living_wage_table  # your living wage table function or variable
from breakdown import living_wage_breakdown  # your living wage breakdown function

st.set_page_config(page_title="Fort Worth Living Wage Explorer", layout="wide")
st.title("🏠 Fort Worth Living Wage Housing Affordability Explorer")

# ---------- Sidebar Inputs ----------
st.sidebar.header("User Inputs")

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
    "4+ Bedrooms": "median_rent_4br"
}
bedroom_label = st.sidebar.selectbox("Number of Bedrooms", list(bedroom_options.keys()))
bedroom_col = bedroom_options[bedroom_label]


st.sidebar.markdown("###  Monthly Cost Inputs")

housing_input = st.sidebar.number_input("Housing ($/mo)", min_value=500, max_value=5000, value=1450)
food_input = st.sidebar.number_input("Food ($/mo)", min_value=100, max_value=2000, value=350)
childcare_input = st.sidebar.number_input("Child Care ($/mo)", min_value=0, max_value=3000, value=800)
transport_input = st.sidebar.number_input("Transportation ($/mo)", min_value=50, max_value=1500, value=400)
health_input = st.sidebar.number_input("Health Care ($/mo)", min_value=50, max_value=1500, value=160)
other_input = st.sidebar.number_input("Other Necessities ($/mo)", min_value=50, max_value=1500, value=300)
civic_input = st.sidebar.number_input("Civic Engagement ($/mo)", min_value=0, max_value=1000, value=170)
internet_input = st.sidebar.number_input("Internet ($/mo)", min_value=0, max_value=500, value=90)
taxes_input = st.sidebar.number_input("Taxes ($/mo)", min_value=0, max_value=3000, value=500)

# Calculate total living wage based on custom inputs
total_living_wage_custom = (
    housing_input + food_input + childcare_input +
    transport_input + health_input + other_input +
    civic_input + internet_input + taxes_input
)


# ---------- Data Loaders ----------
@st.cache_data
def load_housing_gdf():
    gdf = gpd.read_file("fort_worth_grid_pieces_bedrooms.geojson")
    gdf = gdf.to_crs(4326)
    return gdf

@st.cache_data
def get_city_boundary():
    city_gdf = gpd.read_file("fort_worth_city_boundary.geojson")  
    city_gdf = city_gdf.to_crs(4326)
    return city_gdf

gdf = load_housing_gdf()
city_gdf = get_city_boundary()
gdf = gdf[gdf[bedroom_col] > 0].copy()

# ---------- Living Wage Data ----------

percentile = 0.40  # fixed 40th percentile (can be changed or made dynamic)

breakdown_df = living_wage_breakdown(q=percentile)
breakdown_df.columns = [col.strip().lower().replace('#', '').strip() for col in breakdown_df.columns]
filtered = breakdown_df.loc[[family_type]] if family_type in breakdown_df.index else None

if filtered is not None and not filtered.empty:
    housing_cost_pct = filtered["housing"].values[0]
    total_living_wage_pct = filtered["total"].values[0]
else:
    housing_cost_pct = housing_input  # fallback
    total_living_wage_pct = total_living_wage_custom
    st.warning("No matching data found for this family type in dataset, using custom inputs.")

# ---------- Color Coding ----------

def to_color(rent):
    if rent <= housing_input:
        return [0, 185, 0, 120]  # Green if rent <= custom housing budget
    else:
        return [212, 0, 0, 120]  # Red otherwise

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
    "html": f"<b>{bedroom_label} Rent: ${{{bedroom_col}}}</b>",
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

# ---------- Display Selected Info ----------

st.markdown(f"### 👨‍👩‍👧 Selected Family Type: `{family_type}`")
st.success(f"**Custom Required Living Wage:** **${total_living_wage_custom:,.0f}/month**")


# ---------- User-Driven Cost Inputs & Data Table ----------

custom_breakdown = pd.DataFrame([{
    "housing": housing_input,
    "transport": transport_input,
    "food": food_input,
    "health": health_input,
    "civic": civic_input,
    "other": other_input,
    "childcare": childcare_input,
    "internet": internet_input,
    "tax": taxes_input,
    "total": total_living_wage_custom
}], index=[family_type])

st.markdown("#### Living Wage Breakdown (Custom Inputs)")
st.dataframe(custom_breakdown)
st.markdown("#### Living Wage Breakdown (Reference Data)")
if filtered is not None and not filtered.empty:
    st.dataframe(filtered)
else:
    st.info("No reference data available for this family type.")


# ---------- Show Reference Living Wage Table ----------

percentile = st.sidebar.slider(
    "Select Living Wage Percentile (Reference Table)", 
    min_value=0.1, max_value=0.9, value=0.40, step=0.01, format="%.2f"
)

ref_table = living_wage_table(q=percentile)
if family_type in ref_table.index:
    st.markdown(f"#### Living Wage Table (Selected Family Type)")
    st.dataframe(ref_table.loc[[family_type]])
else:
    st.info("No reference data available for this family type in the table.")
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
