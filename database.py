import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

def get_db_connection():
    print("Connecting to Firestore database...")
    
    try:
        # Check if secrets exist
        if "firebase" not in st.secrets:
            error_msg = "❌ Firebase secrets not found in st.secrets"
            print(error_msg)
            # st.error(error_msg)
            return None
            
        print("Firebase secrets found")
        
        firebase_credentials = dict(st.secrets["firebase"])  # Convert secrets to dict
        print(f"Firebase credentials keys: {list(firebase_credentials.keys())}")

        # Initialize Firebase if not already initialized
        if not firebase_admin._apps:
            print("Initializing Firebase app...")
            cred = credentials.Certificate(firebase_credentials)  # Use dictionary directly
            firebase_admin.initialize_app(cred)
            print("Firebase app initialized successfully")
        else:
            print("Firebase app already initialized")

        # Connect to Firestore
        print("Creating Firestore client...")
        db = firestore.client()
        print("Firestore client created successfully")
        return db

    except Exception as e:
        error_msg = f"❌ Error connecting to Firestore: {e}"
        print(error_msg)
        # st.error(error_msg)
        return None

def init_database():
    """
    Initialize the database with the required tables
    
    Args:
        db_path: Path to create the database file
    """
    # engine = get_db_connection()
    # if engine is None:
    #     print("Database connection failed.")
    #     return
    # try:
    #     with engine.begin() as conn:
    #         conn.execute(text('''
    #             CREATE TABLE IF NOT EXISTS orders (
    #                 id INT AUTO_INCREMENT PRIMARY KEY,
    #                 order_id VARCHAR(255) NOT NULL UNIQUE,
    #                 sku VARCHAR(255) NOT NULL,
    #                 quantity INT NOT NULL,
    #                 status VARCHAR(50) NOT NULL DEFAULT 'new',
    #                 picked_by VARCHAR(255),
    #                 validated_by VARCHAR(255),
    #                 platform VARCHAR(255),
    #                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    #                 updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    #                 dispatch_date DATETIME NOT NULL
    #             )
    #         '''))
    #         conn.commit()
    # except Exception as e:
    #     print(f"1Error initializing database: {e}")

def get_pass(username):
    print("Fetching password for user:", username)
    
    db = get_db_connection()
    if db is None:
        error_msg = "❌ Database connection failed in get_pass"
        print(error_msg)
        # st.error(error_msg)
        return None
        
    try:
        print(f"Querying Firestore for user: {username}")
        
        user_ref = db.collection("users").document(username)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            error_msg = f"❌ User {username} not found in Firestore"
            print(error_msg)
            # st.error(error_msg)
            return None
            
        user_data = user_doc.to_dict()
        print(f"User data retrieved for {username}: {list(user_data.keys()) if user_data else 'None'}")
        
        if 'pass' not in user_data:
            error_msg = f"❌ Password field not found for user {username}"
            print(error_msg)
            # st.error(error_msg)
            return None
            
        print(f"✅ Password retrieved successfully for {username}")
        return user_data['pass']
        
    except Exception as e:
        error_msg = f"❌ Error fetching password for {username}: {e}"
        print(error_msg)
        # st.error(error_msg)
        return None

def get_party(username):
    print(f"Fetching party for user: {username}")
    # st.write(f"🔍 DEBUG: Fetching party for user: {username}")
    
    db = get_db_connection()
    if db is None:
        error_msg = "❌ Database connection failed in get_party"
        print(error_msg)
        # st.error(error_msg)
        return "Both"  # Default fallback
        
    try:
        print(f"Querying Firestore for user party: {username}")
        # st.write(f"🔍 DEBUG: Querying Firestore for user party: {username}")
        
        user_ref = db.collection("users").document(username)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            error_msg = f"❌ User {username} not found in Firestore for party lookup"
            print(error_msg)
            # st.error(error_msg)
            return "Both"  # Default fallback
            
        user_data = user_doc.to_dict()
        print(f"User data for party lookup: {list(user_data.keys()) if user_data else 'None'}")
        # st.write(f"🔍 DEBUG: User data keys for party: {list(user_data.keys()) if user_data else 'None'}")
        
        if not user_data or 'party' not in user_data:
            error_msg = f"❌ Party field not found for user {username}"
            print(error_msg)
            # st.error(error_msg)
            return "Both"  # Default fallback
            
        party_value = user_data['party']
        print(f"Party value for {username}: {party_value}")
        # st.write(f"🔍 DEBUG: Party value for {username}: {party_value}")
        
        if party_value == 1:
            result = "Kangan"
        elif party_value == 2:
            result = "RS"
        elif party_value == 3:
            result = "Both"
        else:
            print(f"Unknown party value {party_value} for user {username}, defaulting to 'Both'")
            # st.warning(f"Unknown party value {party_value} for user {username}, defaulting to 'Both'")
            result = "Both"
            
        print(f"✅ Party result for {username}: {result}")
        # st.write(f"✅ DEBUG: Party result for {username}: {result}")
        return result
        
    except Exception as e:
        error_msg = f"❌ Error fetching party for {username}: {e}"
        print(error_msg)
        # st.error(error_msg)
        return "Both"  # Default fallback

