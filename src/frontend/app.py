import streamlit as st

st.set_page_config(page_title="GridKey BESS Optimizer", layout="wide")

st.title("GridKey BESS Optimizer + WatsonX Agent")

st.sidebar.header("Configuration")
location = st.sidebar.text_input("Location", "Munich")

col1, col2 = st.columns(2)

with col1:
    st.header("Dashboard")
    st.info("Optimization results will appear here.")

with col2:
    st.header("Agent Chat")
    user_input = st.text_input("Ask the agent:")
    if user_input:
        st.write(f"Agent: Echoing '{user_input}'")
