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
from app.services.llm_service import MedicalCodingAssistant

# Load environment variables
load_dotenv()

# Initialize services
icd_service = ICDService(
    uri=os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
    user=os.getenv("NEO4J_USER", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD")
)

# Initialize LLM service
medical_assistant = MedicalCodingAssistant(icd_service)

# Initialize session state for chat history
if 'messages' not in st.session_state:
    st.session_state.messages = []

def main():
    st.title("ICD-10 Code Explorer")

    # Sidebar for search and browse functionality
    with st.sidebar:
        st.header("Search & Browse")
        
        # Search section
        st.subheader("Search ICD Codes")
        search_query = st.text_input("Enter search term (e.g., pneumonia)")
        
        if search_query:
            with st.spinner('Searching...'):
                results = icd_service.search_by_description(search_query)
                
                if results:
                    st.success(f"Found {len(results)} results")
                    for result in results:
                        with st.expander(f"{result['code']} - {result['short_desc']}"):
                            st.write(f"Category Code: {result['category_code']}")
                            st.write(f"Long Description: {result['long_desc']}")
                else:
                    st.info("No results found")
        
        # Category browser section
        st.subheader("Browse by Category")
        category_code = st.text_input("Enter category code (e.g., J12)")
        
        if category_code:
            with st.spinner('Loading category...'):
                category_results = icd_service.get_category_codes(category_code)
                
                if category_results:
                    for result in category_results:
                        st.write(f"{result['code']} - {result['short_desc']}")
                else:
                    st.info("No codes found in this category")

    # Main area for chat interface
    st.header("Medical Coding Assistant")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Describe the medical condition or ask about ICD codes..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate assistant response
        with st.chat_message("assistant"):
            with st.spinner("Analyzing medical description..."):
                # Use LLM service to process query
                response_data = medical_assistant.process_query(prompt)
                
                # Debug information
                st.write("Debug Info:")
                st.json({
                    "source": response_data["source"],
                    "num_codes": len(response_data["suggested_codes"]),
                    "has_explanation": bool(response_data.get("explanation"))
                })
                
                # Format the response
                response = f"💡 {response_data['explanation']}\n\n"
                
                if response_data['suggested_codes']:
                    response += "**Relevant ICD-10 Codes:**\n\n"
                    for code in response_data['suggested_codes']:
                        response += f"- **{code['code']}**: {code['short_desc']}\n"
                        with st.expander(f"Details for {code['code']}"):
                            st.write(f"Category Code: {code['category_code']}")
                            st.write(f"Long Description: {code['long_desc']}")
                
                st.markdown(response)
                
                # Add assistant response to chat history
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": response
                })

if __name__ == "__main__":
    main()
