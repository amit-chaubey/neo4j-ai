import streamlit as st
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the project root directory to Python path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from app.services.icd_service import ICDService

# Load environment variables
load_dotenv()

# Initialize ICD Service
icd_service = ICDService(
    uri=os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
    user=os.getenv("NEO4J_USER", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD")
)

def main():
    st.title("ICD-10 Code Explorer")
    
    # Search section
    st.header("Search ICD Codes")
    search_query = st.text_input("Enter search term (e.g., tuberculosis, heart disease)")
    
    if search_query:
        with st.spinner('Searching...'):
            results = icd_service.search_by_description(search_query)
            
            if results:
                st.subheader(f"Found {len(results)} results:")
                for result in results:
                    with st.expander(f"{result['code']} - {result['short_desc']}"):
                        st.write(f"Category Code: {result['category_code']}")
                        st.write(f"Long Description: {result['long_desc']}")
                        if result.get('category_name'):
                            st.write(f"Category: {result['category_name']}")
            else:
                st.info("No results found")
    
    # Category browser section
    st.header("Browse by Category")
    category_code = st.text_input("Enter category code (e.g., A15)")
    
    if category_code:
        with st.spinner('Loading category...'):
            category_results = icd_service.get_category_codes(category_code)
            
            if category_results:
                st.subheader(f"Codes in category {category_code}:")
                for result in category_results:
                    st.write(f"{result['code']} - {result['short_desc']}")
            else:
                st.info("No codes found in this category")

if __name__ == "__main__":
    main()
