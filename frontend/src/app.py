"""
Enhanced IMDb Scraper - Frontend Application
"""
import streamlit as st
import os
from services.api_client import APIClient
from pages import dashboard, search, movies, settings

# Page configuration
st.set_page_config(
    page_title="Enhanced IMDb Scraper",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize API client
@st.cache_resource
def get_api_client():
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    return APIClient(backend_url)

api_client = get_api_client()

# Sidebar navigation
with st.sidebar:
    st.title("🎬 IMDb Scraper")
    
    page = st.selectbox(
        "Navigate to:",
        ["Dashboard", "Search Movies", "Movie Library", "Settings"]
    )

# Route to pages
if page == "Dashboard":
    dashboard.show(api_client)
elif page == "Search Movies":
    search.show(api_client)
elif page == "Movie Library":
    movies.show(api_client)
elif page == "Settings":
    settings.show(api_client)
