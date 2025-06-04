import streamlit as st
import geopandas as gpd
import pandas as pd
import pydeck as pdk
from breakdown import living_wage_breakdown
import matplotlib
import numpy as np
import json
import os
import zipfile
import requests


# --- Config ---
st.set_page_config(page_title="Fort Worth Living Wage Explorer", layout="wide")
st.title("🏠 Fort Worth Living Wage Housing Affordability Explorer")

# --- Sidebar Inputs ---
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

# --- Load Data ---
@st.cache_data
def load_data():
    gdf = gpd.read_file("fort_worth_tracts_with_rent.geojson")
    gdf = gdf[gdf["monthly_rent"] > 0].copy()
    return gdf

gdf = load_data()

breakdown_df = living_wage_breakdown(q=0.40)
breakdown_df.columns = [col.strip().lower().replace('#', '').strip() for col in breakdown_df.columns]
filtered = breakdown_df.loc[[family_type]] if family_type in breakdown_df.index else pd.DataFrame()

eligible_areas = gdf[gdf["monthly_rent"] <= housing_cost].copy()
eligible_areas = eligible_areas.sort_values("monthly_rent").reset_index(drop=True)
eligible_areas["Rank"] = eligible_areas.index + 1

st.markdown(f"### 👨‍👩‍👧 Selected Family Type: `{family_type}`")

if not filtered.empty:
    total_living_wage = filtered["total"].values[0]
    st.success(f"**Required Living Wage** (with taxes, 40th percentile costs): **${total_living_wage:,.0f}/month**")
else:
    st.warning("No matching data found for this family type.")

# --- Map Display ---
st.subheader("🗺️ Areas Where You Can Afford to Live")
if eligible_areas.empty:
    st.error("❌ No areas match your selected budget.")
else:
    # Ensure CRS is correct
    try:
        eligible_areas = eligible_areas.to_crs(4326)
    except Exception as e:
        st.error(f"CRS conversion failed: {e}")

    # Handle polygons and multipolygons safely
    def extract_coords(geom):
        if geom is None:
            return []
        if geom.geom_type == 'Polygon':
            return [list(geom.exterior.coords)]
        elif geom.geom_type == 'MultiPolygon':
            return [list(p.exterior.coords) for p in geom.geoms]
        else:
            return []

    eligible_areas["coordinates"] = eligible_areas["geometry"].apply(extract_coords)
    eligible_areas["lon"] = eligible_areas.geometry.centroid.x
    eligible_areas["lat"] = eligible_areas.geometry.centroid.y

    # >>>>>> COLOR SECTION: Green-Yellow-Red <<<<<<
    rent_min = eligible_areas["monthly_rent"].min()
    rent_max = eligible_areas["monthly_rent"].max()
    norm_rent = (eligible_areas["monthly_rent"] - rent_min) / (rent_max - rent_min + 1e-6)
    cmap = matplotlib.cm.get_cmap('RdYlGn_r')
    def to_rgb255(x):
        r, g, b, _ = [int(255 * v) for v in cmap(x)]
        return [r, g, b, 120]  # More opaque

    eligible_areas["fill_color"] = norm_rent.apply(to_rgb255)

    layer = pdk.Layer(
        "PolygonLayer",
        data=eligible_areas,
        get_polygon="coordinates",
        get_fill_color="fill_color",
        pickable=True,
        auto_highlight=True,
        stroked=True,
        get_line_color=[0, 0, 0, 80],
        line_width_min_pixels=1,
    )

    initial_view = pdk.ViewState(
        longitude=eligible_areas["lon"].mean(),
        latitude=eligible_areas["lat"].mean(),
        zoom=10,
        pitch=0,
    )

    tooltip = {
        "html": "<b>Rank #{Rank}</b><br/>Monthly Rent: ${monthly_rent}<br/>",
        "style": {"color": "white"}
    }

    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=initial_view,
            tooltip=tooltip,
            map_style="mapbox://styles/mapbox/light-v9"
        )
    )

    # Color legend
    st.markdown(
        """
        <div style="display: flex; align-items: center;">
            <div style="background: linear-gradient(to right, #00b900, #ffe000, #d40000); width: 160px; height: 18px; margin-right: 10px;"></div>
            <div>Affordable (Green) &larr; &rarr; Expensive (Red)</div>
        </div>
        """, unsafe_allow_html=True
    )

    with st.expander("📋 View Eligible Area Data"):
        display_df = eligible_areas.reset_index(drop=True)
        display_df.index += 1
        pretty_df = display_df[['Rank', 'monthly_rent', 'lat', 'lon']].rename(columns={
            'Rank': 'Rank',
            'monthly_rent': 'Monthly Rent ($)',
            'lat': 'Latitude',
            'lon': 'Longitude'
        })
        st.dataframe(pretty_df, use_container_width=True)

        csv = pretty_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Eligible Areas as CSV",
            data=csv,
            file_name='eligible_areas_fort_worth.csv',
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
