# Utility functions for lightweight data cleaning agent

import re
import logging
import textwrap
import pandas as pd
from langchain_core.output_parsers import BaseOutputParser

logger = logging.getLogger(__name__)

DATA_CLEANING_PROMPT_TEMPLATE = """\
You are a Data Cleaning Agent. Create a {function_name}() function to clean the data.

Basic Cleaning Steps to implement:
1. Remove columns with more than 40% missing values
2. Impute missing values (mean for numeric, mode for categorical)
3. Remove duplicate rows
4. Remove outliers (numerical cols) outside of p05 and p95
5. Normalize string columns (strip whitespace, normalize casing)

User Instructions:
{user_instructions}

Dataset Summary:
{all_datasets_summary}

Return Python code in ```python``` format with a single function:

def {function_name}(data_raw):
    import pandas as pd
    import numpy as np
    # Your cleaning code here
    return data_cleaned

Important: Ensure fit_transform() outputs are flattened with .ravel() when assigning to DataFrame columns."""


class PythonOutputParser(BaseOutputParser):
    """Extract Python code from LLM responses."""
    
    def parse(self, text: str):
        """Extract code from ```python``` blocks or return text as-is."""
        python_code_match = re.search(r'```python(.*?)```', text, re.DOTALL)
        if python_code_match:
            return python_code_match.group(1).strip()
        return text


def get_dataframe_summary(df: pd.DataFrame, indent: int = 0) -> str:
    """
    Generate a simple summary of a DataFrame for the LLM.
    
    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to summarize.
    
    Returns
    -------
    str
        A text summary of the DataFrame.
    """
    missing_stats = (df.isna().sum() / len(df) * 100).sort_values(ascending=False)
    missing_summary = "\n  ".join([f"{col}: {val:.2f}%" for col, val in missing_stats.items()])

    column_types = "\n  ".join([f"{col}: {dtype}" for col, dtype in df.dtypes.items()])

    # For outlier detection, we need to calcualte Percentiles and IQR in numerical cols
    numerical_cols = df.select_dtypes(include="number").columns
    outlier_stats = {}
    for col in numerical_cols:
        Q1 = df[col].quantile(0.05)
        Q3 = df[col].quantile(0.95)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        outlier_stats[col] = f"Lower Bound: {lower_bound:.2f}, Upper Bound: {upper_bound:.2f}"
        
    outlier_summary = "\n  ".join([f"{col}: {val}" for col, val in outlier_stats.items()])

    # Sample unique values for string columns
    string_cols = df.select_dtypes(include="object").columns
    string_samples = {}
    for col in string_cols:
        unique_vals = df[col].dropna().unique()[:10]
        string_samples[col] = f"{list(unique_vals)}"
    string_summary = "\n  ".join([f"{col}: {val}" for col, val in string_samples.items()])

    summary = (
        "Column Data Types:\n"
        f"  {column_types}\n\n"
        "Missing Value Percentage:\n"
        f"  {missing_summary}\n\n"
        "Outlier Stats (numerical cols):\n"
        f"  {outlier_summary}\n\n"
        "String Column Samples:\n"
        f"  {string_summary}"
    )

    return textwrap.indent(summary, " " * indent)


def execute_agent_code(state, data_key, code_snippet_key, result_key, error_key, agent_function_name):
    """
    Execute the generated agent code on the data.
    
    Parameters
    ----------
    state : dict
        The current state containing data and code.
    data_key : str
        Key in state where the input data is stored.
    code_snippet_key : str
        Key in state where the generated code is stored.
    result_key : str
        Key to store the result in.
    error_key : str
        Key to store any error message in.
    agent_function_name : str
        Name of the function to execute from the generated code.
    
    Returns
    -------
    dict
        Dictionary with result and error keys.
    """
    logger.info("Executing agent code")
    
    data = state.get(data_key)
    agent_code = state.get(code_snippet_key)
    df = pd.DataFrame.from_dict(data)
    
    # Execute the LLM-generated code in isolated namespace
    # Note: exec() can be risky - only use with trusted LLM-generated code
    local_vars = {}
    global_vars = {}
    exec(agent_code, global_vars, local_vars)
    
    # Get the function from executed code
    agent_function = local_vars.get(agent_function_name)
    if not agent_function or not callable(agent_function):
        raise ValueError(f"Function '{agent_function_name}' not found in generated code.")
    
    # Run the function and handle errors
    agent_error = None
    result = None
    try:
        result = agent_function(df)
        if isinstance(result, pd.DataFrame):
            result = result.to_dict()
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        agent_error = f"An error occurred during data cleaning: {str(e)}"
    
    return {result_key: result, error_key: agent_error}


def fix_agent_code(state, code_snippet_key, error_key, llm, prompt_template, function_name, retry_count_key="retry_count"):
    """
    Fix errors in the generated agent code using the LLM.
    
    Parameters
    ----------
    state : dict
        The current state containing code and error information.
    code_snippet_key : str
        Key in state where the broken code is stored.
    error_key : str
        Key in state where the error message is stored.
    llm : LLM
        The language model to use for fixing the code.
    prompt_template : str
        Template for the fix prompt (should have {code_snippet}, {error}, {function_name} placeholders).
    function_name : str
        Name of the function being fixed.
    retry_count_key : str, optional
        Key in state for tracking retry count. Defaults to "retry_count".
    
    Returns
    -------
    dict
        Dictionary with updated code, cleared error, and incremented retry count.
    """
    logger.info("Fixing agent code")
    logger.debug(f"Retry count: {state.get(retry_count_key)}")
    
    code_snippet = state.get(code_snippet_key)
    error_message = state.get(error_key)
    
    # Create the fix prompt
    prompt = prompt_template.format(
        code_snippet=code_snippet,
        error=error_message,
        function_name=function_name,
    )
    
    # Get fixed code from LLM
    response = (llm | PythonOutputParser()).invoke(prompt)
    
    return {
        code_snippet_key: response,
        error_key: None,
        retry_count_key: state.get(retry_count_key) + 1
    }
