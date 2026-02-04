from datetime import date
from returns.evanik_client import EvanikClient
import re
from database import pending_awb, remove_pending_awb

def process_awb_list(awb_list, client, start_date, end_date, return_date,user_role):
    results = []

    for awb in awb_list:
        #if awb had \ , / , | , - , & , = , # , ) , ( , ] , [ , { , } , ,<comma> ,characters,<space> then skip
        regex = r"[,<>\|\\\/\-\&\=\#\(\)\[\]\{\}\s]"
        if re.search(regex, awb):
            print(f"DEBUG: Skipping invalid AWB {awb} due to special characters")
            results.append((awb, "INVALID_AWB"))
            continue

        record = client.fetch_return_record(awb, start_date, end_date)

        if "error" in record:
            print(f"DEBUG: Error fetching record for AWB {awb}: {record['error']}")
            pending_awb(awb)
            results.append((awb, record["error"]))
            continue

        if record.get("return_date"):
            print(f"DEBUG: AWB {awb} already marked as returned on {record.get('return_date')}")
            results.append((awb, "ALREADY_RETURNED"))
            continue

        update = client.mark_return_received(record, return_date, awb,user_role)

        if update.get("updateResult") == 1:
            print(f"DEBUG: Successfully marked AWB {awb} as returned")
            remove_pending_awb(awb)
            results.append((awb, "SUCCESS"))
        else:
            print(f"DEBUG: Failed to mark AWB {awb} as returned: {update}")
            pending_awb(awb)
            results.append((awb, f"FAILED: {update}"))

    return results
