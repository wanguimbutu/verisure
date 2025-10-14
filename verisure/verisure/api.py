import frappe

@frappe.whitelist(allow_guest=False)
def update_qr_activation(data):
    """
    Receive webhook from Site A and update activation status
    """
    try:
        qrcode = data.get('qrcode')
        activation_status = data.get('activation_status')

        doctype = "Authenticator"

        if frappe.db.exists(doctype, qrcode):
            doc = frappe.get_doc(doctype, qrcode)
            doc.activation_status = activation_status
            doc.save(ignore_permissions=True)
            frappe.db.commit()

            return {"success": True, "message": f"Updated {qrcode}"}
        else:
            return {"success": False, "error": "QR Code not found"}

    except Exception as e:
        frappe.log_error(str(e), "Webhook Update Error")
        return {"success": False, "error": str(e)}