def add_orders_to_db(orders_df, platform):
    """
    Add new orders to the database
    
    Args:
        orders_df: DataFrame containing order data
        platform: Name of the platform (e.g., 'flipkart', 'meesho')
    
    Returns:
        Tuple of (success boolean, count of orders added)
    """
    db = get_db_connection()
    if db is None:
        print("Database connection failed.")
        return False, 0

    batch = db.batch()  # Create a batch write object
    added_count = 0  # Track only successfully added orders

    try:
        for _, row in orders_df.iterrows():
            order_id = str(row["order_id"])
            doc_ref = db.collection("orders").document(order_id)
            # Skip if order already exists (check from our local set)
            doc_snapshot = doc_ref.get()
            if doc_snapshot.exists:
                continue

            # Add order to batch
            batch.set(doc_ref, {
                "sku": row["sku"],
                "quantity": row["quantity"],
                "status": "new",  # Default status
                "picked_by": "",
                "validated_by": "",
                "platform": platform,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "dispatch_date": row["dispatch_date"] if pd.notna(row["dispatch_date"]) else None
            })
            added_count += 1  # Increment only when added

            # Firestore allows a maximum of 500 operations per batch
            if added_count % 500 == 0:
                batch.commit()  # Commit the batch every 500 inserts
                batch = db.batch()  # Start a new batch

        # Commit any remaining writes
        batch.commit()

        st.session_state.orders_df = get_orders_from_db()

        return True, added_count  # Return count of successfully inserted orders

    except Exception as e:
        print(f"Database error: {e}")
        return False, added_count


def get_orders_from_db(status=None):
    """
    Get orders from the database
    
    Args:
        db_path: Path to the database
        status: Optional filter for order status
    
    Returns:
        DataFrame containing the orders
    """

    db = get_db_connection()
    orders_ref = db.collection("orders")

    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    query = orders_ref.where("created_at", ">=", seven_days_ago)

    # Apply status filter if provided
    if status:
        query = orders_ref.where("status", "==", status)

    orders = orders_ref.stream()
    order_list = []

    order_list = [
        {**order.to_dict(), "order_id": order.id}  # Merge Firestore data with ID
        for order in orders
    ]

    df = pd.DataFrame(order_list) if order_list else pd.DataFrame()

    if "dispatch_date" in df.columns:
        df["dispatch_date"] = pd.to_datetime(df["dispatch_date"], format="%d-%m-%Y", dayfirst=True, errors="coerce")

    return df

def update_status(order_id,status):
    db = get_db_connection()
    orders_ref = db.collection("orders").document(order_id)

    order_data = orders_ref.get().to_dict()  # Fetch order data safely
    
    if order_data:
        orders_ref.update({"status": status, "updated_at": datetime.utcnow()})
        print(f"✅ Order {order_id} {status}.")
    else:
        print(f"⚠️ Order {order_id} not found in Firestore.")

def get_orders_grouped_by_sku(orders_df, status=None):
    """
    Groups orders by SKU and dispatch date, ensuring earliest dispatch orders come first.
    """

    try:
        if orders_df.empty:
            print("⚠️ Warning: orders_df is empty before processing.")
            return pd.DataFrame()

        # Create a working copy
        orders_df = orders_df.copy()

        # print("Raw dispatch_date values:", orders_df["dispatch_date"].head(5).tolist())

        # Convert dispatch_date to datetime format
        orders_df["dispatch_date"] = pd.to_datetime(orders_df["dispatch_date"], dayfirst=True, errors="coerce")

        # print("After conversion, dispatch_date sample:\n", orders_df[['dispatch_date']].head())

        before_drop = len(orders_df)
        orders_df = orders_df.dropna(subset=['dispatch_date'])
        after_drop = len(orders_df)
        # print(f"Dropped {before_drop - after_drop} rows with NaT dispatch_date.")

        # Filter by status if provided
        if status:
            orders_df = orders_df[orders_df["status"] == status]

        if orders_df.empty:
            print("⚠️ Warning: No matching records after status filter.")
            return pd.DataFrame()

        def get_dispatch_breakdown(sub_df):
            grouped = sub_df.groupby("dispatch_date")["quantity"].sum().reset_index()
            return [
                {
                    "date": row["dispatch_date"].strftime("%d %b %Y"),
                    "quantity": int(row["quantity"])
                }
                for _, row in grouped.iterrows()
            ]

        # Group by SKU and dispatch_date
        grouped_df = orders_df.groupby("sku").apply(lambda df: pd.Series({
            "total_quantity": int(df["quantity"].sum()),
            "order_count": df["order_id"].nunique(),
            "dispatch_breakdown": get_dispatch_breakdown(df)
        })).reset_index()

        # Sort by dispatch date (earliest first)
        grouped_df = grouped_df.sort_values(by=["sku"], ascending=[True])

        return grouped_df

    except Exception as e:
        print(f"Error in grouping orders: {str(e)}")
        raise

