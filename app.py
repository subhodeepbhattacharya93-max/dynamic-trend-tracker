import streamlit as st
import pandas as pd
from pytrends.request import TrendReq
from GoogleNews import GoogleNews
import datetime
import time
import random
from fake_useragent import UserAgent

# --- Configuration & UI Setup ---
st.set_page_config(page_title="Dynamic Trend Tracker", layout="wide", page_icon="📈")
st.title("📈 Dynamic Trend Tracker")
st.markdown("Enter a keyword and select a date range to see Google Search trends and related news in India.")



# --- Helper Functions ---
@st.cache_data(ttl=3600)  # Cache results for 1 hour to prevent API bans
def fetch_trends_data(keyword, start_date, end_date, geo_code='IN', demo_mode=False):
    """Fetches data from PyTrends with backoff and fake headers."""
    if demo_mode:
        try:
            # Load the local CSVs we generated earlier for CSR
            regional_df = pd.read_csv('csr_regional_interest.csv')
            # Rename the hardcoded 'CSR' column to whatever the user inputted so it charts correctly
            if 'CSR' in regional_df.columns:
                regional_df = regional_df.rename(columns={'CSR': keyword})
            regional_df.index += 1
            top_queries = pd.read_csv('csr_top_queries.csv')
            top_queries.index += 1
            rising_queries = pd.read_csv('csr_rising_queries.csv')
            rising_queries.index += 1
            time.sleep(1) # Fake loading
            return regional_df, top_queries, rising_queries, None
        except Exception as e:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), f"Demo Mode failed to load local files: {e}"
    # Format date for pytrends: 'YYYY-MM-DD YYYY-MM-DD'
    timeframe = f"{start_date.strftime('%Y-%m-%d')} {end_date.strftime('%Y-%m-%d')}"
    
    ua = UserAgent()
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Generate a new fake user agent for each attempt
            headers = {'User-Agent': ua.random, 'Accept-Language': 'en-US,en;q=0.5'}
            
            # Initializing PyTrends (tz=330 is IST)
            pytrends = TrendReq(hl='en-US', tz=330, retries=2, backoff_factor=1, requests_args={'headers': headers})
            pytrends.build_payload([keyword], cat=0, timeframe=timeframe, geo=geo_code, gprop='')
            
            # Fetch City-Wise Interest for India
            regional_df = pytrends.interest_by_region(resolution='CITY', inc_low_vol=True, inc_geo_code=False)
            if not regional_df.empty:
                regional_df = regional_df.sort_values(by=keyword, ascending=False).reset_index()
                regional_df.index += 1 # 1-based indexing for display
            
            # Fetch Related Queries
            queries_dict = pytrends.related_queries()
            top_queries = pd.DataFrame()
            rising_queries = pd.DataFrame()
            
            if queries_dict and keyword in queries_dict:
                top_q = queries_dict[keyword].get('top')
                rising_q = queries_dict[keyword].get('rising')
                if top_q is not None and not top_q.empty:
                    top_queries = top_q
                    top_queries.index += 1
                if rising_q is not None and not rising_q.empty:
                    rising_queries = rising_q
                    rising_queries.index += 1

            return regional_df, top_queries, rising_queries, None
            
        except Exception as e:
            if "429" in str(e) or "Too Many Requests" in str(e):
                if attempt < max_retries - 1:
                    wait_time = random.uniform(2, 5) * (attempt + 1)
                    time.sleep(wait_time)
                else:
                     return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "Google Trends rate limit reached (Error 429). Please try again in an hour."
            else:
                return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), str(e)

    return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "Max retries exceeded."

@st.cache_data(ttl=3600)
def fetch_news(keyword):
    """Fetches top 10 recent news articles using GoogleNews."""
    try:
        googlenews = GoogleNews(lang='en', region='IN', period='7d')
        googlenews.search(keyword)
        results = googlenews.results(sort=True)
        
        articles = []
        # Get up to 10 articles
        for i, item in enumerate(results[:10]):
            articles.append({
                "Title": item.get('title', 'No Title'),
                "Date": item.get('date', 'Unknown Date'),
                "Source": item.get('media', 'Unknown Source'),
                "Link": item.get('link', '#')
            })
        return articles, None
    except Exception as e:
        return [], str(e)


# --- Input Section ---
with st.container(border=True):
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        keyword_input = st.text_input("Enter Keyword:", value="CSR", placeholder="e.g. Cricket, AI, CSR...")
        demo_mode = st.toggle("Enable Demo Mode (Use Local Data)", value=False, help="Enable this if Google Trends is blocking your IP with Error 429. It will load local sample data.")

    with col2:
        start_input = st.date_input("Start Date:", value=datetime.date.today() - datetime.timedelta(days=7))
    
    with col3:
        end_input = st.date_input("End Date:", value=datetime.date.today())
        
    with col4:
        st.write("") # Spacing
        st.write("") # Spacing
        search_button = st.button("🔍 Search Trends", use_container_width=True, type="primary")

# --- Validation ---
if start_input > end_input:
    st.error("Start Date must be before End Date.")
    st.stop()


# --- Main Logic & Display ---
if search_button:
    with st.spinner(f"Analyzing trends for '{keyword_input}'..."):
        
        # Fetch Data
        reg_df, top_df, rise_df, py_error = fetch_trends_data(keyword_input, start_input, end_input, 'IN', demo_mode)
        news_articles, news_error = fetch_news(keyword_input)
        
        if py_error:
            st.error(f"Error fetching Google Trends Data: {py_error}\n*(Note: Google may temporarily block requests if too many are sent. Try again in an hour if you see a 429 error).*")
            st.stop()
            
        st.success("Analysis Complete!")
        
        # Layout Results
        left_col, right_col = st.columns([1, 1])
        
        # --- Left Column ---
        with left_col:
            st.subheader("📍 Top Indian Cities Searching")
            if not reg_df.empty and reg_df[keyword_input].sum() > 0:
                # Filter out 0 interest to make it cleaner
                clean_reg_df = reg_df[reg_df[keyword_input] > 0]
                st.dataframe(clean_reg_df, use_container_width=True, hide_index=False)
            else:
                st.info("No significant regional data available for this keyword/timeframe.")
                
            st.markdown("---")
            
            st.subheader("📰 Top 10 Trending Articles")
            if news_error:
                st.error(f"Failed to fetch news: {news_error}")
            elif news_articles:
                for idx, article in enumerate(news_articles):
                    st.markdown(f"**{idx+1}. [{article['Title']}]({article['Link']})**")
                    st.caption(f"📰 {article['Source']} • 📅 {article['Date']}")
                    st.write("") # Small gap
            else:
                st.info("No recent trending articles found.")


        # --- Right Column ---
        with right_col:
            st.subheader("🔍 Top Related Queries")
            if not top_df.empty:
                st.dataframe(top_df, use_container_width=True)
            else:
                st.info("No top related queries found.")
                
            st.markdown("---")
            
            st.subheader("🚀 Rising Queries")
            if not rise_df.empty:
                st.dataframe(rise_df, use_container_width=True)
            else:
                st.info("No rising trends found.")
