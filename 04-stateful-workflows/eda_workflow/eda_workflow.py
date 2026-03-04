import logging
import os
from typing import Optional, TypedDict

import pandas as pd
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)
WORKFLOW_NAME = "eda_workflow"
LOG_PATH = os.path.join(os.getcwd(), "logs/")
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def load_prompt(filename: str) -> str:
    """Load a prompt template from the prompts directory."""
    prompt_path = os.path.join(PROMPTS_DIR, filename)
    with open(prompt_path, "r") as f:
        return f.read()


class EDAWorkflow:
    """
    Exploratory Data Analysis workflow that performs consistent, first-pass analysis of datasets.
    
    Uses a fixed set of predefined analysis tools to produce structured, tabular outputs.
    Operates sequentially and deterministically through baseline EDA steps.
    
    Parameters
    ----------
    model : LLM, optional
        Language model for synthesizing findings.
    log : bool, default=False
        Whether to save analysis results to a file.
    log_path : str, optional
        Directory for log files.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer for saving workflow state.
    
    Attributes
    ----------
    response : dict or None
        Stores the full response after invoke_workflow() is called.
    """
    
    def __init__(
        self,
        model=None,
        log=False,
        log_path=None,
        checkpointer: Optional[object] = None
    ):
        self.model = model
        self.log = log
        self.log_path = log_path
        self.checkpointer = checkpointer
        self.response = None
        self._compiled_graph = make_eda_baseline_workflow(
            model=model,
            log=log,
            log_path=log_path,
            checkpointer=checkpointer
        )
    
    def invoke_workflow(self, filepath: str, **kwargs):
        """
        Run EDA analysis on the provided dataset.
        
        Parameters
        ----------
        filepath : str
            Path to the dataset file.
        **kwargs
            Additional arguments passed to the underlying graph invoke method.
        
        Returns
        -------
        None
            Results are stored in self.response and accessed via getter methods.
        """
        df = pd.read_csv(filepath)
        
        response = self._compiled_graph.invoke({
            "dataframe": df.to_dict(),
            "results": {},
            "observations": {},
            "current_step": "",
            "summary": "",
            "recommendations": [],
        }, **kwargs)
        
        self.response = response
        return None
    
    def get_summary(self):
        """Retrieves the analysis summary."""
        if self.response:
            return self.response.get("summary")
    
    def get_recommendations(self):
        """Retrieves the recommendations."""
        if self.response:
            return self.response.get("recommendations")
    
    def get_results(self):
        """Retrieves the full analysis results."""
        if self.response:
            return self.response.get("results")
    
    def get_observations(self):
        """Retrieves all observations from analysis steps."""
        if self.response:
            return self.response.get("observations")


