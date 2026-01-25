import streamlit as st
from .admin_services import (
    process_upload,
    get_filtered_orders,
    get_order_stats,
)

from utils import export_orders_to_excel
from db.orders import load_orders

def render_admin_panel():
    st.header("Admin Panel – Order Upload")
    load_orders()
    # File upload section
    st.subheader("Upload Order File")
    uploaded_file = st.file_uploader("Choose a file", type=["xlsx", "xls", "csv"])
    # Platform selection
    platform = st.radio(
        "Select Platform",
        ["flipkart", "meesho"],
        index=0,
        format_func=lambda x: x.capitalize(),
        horizontal=True
    )

    if uploaded_file is not None:
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Process File"):
                success, message = process_upload(uploaded_file, platform)
                if success:
                    st.success(f"Successfully added {message} new orders from {platform.capitalize()}")
                else:
                    st.error(f"Error: {message}")

        with col2:
            if st.button("Export Orders to Excel"):
                excel_data = export_orders_to_excel()
                if excel_data:
                    st.download_button(
                        label="Download Orders Excel",
                        data=excel_data,
                        file_name="orders_export.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.info("No orders available to export.")

    # Display current order statistics
    st.markdown("---")
    st.subheader("Order Statistics")

    stats = get_order_stats()

    col1, col2, col3 = st.columns(3)
    col1.metric("New", stats.get("new", 0))
    col2.metric("Picked", stats.get("picked", 0))
    col3.metric("Validated", stats.get("validated", 0))

    # ===============================
    # Orders Table
    # ===============================
    st.markdown("---")
    st.subheader("All Orders")

    party_filter = st.selectbox(
        "Filter by Party",
        ["Both", "Kangan", "RS"]
    )

    filtered_df = get_filtered_orders(party_filter)

    if filtered_df.empty:
        st.info("No orders found")
    else:
        st.dataframe(filtered_df, use_container_width=True)
