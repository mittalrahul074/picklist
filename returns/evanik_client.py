import base64
import time
import database

class EvanikClient:
    def __init__(self, session):
        self.session = session

    def fetch_return_record(self, awb, start_date, end_date):
        url = (
            f"https://app.evanik.ai/get_return_table_data"
            f"?startDate={start_date}&endDate={end_date}"
            f"&channelName=&storeName=&returnType=Not%20Received"
            f"&deposition=&reimbursement=&transporter="
            f"&searchValue={awb}&page=0&limit=10"
        )
        print(f"DEBUG: Fetching return record URL: {url}")
        res = self.session.get(url)

        if "<html" in res.text.lower():
            return {"error": "SESSION_EXPIRED"}

        data = res.json()
        if not data.get("tableResult"):
            return {"error": "NOT_FOUND"}

        return data["tableResult"][0]

    def mark_return_received(self, item, return_date,awb,user_role):
        encoded_skucode = base64.b64encode(
            (item.get("skucode") or "").encode()
        ).decode()

        encoded_master = base64.b64encode(
            (item.get("master_skucode") or "").encode()
        ).decode()

        url = (
            f"https://app.evanik.ai/update_return_flag?"
            f"deposition=1"
            f"&returnType=receive"
            f"&returnDate={return_date}"
            f"&OrderItemId={item['orderItemId']}"
            f"&skucode={encoded_skucode}"
            f"&OrderId={item['orderid']}"
            f"&master_skucode={encoded_master}"
            f"&inventoryAdd=false"
            f"&total_items={item.get('total_items',1)}"
            f"&invoice_number={item.get('invoice_number','')}"
        )

        print(f"DEBUG: Marking return received URL: {url}")
        res = self.session.get(url)

        if "<html" in res.text.lower():
            return {"error": "SESSION_EXPIRED"}

        database.update_status(item['orderid'], "m_return",user_role)
        database.enter_return_data(item['orderid'], return_date, user_role,awb,item.get("skucode"))

        return res.json()
