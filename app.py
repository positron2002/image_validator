import streamlit as st
import pandas as pd
import io
from openpyxl import Workbook
from openpyxl.styles import PatternFill

st.title("Image Approval App")

# File uploader
uploaded_file = st.file_uploader("Upload your CSV or Excel file", type=["csv", "xlsx"])

# Pagination setup
ROWS_PER_PAGE = 10
if "page" not in st.session_state:
    st.session_state.page = 0  # Start on page 0

# Feedback dictionary to store user responses
row_feedback = {}

# Disapproval reasons
disapproval_reasons = [
    "Wrong Before Image/Poor Identification",
    "After Photo-Missing",
    "After Photo-Wrong/Blurry",
    "Incomplete Work/Work Not Started"
]

if uploaded_file:
    # Read the uploaded file
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Error reading the file: {e}")
        st.stop()

    # Ensure required columns exist
    required_cols = {"Project Id", "Raised Evidence", "Latest Evidence", "Zone", "Ward"}
    if not required_cols.issubset(df.columns):
        st.error(f"Your file is missing required columns: {required_cols - set(df.columns)}")
        st.stop()

    # Pagination logic
    total_pages = len(df) // ROWS_PER_PAGE + (len(df) % ROWS_PER_PAGE > 0)
    start_idx = st.session_state.page * ROWS_PER_PAGE
    end_idx = start_idx + ROWS_PER_PAGE
    df_page = df.iloc[start_idx:end_idx]

    # Loop through rows for review
    for i, row in df_page.iterrows():
        project_id = row["Project Id"]
        pre_image = row["Raised Evidence"]
        post_image = row["Latest Evidence"]
        zone = row["Zone"]
        ward = row["Ward"]

        st.subheader(f"Project ID: {project_id} | Zone: {zone} | Ward: {ward}")
        st.text(f"Action Item: {row.get('Action Item', 'N/A')}")
        st.text(f"Raised Comment: {row.get('Raised Comment', 'N/A')}")

        # Display images
        col1, col2 = st.columns(2)
        with col1:
            if pd.notna(pre_image):
                st.image(pre_image, caption="Raised Evidence (Pre)", use_container_width=True)
            else:
                st.warning("No Pre Image Provided")

        with col2:
            if pd.notna(post_image):
                st.image(post_image, caption="Latest Evidence (Post)", use_container_width=True)
            else:
                st.warning("No Post Image Provided")

        # User input for approval
        status = st.radio(
            label=f"Status for Project ID {project_id}",
            options=["Not Reviewed", "Correct", "Incorrect"],
            key=f"status_{project_id}"
        )

        reason = ""
        if status == "Incorrect":
            reason = st.selectbox(
                label=f"Reason for Disapproval (ID {project_id})",
                options=disapproval_reasons,
                key=f"reason_{project_id}"
            )

        row_feedback[project_id] = {
            "Quality": status,
            "comment": reason if status == "Incorrect" else ""
        }

    # Pagination controls
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.session_state.page > 0:
            if st.button("Previous Page"):
                st.session_state.page -= 1
                st.rerun()
    with col3:
        if st.session_state.page < total_pages - 1:
            if st.button("Next Page"):
                st.session_state.page += 1
                st.rerun()

    # Download updated file
    if st.button("Download Updated File"):
        desired_cols = [
            "Project Id", "Action Item", "Landmark*", "Organisation", "Zone", "Ward",
            "City", "State*", "Raised On", "Raised Comment", "Raised Evidence",
            "Raised Location", "Latest Comment", "Latest Evidence", "Latest Location"
        ]
        existing_cols = [col for col in desired_cols if col in df.columns]
        df_filtered = df[existing_cols].copy()

        df_filtered["Quality"] = df_filtered["Project Id"].apply(
            lambda pid: row_feedback.get(pid, {}).get("Quality", "Not Reviewed")
        )
        df_filtered["Comments"] = df_filtered["Project Id"].apply(
            lambda pid: row_feedback.get(pid, {}).get("comment", "")
        )

        # Create an Excel file with conditional formatting
        with io.BytesIO() as excel_buffer:
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                df_filtered.to_excel(writer, index=False, sheet_name="Approval Data")
                workbook = writer.book
                sheet = workbook["Approval Data"]

                # Define cell formats
                green_fill = PatternFill(start_color="00FF00", end_color="00FF00", fill_type="solid")
                red_fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")

                # Apply the color to the 'Quality' column only
                quality_col_idx = df_filtered.columns.get_loc("Quality") + 1  # openpyxl uses 1-based index
                for row_num, row in df_filtered.iterrows():
                    status = row["Quality"]
                    cell = sheet.cell(row=row_num + 2, column=quality_col_idx)  # +2 to account for header

                    if status == "Correct":
                        cell.fill = green_fill
                    elif status == "Incorrect":
                        cell.fill = red_fill

            # Save the Excel file to memory
            excel_buffer.seek(0)
            st.download_button(
                label="Download Updated Excel",
                data=excel_buffer,
                file_name="updated_approval_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
