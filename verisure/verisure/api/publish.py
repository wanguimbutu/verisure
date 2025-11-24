import frappe
import requests
import json
import urllib.parse
from datetime import datetime


def get_auth_headers():
    """Return headers and URLs for Site A and Site B authentication."""
    auth_config = {
        "site_a": {
            "url": " https://your-site-a/api/resource/doctype",
            "key": " ",
            "secret": " "
        },
        "site_b": {
            "url": "https://site-b/api/resource/doctype",
            "key": "",
            "secret": ""
        }
    }

    headers_a = {
        "Authorization": f"token {auth_config['site_a']['key']}:{auth_config['site_a']['secret']}",
        "Content-Type": "application/json"
    }

    headers_b = {
        "Authorization": f"token {auth_config['site_b']['key']}:{auth_config['site_b']['secret']}",
        "Content-Type": "application/json"
    }

    return {
        "site_a_url": auth_config["site_a"]["url"],
        "site_b_url": auth_config["site_b"]["url"],
        "headers_a": headers_a,
        "headers_b": headers_b
    }


def activate_single_qr_on_site_b(qr_code, site_b_url, headers_b):
    """Helper: activate a single QR code on Site B's Authenticator doctype."""
    try:
        filters = json.dumps([["Authenticator", "qrcode", "=", qr_code]])
        fields = json.dumps(["name"])
        search_url = f"{site_b_url}?fields={urllib.parse.quote(fields)}&filters={urllib.parse.quote(filters)}"

        r2 = requests.get(search_url, headers=headers_b)
        if r2.status_code == 200:
            data = r2.json()
            if data.get("data"):
                auth_name = data["data"][0]["name"]
                update_url = f"{site_b_url}/{auth_name}"
                update_payload = {"activated": "Yes"}

                r3 = requests.put(update_url, headers=headers_b, data=json.dumps(update_payload))
                if r3.status_code in (200, 202):
                    return True
                else:
                    frappe.log_error(f"Site B update failed for {qr_code}: {r3.text}", "QR Activate Error")
            else:
                frappe.log_error(f"QR {qr_code} not found in Site B Authenticator", "QR Activate Not Found")
        else:
            frappe.log_error(
                f"Site B search failed for {qr_code}: {r2.status_code} - {r2.text}",
                "QR Activate Search Error"
            )
    except Exception as e:
        frappe.log_error(f"Error activating {qr_code} on Site B: {str(e)}", "QR Activate Exception")
    return False


@frappe.whitelist()
def activate_on_site_b(docname):

    doc = frappe.get_doc('QR_Codes', docname)
    auth = get_auth_headers()
    site_b_url = auth["site_b_url"]
    headers_b = auth["headers_b"]

    activated_count = 0
    failed_count = 0

    for d in doc.qr_details:
        if not d.qr_code:
            continue

        if activate_single_qr_on_site_b(d.qr_code, site_b_url, headers_b):
            d.activation = "Yes"
            activated_count += 1
        else:
            failed_count += 1

    return {
        "success": True,
        "message": f" Activated {activated_count}, Failed {failed_count}"
    }

@frappe.whitelist()
def publish_to_authenticator(docname):

    doc = frappe.get_doc('QR_Codes', docname)
    auth = get_auth_headers()
    site_a_url = auth["site_a_url"]
    headers_a = auth["headers_a"]

    published_count = 0
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
        }

        try:
            r1 = requests.post(site_a_url, headers=headers_a, data=json.dumps(payload))
            if r1.status_code in (200, 201):
                d.published = "Yes"
                published_count += 1
            else:
                failed_count += 1
                frappe.log_error(f"Site A failed for {d.qr_code}: {r1.text}", "QR Publish Error")
        except Exception as e:
            failed_count += 1
            frappe.log_error(f"Error pushing to Site A for {d.qr_code}: {str(e)}", "QR Publish Exception")

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return f"Published {published_count},Skipped {skipped_count}, Failed {failed_count}"


def get_last_successful_sync():
    """Get timestamp of the last successful sync."""
    last_log = frappe.db.get_all(
        "Sync Log",
        filters={"sync_type": "Authentication History Sync", "status": "Success"},
        fields=["end_time"],
        order_by="end_time desc",
        limit=1,
    )
    if last_log:
        return last_log[0].end_time
    return None


