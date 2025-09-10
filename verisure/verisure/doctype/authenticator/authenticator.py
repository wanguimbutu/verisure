# Copyright (c) 2025, verisure and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now

class Authenticator(Document):
	pass

@frappe.whitelist()
def query_by_qrcode(qrcode):
    """
    Query by QR Code:
    - Returns item_code, item_name, unique_id only.
    """
    doc = frappe.get_doc("Authenticator", {"qrcode": qrcode})
    if not doc:
        frappe.throw("No record found matching the provided qrcode", frappe.DoesNotExistError)

    return {
        "name": doc.name,
        "unique_id": doc.unique_id,
        "item_code": doc.item_code,
        "item_name": doc.item_name
    }



@frappe.whitelist()
def query_by_unique_id(unique_id, location_id=None):
    """
    Query by Unique ID:
    - Returns item_code, item_name, unique_id, expiry_date, batch_id
    - Increments no_of_authentications (sets to 1 if missing or 0)
    - Writes location_id and timestamp into auth_history
    """
    doc = frappe.get_doc("Authenticator", {"unique_id": unique_id})
    if not doc:
        frappe.throw("No record found matching the provided unique_id", frappe.DoesNotExistError)

    # Increment authentication counter
    if not doc.no_of_authentications or doc.no_of_authentications == 0:
        doc.no_of_authentications = 1
    else:
        doc.no_of_authentications += 1

    # Append history
    if location_id:
        doc.append("auth_history", {
            "location_id": location_id,
            "timestamp": now()
        })

    doc.save(ignore_permissions=True)

    return {
        "name": doc.name,
        "unique_id": doc.unique_id,
        "expiry_date": doc.expiry_date,
        "item_code": doc.item_code,
        "item_name": doc.item_name,
        "batch_id": doc.batch_id,
        "no_of_authentications": doc.no_of_authentications,
        "auth_history": doc.auth_history
    }