def make_eda_baseline_workflow(
    model=None,
    log=False,
    log_path=None,
    checkpointer: Optional[object] = None
):
    """
    Factory function that creates a compiled LangGraph workflow for baseline EDA.
    
    Performs automated first-pass analysis with fixed analysis steps.
    
    Parameters
    ----------
    model : LLM, optional
        Language model for synthesizing findings.
    log : bool, default=False
        Whether to save analysis results to a file.
    log_path : str, optional
        Directory for log files.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer for saving workflow state.
    
    Returns
    -------
    CompiledStateGraph
        Compiled LangGraph workflow ready to process EDA requests.
    """
    if log:
        if log_path is None:
            log_path = LOG_PATH
        if not os.path.exists(log_path):
            os.makedirs(log_path)
    
    class EDAState(TypedDict):
        dataframe: dict
        results: dict
        observations: dict[str, list[str]]
        current_step: str
        summary: str
        recommendations: list[str]
    
    def profile_dataset_node(state: EDAState):
        """Generate dataset profile with basic statistics."""
        logger.info("Profiling dataset")
        df = pd.DataFrame.from_dict(state.get("dataframe"))
        results = state.get("results", {})
        
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        
        profile = {
            "shape": {"rows": len(df), "columns": len(df.columns)},
            "columns": df.columns.tolist(),
            "dtypes": df.dtypes.astype(str).to_dict(),
            "numeric_columns": numeric_cols,
            "categorical_columns": categorical_cols,
            "numeric_summary": (
                df[numeric_cols].describe().to_dict() if numeric_cols else {}
            ),
            "categorical_summary": {
                col: df[col].value_counts().head(10).to_dict()
                for col in categorical_cols
            },
        }
        
        results["profile_dataset"] = profile
        
        return {
            "current_step": "profile_dataset",
            "results": results,
        }
    
    def analyze_missingness_node(state: EDAState):
        """Analyze missing values in the dataset."""
        logger.info("Analyzing missingness")
        df = pd.DataFrame.from_dict(state.get("dataframe"))
        results = state.get("results", {})
        
        missing_count = df.isnull().sum().to_dict()
        missing_pct = (
            (df.isnull().sum() / len(df) * 100).round(2).to_dict()
        )
        
        high_missing = {col: pct for col, pct in missing_pct.items() if pct > 20}
        
        missingness = {
            "total_rows": len(df),
            "missing_count": missing_count,
            "missing_percentage": missing_pct,
            "high_missing_columns": high_missing,
            "complete_rows": int(df.dropna().shape[0]),
            "complete_rows_pct": (
                round(df.dropna().shape[0] / len(df) * 100, 2)
                if len(df) > 0 else 0
            ),
        }
        
        results["analyze_missingness"] = missingness
        
        return {
            "current_step": "analyze_missingness",
            "results": results,
        }
    
    def detect_duplicates_node(state: EDAState):
        """Detect exact and near-duplicate rows.

        Counts fully duplicate rows and checks for duplicates on likely ID
        columns (columns with 'id' in the name). Reports sample duplicates
        so the analyst can judge whether they are data entry errors or
        legitimate repeated records.
        """
        logger.info("Detecting duplicates")
        df = pd.DataFrame.from_dict(state.get("dataframe"))
        results = state.get("results", {})

        duplicates = {}

        # Exact duplicates (all columns)
        exact_dupes = df.duplicated(keep=False)
        duplicates["exact_duplicate_rows"] = int(exact_dupes.sum())
        duplicates["exact_duplicate_pct"] = (
            round(exact_dupes.sum() / len(df) * 100, 2) if len(df) > 0 else 0
        )

        # Duplicates on ID-like columns
        id_cols = [c for c in df.columns if "id" in c.lower()]
        id_duplicates = {}
        for col in id_cols:
            dupes = df[col].duplicated(keep=False)
            dupe_count = int(dupes.sum())
            if dupe_count > 0:
                id_duplicates[col] = {
                    "duplicate_rows": dupe_count,
                    "unique_values": int(df[col].nunique()),
                    "total_rows": len(df),
                    "sample_duplicated_values": (
                        df[dupes][col].value_counts().head(5).to_dict()
                    ),
                }
        duplicates["id_column_duplicates"] = id_duplicates

        results["detect_duplicates"] = duplicates

        return {
            "current_step": "detect_duplicates",
            "results": results,
        }

    def detect_outliers_node(state: EDAState):
        """Detect outliers in numeric columns using the IQR method.

        For each numeric column, computes Q1, Q3, and the IQR, then flags
        values below Q1 - 1.5*IQR or above Q3 + 1.5*IQR. Reports count,
        percentage, and the most extreme values.
        """
        logger.info("Detecting outliers")
        df = pd.DataFrame.from_dict(state.get("dataframe"))
        results = state.get("results", {})

        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

        outliers = {}
        for col in numeric_cols:
            series = df[col].dropna()
            if len(series) == 0:
                continue

            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr

            is_outlier = (series < lower_bound) | (series > upper_bound)
            outlier_count = int(is_outlier.sum())

            outliers[col] = {
                "q1": round(float(q1), 2),
                "q3": round(float(q3), 2),
                "iqr": round(float(iqr), 2),
                "lower_bound": round(float(lower_bound), 2),
                "upper_bound": round(float(upper_bound), 2),
                "outlier_count": outlier_count,
                "outlier_pct": round(outlier_count / len(series) * 100, 2),
                "min_value": round(float(series.min()), 2),
                "max_value": round(float(series.max()), 2),
            }
            if outlier_count > 0:
                outlier_vals = series[is_outlier]
                outliers[col]["extreme_low"] = sorted(outlier_vals.nsmallest(3).tolist())
                outliers[col]["extreme_high"] = sorted(outlier_vals.nlargest(3).tolist(), reverse=True)

        results["detect_outliers"] = outliers

        return {
            "current_step": "detect_outliers",
            "results": results,
        }

    def compute_aggregates_node(state: EDAState):
        """Compute group-by aggregates on categorical columns.

        For each categorical column, groups the data and computes count, mean,
        sum, min, and max of numeric columns. This reveals which categories
        drive volume and revenue, and highlights pricing or quantity anomalies.
        """
        logger.info("Computing aggregates")
        df = pd.DataFrame.from_dict(state.get("dataframe"))
        results = state.get("results", {})

        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()

        aggregates = {}
        for cat_col in categorical_cols:
            if df[cat_col].nunique() > 50:
                continue

            group = df.groupby(cat_col)[numeric_cols]
            agg = group.agg(["count", "mean", "sum"]).round(2)
            # Flatten multi-level column names
            agg.columns = ["_".join(col) for col in agg.columns]
            aggregates[cat_col] = {
                "group_counts": df[cat_col].value_counts().to_dict(),
                "aggregations": agg.to_dict(),
            }

        results["compute_aggregates"] = aggregates

        return {
            "current_step": "compute_aggregates",
            "results": results,
        }
    
    def analyze_relationships_node(state: EDAState):
        """Analyze relationships between numeric variables.

        Computes a correlation matrix for all numeric columns and flags strong
        correlations (|r| > 0.7). Also performs a data integrity check: if
        columns look like they satisfy quantity * price = total, it reports
        the percentage of rows where that relationship holds.
        """
        logger.info("Analyzing relationships")
        df = pd.DataFrame.from_dict(state.get("dataframe"))
        results = state.get("results", {})

        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

        relationships = {}

        # Correlation matrix
        if len(numeric_cols) >= 2:
            corr_matrix = df[numeric_cols].corr().round(3).to_dict()
            relationships["correlation_matrix"] = corr_matrix

            # Flag strong correlations (excluding self-correlations)
            strong = {}
            for col_a in numeric_cols:
                for col_b in numeric_cols:
                    if col_a >= col_b:
                        continue
                    r = df[numeric_cols].corr().loc[col_a, col_b]
                    if abs(r) > 0.7:
                        strong[f"{col_a} vs {col_b}"] = round(r, 3)
            relationships["strong_correlations"] = strong
        else:
            relationships["correlation_matrix"] = {}
            relationships["strong_correlations"] = {}

        # Data integrity check: look for quantity * price ≈ total patterns
        col_lower = {c: c for c in df.columns}
        qty_col = next((c for c in df.columns if "quant" in c.lower()), None)
        price_col = next((c for c in df.columns if "price" in c.lower()), None)
        total_col = next((c for c in df.columns if "total" in c.lower()), None)

        if qty_col and price_col and total_col:
            valid = df[[qty_col, price_col, total_col]].dropna()
            expected = valid[qty_col] * valid[price_col]
            matches = (expected - valid[total_col]).abs() < 0.01
            relationships["data_integrity"] = {
                "check": f"{qty_col} * {price_col} == {total_col}",
                "rows_checked": int(len(valid)),
                "rows_matching": int(matches.sum()),
                "match_pct": round(matches.sum() / len(valid) * 100, 2) if len(valid) > 0 else 0,
                "sample_mismatches": (
                    valid[~matches][[qty_col, price_col, total_col]]
                    .head(5)
                    .to_dict(orient="records")
                ),
            }

        results["analyze_relationships"] = relationships

        return {
            "current_step": "analyze_relationships",
            "results": results,
        }
    
    def analyze_temporal_node(state: EDAState):
        """Analyze temporal patterns in datetime columns.

        Auto-detects date/datetime columns, then computes time range, record
        counts by month, day-of-week distribution, and checks for gaps in
        daily coverage. Skips gracefully if no date columns are found.
        """
        logger.info("Analyzing temporal patterns")
        df = pd.DataFrame.from_dict(state.get("dataframe"))
        results = state.get("results", {})

        temporal = {}

        # Try to find and parse date columns
        date_cols = []
        for col in df.columns:
            if pd.api.types.is_string_dtype(df[col]):
                sample = df[col].dropna().head(100)
                try:
                    parsed = pd.to_datetime(sample, format="mixed")
                    if parsed.notna().sum() > len(sample) * 0.8:
                        date_cols.append(col)
                except (ValueError, TypeError):
                    continue
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                date_cols.append(col)

        for col in date_cols:
            dt = pd.to_datetime(df[col], format="mixed", errors="coerce")
            valid = dt.dropna()
            if len(valid) == 0:
                continue

            col_info = {
                "parsed_count": int(valid.count()),
                "unparseable_count": int(dt.isna().sum() - df[col].isna().sum()),
                "date_range": {
                    "min": str(valid.min().date()),
                    "max": str(valid.max().date()),
                    "span_days": int((valid.max() - valid.min()).days),
                },
            }

            # Monthly counts
            monthly = valid.dt.to_period("M").value_counts().sort_index()
            col_info["monthly_counts"] = {
                str(k): int(v) for k, v in monthly.head(12).items()
            }

            # Day-of-week distribution
            dow = valid.dt.day_name().value_counts()
            col_info["day_of_week"] = dow.to_dict()

            # Check for date gaps (days with zero records)
            date_range = pd.date_range(valid.min().date(), valid.max().date())
            days_with_data = valid.dt.date.nunique()
            col_info["coverage"] = {
                "total_days_in_range": len(date_range),
                "days_with_records": int(days_with_data),
                "coverage_pct": round(days_with_data / len(date_range) * 100, 2) if len(date_range) > 0 else 0,
            }

            temporal[col] = col_info

        if not temporal:
            temporal["note"] = "No datetime columns detected"

        results["analyze_temporal"] = temporal

        return {
            "current_step": "analyze_temporal",
            "results": results,
        }

    def analyze_distributions_node(state: EDAState):
        """Analyze statistical distributions of numeric columns.

        Computes skewness, kurtosis, and a normality indicator for each
        numeric column. Flags highly skewed columns that may need log or
        Box-Cox transforms before modeling.
        """
        logger.info("Analyzing distributions")
        df = pd.DataFrame.from_dict(state.get("dataframe"))
        results = state.get("results", {})

        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

        distributions = {}
        for col in numeric_cols:
            series = df[col].dropna()
            if len(series) < 3:
                continue

            skew = float(series.skew())
            kurt = float(series.kurtosis())

            # Classify skewness
            if abs(skew) < 0.5:
                skew_label = "approximately symmetric"
            elif abs(skew) < 1:
                skew_label = "moderately skewed"
            else:
                skew_label = "highly skewed"

            distributions[col] = {
                "skewness": round(skew, 3),
                "kurtosis": round(kurt, 3),
                "skew_direction": "right" if skew > 0 else "left" if skew < 0 else "none",
                "skew_label": skew_label,
                "needs_transform": abs(skew) > 1,
                "percentiles": {
                    "p5": round(float(series.quantile(0.05)), 2),
                    "p25": round(float(series.quantile(0.25)), 2),
                    "p50": round(float(series.quantile(0.50)), 2),
                    "p75": round(float(series.quantile(0.75)), 2),
                    "p95": round(float(series.quantile(0.95)), 2),
                },
            }

        results["analyze_distributions"] = distributions

        return {
            "current_step": "analyze_distributions",
            "results": results,
        }

    def extract_observations_node(state: EDAState):
        """Extract observations from the latest analysis results using LLM."""
        logger.info("Extracting observations")
        
        current_step = state.get("current_step", "")
        results = state.get("results", {})
        observations = state.get("observations", {})
        
        if model is None or not current_step or current_step not in results:
            return {"observations": observations}
        
        step_results = results.get(current_step, {})
        
        class ObservationOutput(BaseModel):
            observations: list[str] = Field(description="1-2 concise, actionable observations")
        
        observation_prompt = ChatPromptTemplate.from_messages([
            ("system", load_prompt("extract_observations_system.txt")),
            ("human", load_prompt("extract_observations_human.txt")),
        ])
        
        chain = observation_prompt | model.with_structured_output(ObservationOutput)
        response = chain.invoke({
            "step_name": current_step.replace("_", " ").title(),
            "results": str(step_results)
        })
        
        observations[current_step] = response.observations
        
        return {
            "observations": observations,
        }
    
    def synthesize_findings_node(state: EDAState):
        """Synthesize accumulated findings into summary and recommendations."""
        logger.info("Synthesizing findings")
        
        observations = state.get("observations", {})
        
        if model is None:
            return {
                "summary": "No LLM provided for synthesis",
                "recommendations": [],
            }
        
        class SynthesisOutput(BaseModel):
            summary: str = Field(description="A concise 2-3 sentence summary of key findings")
            recommendations: list[str] = Field(description="3-5 actionable recommendations")
        
        all_observations = []
        for step_name, step_obs in observations.items():
            all_observations.append(f"\n{step_name.replace('_', ' ').title()}:")
            for obs in step_obs:
                all_observations.append(f"  - {obs}")
        
        observations_text = "\n".join(all_observations)
        
        synthesis_prompt = ChatPromptTemplate.from_messages([
            ("system", load_prompt("synthesize_findings_system.txt")),
            ("human", load_prompt("synthesize_findings_human.txt")),
        ])
        
        chain = synthesis_prompt | model.with_structured_output(SynthesisOutput)
        response = chain.invoke({"observations": observations_text})
        
        return {
            "summary": response.summary,
            "recommendations": response.recommendations,
        }
    
    workflow = StateGraph(EDAState)

    # Analysis nodes (8 tools, each followed by observation extraction)
    analysis_steps = [
        ("profile_dataset", profile_dataset_node),
        ("analyze_missingness", analyze_missingness_node),
        ("detect_duplicates", detect_duplicates_node),
        ("detect_outliers", detect_outliers_node),
        ("compute_aggregates", compute_aggregates_node),
        ("analyze_relationships", analyze_relationships_node),
        ("analyze_temporal", analyze_temporal_node),
        ("analyze_distributions", analyze_distributions_node),
    ]

    for i, (name, node_fn) in enumerate(analysis_steps, start=1):
        workflow.add_node(name, node_fn)
        workflow.add_node(f"extract_observations_{i}", extract_observations_node)

    workflow.add_node("synthesize_findings", synthesize_findings_node)

    # Wire: tool → observations → next tool → ... → synthesize → END
    workflow.set_entry_point(analysis_steps[0][0])

    for i, (name, _) in enumerate(analysis_steps, start=1):
        workflow.add_edge(name, f"extract_observations_{i}")
        if i < len(analysis_steps):
            workflow.add_edge(f"extract_observations_{i}", analysis_steps[i][0])
        else:
            workflow.add_edge(f"extract_observations_{i}", "synthesize_findings")

    workflow.add_edge("synthesize_findings", END)
    
    app = workflow.compile(checkpointer=checkpointer, name=WORKFLOW_NAME)
    
    return app