def create_sync_log_entry(start_time, synced_count, skipped_count, failed_count, status, log_details=None):
    """Create a Sync Log record."""
    log = frappe.get_doc({
        "doctype": "Sync Log",
        "sync_type": "Authentication History Sync",
        "start_time": start_time,
        "end_time": datetime.now(),
        "last_run": start_time,
        "synced_count": synced_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "status": status,
        "log_details": log_details or ""
    })
    log.insert(ignore_permissions=True)
    frappe.db.commit()
    return log.name


@frappe.whitelist()
def sync_authentication_history():

    start_time = datetime.now()
    synced_count = 0
    skipped_count = 0
    failed_count = 0
    log_details = []

    auth = get_auth_headers()
    site_a_url = auth["site_a_url"]
    site_b_url = auth["site_b_url"]
    headers_a = auth["headers_a"]
    headers_b = auth["headers_b"]

    try:
        last_run = get_last_successful_sync()
        frappe.logger().info(f"Last successful sync: {last_run}")

        filters = []
        if last_run:
            filters.append(["modified", ">", last_run.strftime("%Y-%m-%d %H:%M:%S")])

        fields = json.dumps(["name", "qrcode", "authentication_history", "modified"])
        filters_json = json.dumps(filters)
        params = f"fields={urllib.parse.quote(fields)}&filters={urllib.parse.quote(filters_json)}&limit_page_length=0"
        get_url = f"{site_b_url}?{params}"

        r_b = requests.get(get_url, headers=headers_b)
        if r_b.status_code != 200:
            msg = f"Failed to fetch Site B data: {r_b.text}"
            frappe.log_error(msg, "Auth History Sync")
            create_sync_log_entry(start_time, synced_count, skipped_count, failed_count, "Failed", msg)
            return {"success": False, "message": msg}

        data_b = r_b.json().get("data", [])
        if not data_b:
            create_sync_log_entry(start_time, 0, 0, 0, "Success", "No new data since last sync.")
            return {"success": True, "message": "No new authentication history to sync."}

        for auth_b in data_b:
            qr_code = auth_b.get("qrcode")
            if not qr_code:
                continue

            filters_a = json.dumps([["Authenticator", "qrcode", "=", qr_code]])
            fields_a = json.dumps(["name", "authentication_history"])
            search_url = f"{site_a_url}?fields={urllib.parse.quote(fields_a)}&filters={urllib.parse.quote(filters_a)}"

            r_a = requests.get(search_url, headers=headers_a)
            if r_a.status_code != 200:
                failed_count += 1
                log_details.append(f"{qr_code}: Site A search error {r_a.status_code}")
                continue

            data_a = r_a.json().get("data", [])
            if not data_a:
                skipped_count += 1
                log_details.append(f"{qr_code}: Missing on Site A.")
                continue

            site_a_auth = data_a[0]
            auth_name = site_a_auth["name"]

            history_b = auth_b.get("authentication_history", [])
            if not history_b:
                continue

            history_a = site_a_auth.get("authentication_history", [])
            existing_ids = {h.get("unique_id") for h in history_a if h.get("unique_id")}
            new_entries = [row for row in history_b if row.get("unique_id") not in existing_ids]

            if not new_entries:
                skipped_count += 1
                continue

            update_payload = {"authentication_history": history_a + new_entries}
            update_url = f"{site_a_url}/{auth_name}"
            r_update = requests.put(update_url, headers=headers_a, data=json.dumps(update_payload))

            if r_update.status_code in (200, 202):
                synced_count += len(new_entries)
            else:
                failed_count += 1
                log_details.append(f"{qr_code}: update failed ({r_update.status_code}) {r_update.text}")

        create_sync_log_entry(
            start_time,
            synced_count,
            skipped_count,
            failed_count,
            "Success",
            "\n".join(log_details)
        )

        return {
            "success": True,
            "message": f"Synced {synced_count} new entries, Skipped {skipped_count},Failed {failed_count}"
        }

    except Exception as e:
        frappe.log_error(f"Error syncing Authenticator data: {str(e)}", "Auth History Sync Exception")
        create_sync_log_entry(start_time, synced_count, skipped_count, failed_count, "Failed", str(e))
        return {"success": False, "message": f"Sync failed: {str(e)}"}