def get_product_image_url(sku):
    print("Fetching product image for SKU:", sku)
    db = get_db_connection()
    if db is None:
        return None
    
    print("Incoming SKU:", sku, repr(sku))
    print("Lower SKU:", sku.lower(), repr(sku.lower()))

    # Fetch all products for debugging
    docs = db.collection("products").stream()
    for d in docs:
        data = d.to_dict()
        print("DB SKU:", data.get("sku"), repr(data.get("sku")))

    sku_lower = sku.lower().strip()
    # products collection structure:
    # products/{unique_id} where document contains { sku: ..., img_url: ... }
    products_ref = db.collection("products").where("sku", "==", sku_lower).limit(1)
    docs = list(products_ref.stream())
    
    if not docs:
        return None

    data = docs[0].to_dict()
    print("Product data retrieved:", data)
    return data.get("img_url")

def update_orders_for_sku(sku, quantity_to_process, new_status, user=None):
    """
    Safe race-condition-free update for a specific SKU + dispatch_date.
    Uses Firestore transaction to prevent multiple users from corrupting data.
    """

    db = get_db_connection()
    if db is None:
        return 0, []

    transaction = db.transaction()

    # Determine old status → what we are converting *from*
    old_status = (
        "new" if new_status == "picked" else
        "picked" if new_status == "validated" else
        None
    )

    if old_status is None:
        return 0, []

    @firestore.transactional
    def process(transaction):
        # STEP 1 — READ orders safely inside transaction
        query = (
            db.collection("orders")
            .where("sku", "==", sku)
            .where("status", "==", old_status)
            .order_by("created_at")
            .limit(quantity_to_process)
        )

        orders = list(transaction.get(query))

        # CRITICAL VALIDATION
        if len(orders) < quantity_to_process:
            # update dataframe in session state to reflect current DB state
            st.session_state.orders_df = get_orders_from_db()
            return -1, []

        processed_ids = []

        # STEP 2 — UPDATE ORDER-BY-ORDER inside the same transaction
        for order in orders:
            ref = order.reference
            update_fields = {
                "status": new_status,
                "updated_at": datetime.utcnow()
            }

            if user:
                update_fields[f"{new_status}_by"] = user

            transaction.update(ref, update_fields)
            processed_ids.append(order.id)

        return len(processed_ids), processed_ids

    # RUN the transactional function
    try:
        processed_qty, processed_ids = process(transaction)
    except Exception as ex:
        raise

    # STEP 3 — update Streamlit session cache (optional)
    if "orders_df" in st.session_state:
        df = st.session_state.orders_df
        mask = df["order_id"].isin(processed_ids)
        df.loc[mask, "status"] = new_status
        if user:
            df.loc[mask, f"{new_status}_by"] = user
        st.session_state.orders_df = df

    return processed_qty, processed_ids

def calculate_order_counts():
    import utils
    """
    Calculate counts of orders by status
    
    Returns:
        Dictionary with counts for each status
    """
    counts = {'new': 0, 'picked': 0, 'validated': 0}

    if "orders_df" not in st.session_state:
        st.session_state.orders_df = get_orders_from_db()

    orders_df = st.session_state.orders_df  # Get the cached orders DataFrame
    party_filter = st.session_state.get("party_filter", "Both")
    orders_df = utils.get_party_filter_df(orders_df, party_filter)

    if not orders_df.empty:
        counts = orders_df["status"].value_counts().to_dict()  # Count occurrences of each status
    
    # Ensure all statuses are included (even if 0)
    for status in ["new", "picked", "validated"]:
        counts.setdefault(status, 0)

    return counts

def get_user_productivity():
    import utils
    """
    Get productivity data by user from Firestore.

    Returns:
        DataFrame with user productivity data
    """
    if "orders_df" not in st.session_state or st.session_state.orders_df.empty:
        return pd.DataFrame(columns=['user', 'picked_count', 'picked_quantity', 'validated_count', 'validated_quantity'])

    orders_df = st.session_state.orders_df
    party_filter = st.session_state.get("party_filter", "Both")
    orders_df = utils.get_party_filter_df(orders_df, party_filter)

    # Filter and group data for picked orders
    picked_summary = (
        orders_df[orders_df["picked_by"].notna()]
        .groupby("picked_by")
        .agg(picked_count=("picked_by", "count"), picked_quantity=("quantity", "sum"))
        .reset_index()
        .rename(columns={"picked_by": "user"})
    )

    # Filter and group data for validated orders
    validated_summary = (
        orders_df[orders_df["validated_by"].notna()]
        .groupby("validated_by")
        .agg(validated_count=("validated_by", "count"), validated_quantity=("quantity", "sum"))
        .reset_index()
        .rename(columns={"validated_by": "user"})
    )

    # Merge both summaries
    productivity_df = pd.merge(picked_summary, validated_summary, on="user", how="outer").fillna(0)

    # Convert count/quantity columns to integer type
    for col in ["picked_count", "picked_quantity", "validated_count", "validated_quantity"]:
        productivity_df[col] = productivity_df[col].astype(int)

    return productivity_df