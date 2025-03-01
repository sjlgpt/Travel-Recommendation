import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import re

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

if not GOOGLE_API_KEY:
    st.error("Please set up your GOOGLE_API_KEY in the .env file")
    st.stop()

# Configure Gemini
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = None
    
    # Try different model versions in order of preference
    model_versions = ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro']
    
    for version in model_versions:
        try:
            model = genai.GenerativeModel(version)
            # Test if model works
            test_response = model.generate_content('Test')
            # st.success(f"Successfully connected using {version} model")
            break
        except Exception:
            continue
            
    if not model:
        raise Exception("No available Gemini models found")
        
except Exception as e:
    st.error(f"Error configuring Gemini: {str(e)}")
    st.stop()

# Initialize session state
if 'previous_places' not in st.session_state:
    st.session_state.previous_places = []
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []  # Will now store dicts with 'query' and 'response' keys

def validate_response(response_text):
    try:
        # Clean any potential markdown or extra whitespace
        response_text = re.sub(r'^.*\n', '', response_text)
        response_text = re.sub(r'\n$', '', response_text)
        response_text = response_text.strip()
        data = json.loads(response_text)
        required_keys = ["name", "description", "cost", "timing", "best_time", "tips"]
        
        if "places" not in data:
            return None
        if not isinstance(data["places"], list) or len(data["places"]) == 0:
            return None
        for place in data["places"]:
            if not all(key in place and place[key] for key in required_keys):
                return None
        return data
    except Exception as e:
        print(f"Validation error: {str(e)}")
        print(f"Response text: {response_text}")
        return None

def get_places_recommendations(query):
    try:
        prompt = f"""Based on this query: '{query}'
Please provide exactly 5 popular tourist places that match the query criteria.
Format your response as valid JSON with the following structure:
{{
    "places": [
        {{
            "name": "Tourist Place Name",
            "description": "2-3 sentence description",
            "cost": "Approximate cost in INR",
            "timing": "Opening and closing hours",
            "best_time": "Best season or time to visit",
            "tips": "One important travel tip"
        }}
    ]
}}"""

        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean the response text
        if 'json' in response_text:
            response_text = re.sub(r'^json\s*|\s*```$', '', response_text)
        
        data = validate_response(response_text)
        if not data:
            raise ValueError("Invalid response format from API")
        return data
            
    except Exception as e:
        st.error(f"Error generating recommendations: {str(e)}")
        return None

def extract_price(cost_string):
    """Extract numerical price from cost string"""
    matches = re.findall(r'(?:Rs\.?|INR)\s*(\d+(?:,\d+)*(?:\.\d+)?)', cost_string)
    if matches:
        # Remove commas and convert to float
        return float(matches[0].replace(',', ''))
    return float('inf')  # Return infinity if no price found

def filter_places(places, num):
    return places[:min(num, len(places))]

def extract_number_from_query(query):
    numbers = re.findall(r'\d+', query)
    return int(numbers[0]) if numbers else 5

def sort_places_by_price(places, ascending=True):
    """Sort places by their price"""
    return sorted(places, key=lambda x: extract_price(x['cost']), reverse=not ascending)

def process_follow_up_query(query, previous_places):
    """Process follow-up queries for filtering and sorting"""
    if "sort" in query.lower() and "price" in query.lower():
        ascending = "increasing" in query.lower() or "low to high" in query.lower()
        return {"places": sort_places_by_price(previous_places, ascending)}
    elif "out of these" in query.lower():
        num_places = extract_number_from_query(query)
        return {"places": previous_places[:num_places]}
    return None

# Streamlit UI
st.title("🌍 Travel Recommendations")
st.write("Ask about places to visit in any location with your budget!")

# Add example queries
with st.expander("📝 Example Queries"):
    st.write("- suggest me some good visiting places in hyderabad under 5000")
    st.write("- show me tourist spots in bangalore within 3000 rupees")
    st.write("- ok suggest me 3 out of these most popular places")

user_query = st.text_input("🔍 Enter your query:")

if user_query:
    # Create new chat entry
    chat_entry = {
        "query": user_query,
        "response": None
    }
    
    with st.spinner("Generating recommendations..."):
        # Handle follow-up queries
        if any(x in user_query.lower() for x in ["out of these", "sort", "price"]):
            if not st.session_state.previous_places:
                st.warning("Please make an initial query first!")
            else:
                places_data = process_follow_up_query(user_query, st.session_state.previous_places)
                if places_data:
                    chat_entry["response"] = places_data
                    if "sort" in user_query.lower():
                        st.success("Sorted places by price!")
                    else:
                        st.success(f"Showing top {len(places_data['places'])} places from previous recommendations")
        else:
            places_data = get_places_recommendations(user_query)
            if places_data:
                chat_entry["response"] = places_data
                st.session_state.previous_places = places_data["places"]
                st.success("Found the following recommendations!")

        # Display results
        if places_data and places_data["places"]:
            for idx, place in enumerate(places_data["places"], 1):
                with st.expander(f"#{idx} {place['name']} 🏛"):
                    st.markdown(f"*Description:* {place['description']}")
                    st.markdown(f"💰 Cost:** {place['cost']}")
                    st.markdown(f"⏰ Timing:** {place['timing']}")
                    st.markdown(f"🗓 Best Time to Visit:** {place['best_time']}")
                    st.markdown(f"💡 Travel Tips:** {place['tips']}")
    
    # Add the chat entry to history after getting response
    st.session_state.chat_history.append(chat_entry)

# Replace the old chat history display with this new version
with st.sidebar:
    st.subheader("💬 Chat History")
    for entry in reversed(st.session_state.chat_history):  # Show newest first
        with st.expander(f"🗣 {entry['query']}", expanded=False):
            if entry['response'] and entry['response'].get('places'):
                for idx, place in enumerate(entry['response']['places'], 1):
                    st.markdown(f"""
                    *{idx}. {place['name']}*  
                    💰 {place['cost']}
                    """)
            else:
                st.info("No response generated")
