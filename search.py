import streamlit as st
import pandas as pd
import utils
import database

def render_search_panel():
    st.header("🔍 Search Orders")

    db = database.get_db_connection()
    orders_ref = db.collection("orders")
    users_ref = db.collection("users")
    st.subheader("Search Criteria")

    # ---------- LOAD USERS ONCE ----------
    user_docs = users_ref.stream()
    user_list = sorted([doc.id for doc in user_docs])
    user_list.insert(0, "Any")

    # ---------- UI INPUTS ----------
    col1, col2 = st.columns(2)

    with col1:
        order_id_input = st.text_input("Order ID (exact match)")
        sku_input = st.text_input("SKU")

    with col2:
        status_input = st.selectbox(
            "Status",
            options=["Any", "new", "picked", "validated", "cancelled", "wrong"]
        )
        picked_by_input = st.selectbox("Picked By", user_list)
        validated_by_input = st.selectbox("Validated By", user_list)

    st.markdown("---")

    # ---------- SEARCH ACTION ----------
    if st.button("🔎 Search", type="primary"):
        # CASE 1: Direct Order ID lookup (fastest)
        if order_id_input:
            doc = orders_ref.document(order_id_input).get()
            if doc.exists:
                st.success("✅ Order found")
                df = pd.DataFrame([doc.to_dict()])
                st.dataframe(df, use_container_width=True)
            else:
                st.warning("❌ No order found with this Order ID")
            return

        # CASE 2: Build Firestore query
        query = orders_ref

        if sku_input:
            query = query.where("sku", "==", sku_input)

        if status_input != "Any":
            query = query.where("status", "==", status_input)

        if picked_by_input:
            query = query.where("picked_by", "==", picked_by_input)

        if validated_by_input:
            query = query.where("validated_by", "==", validated_by_input)

        # ---------- EXECUTE QUERY ----------
        docs = list(query.stream())

        if not docs:
            st.warning("❌ No matching orders found")
            return

        results = [{"order_id": doc.id} | doc.to_dict() for doc in docs]

        st.success(f"✅ Found {len(results)} matching orders")
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
