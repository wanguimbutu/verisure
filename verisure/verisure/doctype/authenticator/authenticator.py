# Copyright (c) 2025, verisure and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now
import json

class Authenticator(Document):
	pass

@frappe.whitelist()
def query_by_qrcode(qrcode: str):
    fields = ["name", "unique_id", "item_code", "item_name"]

    result = frappe.db.get_value("Authenticator", {"qrcode": qrcode}, fields, as_dict=True)

    if not result:
        return {"message": f"No record found for qrcode: {qrcode}"}

    return result


@frappe.whitelist(allow_guest=True)
def query_by_unique_id():
    # Try to get from form_dict first
    data = frappe.local.form_dict

    # If nothing, parse JSON body
    if not data.get("unique_id"):
        try:
            body = frappe.request.get_data(as_text=True)
            data = json.loads(body)
        except Exception:
            data = {}

    unique_id = data.get("unique_id")
    location_id = data.get("location_id")

    if not unique_id:
        return {"error": "unique_id is required"}

    # Fetch the authenticator doc
    doc = frappe.get_doc("Authenticator", {"unique_id": unique_id})

    # Increment or set no_of_authentications
    if not doc.no_of_authentications:
        doc.no_of_authentications = 1
    else:
        doc.no_of_authentications += 1

    # Append authentication history
    doc.append("authentication_history", {
        "location_id": location_id or "UNKNOWN",
        "timestamp": now()
    })

    doc.save(ignore_permissions=True)

    return {
        "name": doc.name,
        "expiry_date": doc.expiry_date,
        "item_code": doc.item_code,
        "item_name": doc.item_name,
        "batch_id": doc.batch_id,
        "no_of_authentications": doc.no_of_authentications,
        "authentication_history": doc.authentication_history
    }
