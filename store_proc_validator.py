import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="Stored Proc Output Validator", layout="wide")
st.title("🧪 Stored Procedure Output Validator")

# Upload two Excel files
st.sidebar.header("Upload Excel Files")
file1 = st.sidebar.file_uploader("📤 Existing Logic Output", type=["xlsx"])
file2 = st.sidebar.file_uploader("📤 Optimized Logic Output", type=["xlsx"])

# Comparison settings
st.sidebar.header("Comparison Settings")
ignore_case = st.sidebar.checkbox("Ignore text case differences", value=True)
ignore_whitespace = st.sidebar.checkbox("Ignore whitespace differences", value=True)
float_precision = st.sidebar.number_input("Float comparison precision (decimal places)", min_value=1, max_value=10, value=5)
treat_nulls_equal = st.sidebar.checkbox("Treat all null values as equal (None, NaN, empty string)", value=True)

def safe_equals(val1, val2):
    """Compare two values with settings applied"""
    if treat_nulls_equal:
        if pd.isna(val1) and pd.isna(val2):
            return True
        if pd.isna(val1) or pd.isna(val2):
            return False

    str1 = str(val1) if val1 is not None else ""
    str2 = str(val2) if val2 is not None else ""

    if ignore_whitespace:
        str1 = str1.strip()
        str2 = str2.strip()

    if ignore_case:
        str1 = str1.lower()
        str2 = str2.lower()

    try:
        num1 = float(str1) if str1 else float('nan')
        num2 = float(str2) if str2 else float('nan')
        if not pd.isna(num1) and not pd.isna(num2):
            return round(num1, float_precision) == round(num2, float_precision)
    except (ValueError, TypeError):
        pass

    return str1 == str2

if file1 and file2:
    df_old = pd.read_excel(file1)
    df_new = pd.read_excel(file2)

    st.subheader("📊 Data Overview")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Rows in File 1", df_old.shape[0])
    with col2:
        st.metric("Rows in File 2", df_new.shape[0])
    with col3:
        st.metric("Columns", df_old.shape[1])

    old_cols = set(df_old.columns)
    new_cols = set(df_new.columns)

    if old_cols != new_cols:
        st.warning("⚠️ Column mismatch detected:")
        only_in_old = old_cols - new_cols
        only_in_new = new_cols - old_cols

        if only_in_old:
            st.info(f"Columns only in file 1: {', '.join(only_in_old)}")
        if only_in_new:
            st.info(f"Columns only in file 2: {', '.join(only_in_new)}")

    with st.expander("Preview Input Data"):
        st.write("✅ Existing Logic Output (First 5 rows)")
        st.dataframe(df_old.head())
        st.write("✅ Optimized Logic Output (First 5 rows)")
        st.dataframe(df_new.head())

    sort_cols = st.multiselect("🔑 Select Key Column(s) to Sort By", options=df_old.columns.tolist(), default=[df_old.columns[0]] if not df_old.empty else [])

    if sort_cols:
        df_old_sorted = df_old.sort_values(by=sort_cols).reset_index(drop=True)
        df_new_sorted = df_new.sort_values(by=sort_cols).reset_index(drop=True)

        progress_bar = st.progress(0)
        st.text("Comparing data...")

        if len(df_old_sorted) != len(df_new_sorted):
            st.warning(f"⚠️ Row count mismatch: File 1 has {len(df_old_sorted)} rows, File 2 has {len(df_new_sorted)} rows")

        common_cols = list(set(df_old_sorted.columns) & set(df_new_sorted.columns))

        mismatch_report = []
        mismatched_columns = set()

        for idx in range(min(len(df_old_sorted), len(df_new_sorted))):
            if idx % 10 == 0:
                progress_percent = idx / min(len(df_old_sorted), len(df_new_sorted))
                progress_bar.progress(progress_percent)

            row_has_mismatch = False
            row_data = {"Row": idx + 1}
            for key_col in sort_cols:
                row_data[f"Key_{key_col}"] = df_old_sorted.loc[idx, key_col]

            for col in common_cols:
                old_val = df_old_sorted.loc[idx, col]
                new_val = df_new_sorted.loc[idx, col]
                if not safe_equals(old_val, new_val):
                    row_has_mismatch = True
                    mismatched_columns.add(col)
                    row_data[f"Old_{col}"] = old_val
                    row_data[f"New_{col}"] = new_val

            if row_has_mismatch:
                mismatch_report.append(row_data)

        progress_bar.progress(1.0)
        st.empty()

        mismatch_df = pd.DataFrame(mismatch_report) if mismatch_report else pd.DataFrame()

        if mismatch_df.empty:
            st.success("✅ No mismatches found. The outputs are identical after sorting (with current comparison settings).")
        else:
            st.warning(f"⚠️ Mismatches found in columns: {', '.join(sorted(mismatched_columns))}")
            display_cols = ["Row"] + [f"Key_{col}" for col in sort_cols]

            tab1, tab2 = st.tabs(["Summary View", "Detailed View"])

            with tab1:
                mismatch_counts = {col: sum(1 for row in mismatch_report if f"Old_{col}" in row) for col in mismatched_columns}

                summary_df = pd.DataFrame({
                    "Column": list(mismatch_counts.keys()),
                    "Mismatch Count": list(mismatch_counts.values()),
                    "% of Rows": [count / min(len(df_old_sorted), len(df_new_sorted)) * 100 for count in mismatch_counts.values()]
                })

                st.dataframe(summary_df.sort_values("Mismatch Count", ascending=False))
                st.subheader("Sample differences by column")
                for col in sorted(mismatched_columns):
                    with st.expander(f"Column: {col}"):
                        sample_rows = [row for row in mismatch_report if f"Old_{col}" in row][:5]
                        if sample_rows:
                            sample_df = pd.DataFrame([{
                                "Row": row["Row"],
                                "Old Value": row[f"Old_{col}"],
                                "New Value": row[f"New_{col}"]
                            } for row in sample_rows])
                            st.dataframe(sample_df)

            with tab2:
                cols_to_show = st.multiselect("Select columns to compare", options=sorted(mismatched_columns), default=list(sorted(mismatched_columns))[:3] if mismatched_columns else [])
                if cols_to_show:
                    for col in cols_to_show:
                        display_cols.extend([f"Old_{col}", f"New_{col}"])
                    valid_cols = [col for col in display_cols if col in mismatch_df.columns]
                    st.dataframe(mismatch_df[valid_cols])
                else:
                    st.info("Select columns to view comparison details")

            output = BytesIO()
            mismatch_df.to_excel(output, index=False)
            st.download_button(
                label="📥 Download Mismatch Report",
                data=output.getvalue(),
                file_name="mismatch_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.info("👉 Please select at least one sorting key column.")
else:
    st.info("⬅️ Please upload both Excel files to start comparison.")
