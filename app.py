import streamlit as st
import pandas as pd
import json
import io
from openpyxl import Workbook
from openpyxl.styles import PatternFill
import os

# Streamlit page configuration
st.set_page_config(layout="wide")  # Makes the layout wider
st.title("A-PAG QC LOG")

# File uploader
uploaded_file = st.file_uploader("Upload your CSV or Excel file", type=["csv", "xlsx"])

# Feedback file location
FEEDBACK_FILE = "feedback_data.json"

# Ensure the feedback file exists
if not os.path.exists(FEEDBACK_FILE):
    with open(FEEDBACK_FILE, "w") as f:
        json.dump({}, f)

# Load previous feedback data into session state
if "feedback" not in st.session_state:
    with open(FEEDBACK_FILE, "r") as f:
        st.session_state.feedback = json.load(f)

# Pagination setup
ROWS_PER_PAGE = 10
if "page" not in st.session_state:
    st.session_state.page = 0  # Start on page 0

# Store selected filters in session state
if "selected_action_item" not in st.session_state:
    st.session_state.selected_action_item = "All"
if "selected_zone" not in st.session_state:
    st.session_state.selected_zone = "All"
if "selected_ward" not in st.session_state:
    st.session_state.selected_ward = "All"

# Disapproval reasons
disapproval_reasons = [
    "Wrong Before Image/Poor Identification",
    "After Photo-Missing",
    "After Photo-Wrong/Blurry",
    "Incomplete Work/Work Not Started"
]

# If a file is uploaded
if uploaded_file:
    # Read the uploaded file
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Error reading the file: {e}")
        st.stop()

    # Ensure required columns exist
    required_cols = {"Project Id", "Raised Evidence", "Latest Evidence", "Zone", "Ward", "Action Item"}
    if not required_cols.issubset(df.columns):
        st.error(f"Your file is missing required columns: {required_cols - set(df.columns)}")
        st.stop()

    # Filters for Action Item, Zone, and Ward
    new_action_item = st.selectbox("Filter by Action Item", ["All"] + df["Action Item"].dropna().unique().tolist())
    new_zone = st.selectbox("Filter by Zone", ["All"] + df["Zone"].dropna().unique().tolist())
    new_ward = st.selectbox("Filter by Ward", ["All"] + df["Ward"].dropna().unique().tolist())

    # Reset to first page if any filter changes
    if (new_action_item != st.session_state.selected_action_item or
        new_zone != st.session_state.selected_zone or
        new_ward != st.session_state.selected_ward):
        st.session_state.page = 0  # Reset to first page

    # Update session state with new filters
    st.session_state.selected_action_item = new_action_item
    st.session_state.selected_zone = new_zone
    st.session_state.selected_ward = new_ward

    # Apply filters
    filtered_df = df.copy()
    if new_action_item != "All":
        filtered_df = filtered_df[filtered_df["Action Item"] == new_action_item]
    if new_zone != "All":
        filtered_df = filtered_df[filtered_df["Zone"] == new_zone]
    if new_ward != "All":
        filtered_df = filtered_df[filtered_df["Ward"] == new_ward]

    # Pagination logic AFTER filtering
    total_pages = max(1, len(filtered_df) // ROWS_PER_PAGE + (len(filtered_df) % ROWS_PER_PAGE > 0))
    start_idx = st.session_state.page * ROWS_PER_PAGE
    end_idx = start_idx + ROWS_PER_PAGE
    df_page = filtered_df.iloc[start_idx:end_idx]

    # Display error if page is empty after filtering
    if df_page.empty:
        st.session_state.page = 0  # Reset to first page
        df_page = filtered_df.iloc[:ROWS_PER_PAGE]  # Show first page of results

    # Live Review Summary
    status_counts = {
        "Status Yet to be Updated": 0,
        "Not Reviewed": 0,
        "Correct": 0,
        "Incorrect": 0
    }

    for pid in filtered_df["Project Id"]:
        current_status = st.session_state.feedback.get(str(pid), {}).get("Quality", "Status Yet to be Updated")
        status_counts[current_status] += 1

    # Display summary stats in the sidebar (Dynamically updated)
    with st.sidebar:
        st.subheader("Review Summary 📊")
        st.write(f" **Correct:** {status_counts['Correct']}")
        st.write(f"**Incorrect:** {status_counts['Incorrect']}")
        st.write(f" **Not Reviewed:** {status_counts['Not Reviewed']}")
        st.write(f" **Status Yet to be Updated:** {status_counts['Status Yet to be Updated']}")

        # Live Percentage calculation
        total_correct = status_counts['Correct']
        total_incorrect = status_counts['Incorrect']
        if total_correct + total_incorrect > 0:
            live_percentage = (total_correct * 100) / (total_correct + total_incorrect)
            st.write(f" **Live Percentage:** {live_percentage:.2f}%")

    # Loop through rows for review
    for _, row in df_page.iterrows():
        project_id = str(row["Project Id"])
        pre_image = row["Raised Evidence"]
        post_image = row["Latest Evidence"]

        st.subheader(f"Project ID: {project_id} | Action Item: {row.get('Action Item', 'N/A')}")
        st.text(f"Zone: {row['Zone']} | Ward: {row['Ward']}")
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

        # Review status
        saved_status = st.session_state.feedback.get(project_id, {}).get("Quality", "Status Yet to be Updated")

        status = st.radio(
            label=f"Status for Project ID {project_id}",
            options=["Status Yet to be Updated", "Not Reviewed", "Correct", "Incorrect"],
            key=f"status_{project_id}",
            index=["Status Yet to be Updated", "Not Reviewed", "Correct", "Incorrect"].index(saved_status)
        )

        saved_reason = st.session_state.feedback.get(project_id, {}).get("comment", "")

        reason = ""
        if status == "Incorrect":
            reason = st.selectbox(
                label=f"Reason for Disapproval (ID {project_id})",
                options=disapproval_reasons,
                key=f"reason_{project_id}",
                index=disapproval_reasons.index(saved_reason) if saved_reason in disapproval_reasons else 0
            )

        st.session_state.feedback[project_id] = {
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

    # Save feedback to file
    def save_feedback():
        with open(FEEDBACK_FILE, "w") as f:
            json.dump(st.session_state.feedback, f)

    if st.button("Save My Responses"):
        save_feedback()
        st.success("Responses Saved!")

    # Download Excel file
    def create_excel_download(df):
        buffer = io.BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.append(df.columns.tolist())

        for _, row in df.iterrows():
            ws.append(row.tolist())

        wb.save(buffer)
        buffer.seek(0)
        return buffer

    if st.button("Download Excel"):
        excel_buffer = create_excel_download(filtered_df)
        st.download_button("Download the Excel file", excel_buffer, "qc_log.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
