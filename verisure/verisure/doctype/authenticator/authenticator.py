# Copyright (c) 2025, verisure and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now

class Authenticator(Document):
	pass

@frappe.whitelist()
def query_by_qrcode(qrcode: str):
    fields = ["name", "unique_id", "item_code", "item_name"]

    result = frappe.db.get_value("Authenticator", {"qrcode": qrcode}, fields, as_dict=True)

    if not result:
        return {"message": f"No record found for qrcode: {qrcode}"}

    return result


@frappe.whitelist()
def query_by_unique_id(unique_id=None, location_id=None):
    """Fetch record by unique_id and update authentication history"""
    if not unique_id:
        return {"error": "unique_id is required"}

    fields = ["name", "expiry_date", "item_code", "item_name", "batch_id", "no_of_authentications", "auth_history"]

    doc = frappe.db.get_value("Authenticator", {"unique_id": str(unique_id).strip()}, fields, as_dict=True)

    if not doc:
        return {"message": f"No record found for unique_id: {unique_id}"}

    # increment no_of_authentications
    no_auths = doc.get("no_of_authentications") or 0
    frappe.db.set_value("Authenticator", doc.name, "no_of_authentications", no_auths + 1)

    # append auth_history
    history = doc.get("auth_history") or []
    history.append({"location_id": location_id or "UNKNOWN", "timestamp": now()})
    frappe.db.set_value("Authenticator", doc.name, "auth_history", history)

    # refresh updated values
    updated_doc = frappe.db.get_value(
        "Authenticator", {"name": doc.name}, fields, as_dict=True
    )

    return updated_doc
