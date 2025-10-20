import frappe
import requests
import json

@frappe.whitelist()
def publish_to_authenticator(docname):
    doc = frappe.get_doc('QR Codes', docname)

    # --- Target site details ---
    target_url = "target url here"
    api_key = "<api_key>"
    api_secret = "<api_secret>"

    headers = {
        "Authorization": f"token {api_key}:{api_secret}",
        "Content-Type": "application/json"
    }

    published_count = 0
    skipped_count = 0
    failed_count = 0

    for d in doc.qr_details:
        # Skip if already published
        if d.published and d.published.strip().lower() == "Yes":
            skipped_count += 1
            continue

        payload = {
            "qr_code": d.qr_code,
            "item_code": d.item_code,
            "batch_no": d.batch_no
        }

        try:
            response = requests.post(target_url, headers=headers, data=json.dumps(payload))
            if response.status_code in (200, 201):
                d.published = "Yes"
                published_count += 1
            else:
                failed_count += 1
                frappe.log_error(
                    f"Failed to push QR Code {d.qr_code}. Status: {response.status_code}. Response: {response.text}",
                    "QR Publish Error"
                )
        except Exception as e:
            failed_count += 1
            frappe.log_error(f"Error publishing QR {d.qr_code}: {str(e)}", "QR Publish Exception")

    # Save updated published statuses
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return f"Published {published_count}, Skipped {skipped_count}, Failed {failed_count}"
