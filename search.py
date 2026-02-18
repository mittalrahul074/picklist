import streamlit as st
import pandas as pd
import utils
import database
from datetime import datetime, timedelta

def _render_orders_elegant(df: pd.DataFrame, orders_ref):
    """
    Apple-style elegant hierarchical order display

    Structure:
        Date
            SKU
                Order ID
                    Editable details
    """

    if df.empty:
        st.info("No results")
        return

    # Ensure datetime format
    if "updated_at" in df.columns:
        df["updated_at"] = pd.to_datetime(df["updated_at"], errors="coerce")

    # Create date column
    df["date"] = df["updated_at"].dt.date

    # Sort newest first
    df = df.sort_values(
        by=["updated_at"],
        ascending=False
    )
    # Group by date
    for date, date_group in df.groupby("date"):

        st.markdown(f"## 📅 {date}")

        # Group by SKU
        for sku, sku_group in date_group.groupby("sku"):

            with st.expander(f"📦 SKU: {sku} ({len(sku_group)})", expanded=False):

                #show option to view imges via get_product_image_url
                img_url = database.get_product_image_url(sku)
                for idx, row in sku_group.iterrows():

                    order_id = row["order_id"]

                    with st.container():

                        colA, colB, colC,colD = st.columns([2,2,2,2])

                        colA.write(f"**Order:** {row['order_id']}")
                        colB.write(f"Status: `{row['status']}`")
                        colC.write(f"Picked: `{row['picked_by']}`")
                        colD.write(f"Validated: `{row['validated_by']}`")

                        print(f"DEBUG: SKU {sku} has image URL: {img_url}")
                        if img_url:
                            #view image in new tab
                            st.markdown(f"[View Image]({img_url})", unsafe_allow_html=True)
                        if st.session_state.user_type in [4, 5]:
                            _render_order_edit_form(row, orders_ref, idx)

def _render_order_edit_form(order_data, orders_ref, idx):

    order_id = str(order_data.get("order_id", ""))

    if not order_id:
        st.error("Invalid order_id")
        return

    key_prefix = f"order_{order_id}_{idx}"

    with st.expander("Edit Order Details", expanded=False):

        col1, col2 = st.columns(2)
        
        status_options = ["new", "picked", "validated", "cancelled", "wrong"]

        current_status = order_data.get("status", "new")

        try:
            status_index = status_options.index(current_status)
        except ValueError:
            status_index = 0

        with col1:
            new_status = st.selectbox(
                "Status",
                options=["new", "picked", "validated", "cancelled", "wrong"],
                index=["new", "picked", "validated", "cancelled", "wrong"].index(order_data.get("status", "new")),
                key=f"status_{order_id}_{idx}"
            )

        with col2:
            new_picked_by = st.text_input("Picked By", value=order_data.get("picked_by", ""),key=f"{key_prefix}_picked_by")
            new_validated_by = st.text_input("Validated By", value=order_data.get("validated_by", ""),key=f"validated_{order_id}_{idx}")

        if st.button(f"Save Changes for {order_id}", type="primary",key=f"{key_prefix}_save"):
            try:
                # udate order in firestore rules if status is changed from picked or validated then picked_by or validated_by are set empty, and if status is picked or validated  then picked_by or validated_by are set to current user, if status is new or cancelled or wrong then picked_by and validated_by are set empty and if status is picked or validated then picked_by or validated_by are set to current user
                
                # If status is changed from picked or validated, clear picked_by and validated_by
                if current_status in ["picked", "validated"] and new_status not in ["picked", "validated"]:
                    new_picked_by = ""
                    new_validated_by = ""
                # If status is changed to picked or validated, set picked_by or validated_by to current user
                elif new_status in ["picked", "validated"] and current_status not in ["picked",
                    "validated"]:
                    current_user = st.session_state.user_role
                    if new_status == "picked":
                        new_picked_by = current_user
                        new_validated_by = ""
                    elif new_status == "validated":
                        new_picked_by = current_user
                        new_validated_by = current_user

                orders_ref.document(order_id).update({
                    "status": new_status,
                    "picked_by": new_picked_by,
                    "validated_by": new_validated_by,
                    "updated_at": datetime.utcnow()
                })
                st.success("✅ Order updated successfully")
            except Exception as e:
                st.error(f"❌ Error updating order: {e}")

