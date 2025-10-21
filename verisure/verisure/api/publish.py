import frappe
import requests
import json

@frappe.whitelist()
def publish_to_authenticator(docname):
    doc = frappe.get_doc('QR Codes', docname)

    # --- Site A: Create new records ---
    site_a_url = ""
    site_a_key = "<site_a_api_key>"
    site_a_secret = "<site_a_api_secret>"

    # --- Site B: Update existing records ---
    site_b_url = "https://another-site.com"
    site_b_key = "<site_b_api_key>"
    site_b_secret = "<site_b_api_secret>"

    headers_a = {
        "Authorization": f"token {site_a_key}:{site_a_secret}",
        "Content-Type": "application/json"
    }
    headers_b = {
        "Authorization": f"token {site_b_key}:{site_b_secret}",
        "Content-Type": "application/json"
    }

    published_count = 0
    activated_count = 0
    failed_count = 0
    skipped_count = 0

    for d in doc.qr_details:
        if d.published and d.published.strip().lower() == "yes":
            skipped_count += 1
            continue

        payload = {
            "qr_code": d.qr_code,
            "item_code": d.item_code,
            "batch_no": d.batch_no,
            "unique_no": d.unique_no
        }

        # Push to Site A ---
        try:
            r1 = requests.post(site_a_url, headers=headers_a, data=json.dumps(payload))
            if r1.status_code in (200, 201):
                d.published = "Yes"
                published_count += 1
            else:
                failed_count += 1
                frappe.log_error(f"Site A failed for {d.qr_code}: {r1.text}", "QR Publish Error")
                continue
        except Exception as e:
            failed_count += 1
            frappe.log_error(f"Error pushing to Site A for {d.qr_code}: {str(e)}", "QR Publish Exception")
            continue

        #Update 'activated' field on Site B ---
        try:
            # Search for existing Authenticator by qr_code
            search_url = f"{site_b_url}/api/resource/Authenticator?fields=['name']&filters=[[\"Authenticator\",\"qr_code\",\"=\",\"{d.qr_code}\"]]"
            r2 = requests.get(search_url, headers=headers_b)

            if r2.status_code == 200:
                data = r2.json()
                if data.get("data"):
                    auth_name = data["data"][0]["name"]
                    update_url = f"{site_b_url}/api/resource/Authenticator/{auth_name}"
                    update_payload = {"activated": "Yes"}
                    r3 = requests.put(update_url, headers=headers_b, data=json.dumps(update_payload))
                    if r3.status_code in (200, 202):
                        activated_count += 1
                    else:
                        frappe.log_error(f"Site B update failed for {d.qr_code}: {r3.text}", "QR Activate Error")
                else:
                    frappe.log_error(f"QR {d.qr_code} not found on Site B", "QR Activate Not Found")
            else:
                frappe.log_error(f"Site B search failed for {d.qr_code}: {r2.text}", "QR Activate Search Error")

        except Exception as e:
            frappe.log_error(f"Error updating Site B for {d.qr_code}: {str(e)}", "QR Activate Exception")

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return f"Published {published_count}, Activated {activated_count}, Skipped {skipped_count}, ❌ Failed {failed_count}"
