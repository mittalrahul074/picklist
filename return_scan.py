import database
from returns.evanik_auth import evanik_login
from returns.evanik_client import EvanikClient
from returns.return_processor import process_awb_list
import streamlit as st
from datetime import date, timedelta

def render_return_scan_panel():
    st.header("📦 Return Scan System")

    email = "mittal.distributors.online@gmail.com"
    password = "123456"

    uploaded_file = st.file_uploader("Upload AWB CSV", type=["csv"])

    #start_date is today - 30 days in 2025-11-29 and end_date is today -1 day and return_date is today all in yyyy-mm-dd format
    start_date = date.today() - timedelta(days=30)
    end_date = date.today() - timedelta(days=1)
    return_date = date.today()

    if st.button("🚀 Process Returns"):
        if not all([email, password, uploaded_file]):
            st.error("All fields required")
            return

        try:
            session = evanik_login(email, password)
            client = EvanikClient(session)
        except Exception as e:
            st.error(str(e))
            return

        awbs = [
            line.decode().strip()
            for line in uploaded_file.readlines()[1:]
            if line.strip()
        ]

        old_awbs = database.pending_awbs_list()

        with st.spinner("Processing returns..."):
            results = process_awb_list(
                awbs,
                client,
                start_date.isoformat(),
                end_date.isoformat(),
                return_date.isoformat(),
                st.session_state.user_role
            )

            old_results = process_awb_list(
                old_awbs,
                client,
                start_date.isoformat(),
                end_date.isoformat(),
                return_date.isoformat(),
                st.session_state.user_role
            )

        st.success("Done")
        st.dataframe(results)
        st.markdown("### Reprocessing Pending AWBs")
        st.dataframe(old_results)
