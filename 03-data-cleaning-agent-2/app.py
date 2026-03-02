"""Streamlit interface for the Data Cleaning Agent."""

import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from data_cleaning_agent import LightweightDataCleaningAgent

load_dotenv()

st.title("Data Cleaning Agent")

# --- Upload ---
uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

if uploaded_file:
    df_raw = pd.read_csv(uploaded_file)

    # --- Raw Data Preview ---
    st.subheader("Raw Data Preview")
    st.write(f"Shape: {df_raw.shape[0]} rows x {df_raw.shape[1]} columns")
    st.dataframe(df_raw.head(10))

    # --- Data Quality Metrics ---
    st.subheader("Data Quality")
    col1, col2, col3 = st.columns(3)
    col1.metric("Rows", df_raw.shape[0])
    col2.metric("Duplicates", int(df_raw.duplicated().sum()))
    total_missing = df_raw.isna().sum().sum()
    total_cells = df_raw.shape[0] * df_raw.shape[1]
    col3.metric("Missing Values", f"{total_missing} ({total_missing / total_cells * 100:.1f}%)")

    # Missing values bar chart
    missing = df_raw.isna().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    if not missing.empty:
        st.bar_chart(missing, horizontal=True)

    # --- Custom Instructions ---
    user_instructions = st.text_area(
        "Custom instructions (optional)",
        placeholder="e.g. 'Drop the city column entirely', 'Convert salary to thousands'",
    )

    # --- Clean ---
    if st.button("Clean Data", type="primary"):
        with st.spinner("Generating and executing cleaning code..."):
            try:
                llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
                agent = LightweightDataCleaningAgent(model=llm, log=True)
                agent.invoke_agent(
                    data_raw=df_raw,
                    user_instructions=user_instructions if user_instructions else None,
                )

                # Check for errors
                error = agent.response.get("data_cleaner_error") if agent.response else None
                if error:
                    st.error(f"Agent failed after retries: {error}")
                    # Still show the code so user can debug
                    code = agent.get_data_cleaner_function()
                    if code:
                        with st.expander("Generated Code (failed)"):
                            st.code(code, language="python")
                else:
                    df_cleaned = agent.get_data_cleaned().reset_index(drop=True)
                    st.success("Done!")

                    # --- Generated Code ---
                    with st.expander("Generated Cleaning Code"):
                        st.code(agent.get_data_cleaner_function(), language="python")

                    # --- Before / After Comparison ---
                    st.subheader("Before / After")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**Before**")
                        st.metric("Rows", df_raw.shape[0])
                        st.metric("Columns", df_raw.shape[1])
                        st.metric("Missing", int(df_raw.isna().sum().sum()))
                        st.metric("Duplicates", int(df_raw.duplicated().sum()))
                    with c2:
                        st.markdown("**After**")
                        st.metric("Rows", df_cleaned.shape[0], delta=int(df_cleaned.shape[0] - df_raw.shape[0]))
                        st.metric("Columns", df_cleaned.shape[1], delta=int(df_cleaned.shape[1] - df_raw.shape[1]))
                        st.metric("Missing", int(df_cleaned.isna().sum().sum()), delta=int(df_cleaned.isna().sum().sum() - df_raw.isna().sum().sum()))
                        st.metric("Duplicates", int(df_cleaned.duplicated().sum()), delta=int(df_cleaned.duplicated().sum() - df_raw.duplicated().sum()))

                    # --- Cleaned Data ---
                    st.subheader("Cleaned Data")
                    st.write(f"Final size: **{df_cleaned.shape[0]} rows x {df_cleaned.shape[1]} columns**")
                    st.dataframe(df_cleaned.head(10))

                    # --- Download ---
                    csv = df_cleaned.to_csv(index=False)
                    st.download_button(
                        "Download Cleaned Data",
                        data=csv,
                        file_name="cleaned_data.csv",
                        mime="text/csv",
                    )

            except Exception as e:
                st.error(f"Something went wrong: {e}")
