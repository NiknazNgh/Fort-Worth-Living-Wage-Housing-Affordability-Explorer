import streamlit as st
import geopandas as gpd
import pandas as pd
import pydeck as pdk

st.set_page_config(page_title="Fort Worth Tracts With Rent", layout="wide")
st.title("🗺️ Fort Worth Census Tracts With Rent")

# Load GeoJSON
gdf = gpd.read_file("fort_worth_tracts_with_rent.geojson")

st.subheader("Data Preview")
st.dataframe(gdf.drop(columns='geometry').head())

# If rent column exists, use it for shading
if 'rent' in gdf.columns:
    # Convert geometry to centroid for plotting with pydeck
    gdf['lon'] = gdf.geometry.centroid.x
    gdf['lat'] = gdf.geometry.centroid.y

    # Create a layer for polygons
    polygon_layer = pdk.Layer(
        "GeoJsonLayer",
        data=gdf,
        get_fill_color="[255, 255 - min(200, rent), 100, 120]" if 'rent' in gdf.columns else "[200, 200, 200, 120]",
        pickable=True,
        opacity=0.5,
        stroked=True,
        filled=True,
        get_line_color=[80, 80, 80],
        line_width_min_pixels=1,
    )

    # Set initial view state
    view_state = pdk.ViewState(
        longitude=gdf['lon'].mean(),
        latitude=gdf['lat'].mean(),
        zoom=10,
        pitch=0,
    )

    st.pydeck_chart(pdk.Deck(
        map_style='mapbox://styles/mapbox/light-v9',
        layers=[polygon_layer],
        initial_view_state=view_state,
        tooltip={"text": "Rent: {rent}"}
    ))
else:
    st.write("No 'rent' column found in the data. Showing boundaries only.")
    st.map(gdf)