def render_search_panel():
    prefill = st.session_state.get("search_prefill", {})
    st.header("🔍 Search Orders")

    db = database.get_db_connection()
    orders_ref = db.collection("orders")
    users_ref = db.collection("users")
    product_ref = db.collection("products")
    st.subheader("Search Criteria")

    # ---------- LOAD USERS ONCE ----------
    user_docs = users_ref.stream()
    user_list = sorted([doc.id for doc in user_docs])
    user_list.insert(0, "Any")

    #product list
    product_list = set()

    for doc in product_ref.stream():
        sku = doc.to_dict().get("sku")
        if sku:
            product_list.add(sku)

    product_list = sorted(product_list)
    product_list.insert(0, "Any")

    # ---------- UI INPUTS ----------
    col1, col2 = st.columns(2)

    with col1:
        order_id_input = st.text_input("Order ID (exact match)",value=prefill.get("order_id", ""),key="search_order_id")
        sku_input = st.selectbox("Product SKU", options=product_list,index=product_list.index(prefill.get("sku")) if prefill.get("sku") in product_list else 0,key="search_sku")

    with col2:
        status_input = st.selectbox(
            "Status",
            options=["Any", "new", "picked", "validated", "cancelled", "wrong"],
            index=["Any", "new", "picked", "validated", "cancelled", "wrong"].index(prefill.get("status")) if prefill.get("status") in ["Any", "new", "picked", "validated", "cancelled", "wrong"] else 0, key="search_status"
        )
        picked_by_input = st.selectbox("Picked By", user_list)
        validated_by_input = st.selectbox("Validated By", user_list)

    st.markdown("### 📅 Updated Date Filter")

    col3, col4 = st.columns(2)

    with col3:
        updated_from = st.date_input("Updated From (optional)", value = prefill.get("updated_from", None), key="search_updated_from")

    with col4:
        updated_to = st.date_input("Updated To (optional)", value=prefill.get("updated_to", None), key="search_updated_to")

    st.markdown("---")

    if prefill:
        run_search = True
    else:
        run_search = st.button("🔎 Search", type="primary")

    # ---------- SEARCH ACTION ----------
    if run_search:
        # CASE 1: Direct Order ID lookup (fastest)
        if order_id_input:
            doc = orders_ref.document(order_id_input).get()
            if doc.exists:
                st.success("✅ Order found")
                df = pd.DataFrame([doc.to_dict()])
                st.dataframe(df, use_container_width=True)
            else:
                st.warning("❌ No order found with this Order ID")

            if "search_prefill" in st.session_state:
                del st.session_state["search_prefill"]

            return

        # CASE 2: Build Firestore query
        query = orders_ref

        #dont allow search without sku or ordrer id
        # if sku_input == "Any" and not order_id_input:
        #     st.warning("❌ Please provide at least a Product SKU or Order ID to search")
        #     return

        if sku_input != "Any":
            query = query.where("sku", "==", sku_input.upper())

        if status_input != "Any":
            query = query.where("status", "==", status_input)

        if picked_by_input != "Any":
            query = query.where("picked_by", "==", picked_by_input)

        if validated_by_input != "Any":
            query = query.where("validated_by", "==", validated_by_input)

        if updated_from:
            start_ts = datetime.combine(updated_from, datetime.min.time())
            query = query.where("updated_at", ">=", start_ts)

        if updated_to:
            end_ts = datetime.combine(updated_to, datetime.max.time())
            query = query.where("updated_at", "<=", end_ts)

        # ---------- EXECUTE QUERY ----------
        docs = list(query.stream())

        if not docs:
            st.warning("❌ No matching orders found")
            if "search_prefill" in st.session_state:
                del st.session_state["search_prefill"]
            return

        results = [{"order_id": doc.id} | doc.to_dict() for doc in docs]

        st.success(f"✅ Found {len(results)} matching orders")
        df = pd.DataFrame(results)
        _render_orders_elegant(df, orders_ref)
        if "search_prefill" in st.session_state:
            del st.session_state["search_prefill"]
