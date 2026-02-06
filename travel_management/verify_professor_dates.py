import frappe
from datetime import datetime


@frappe.whitelist()
def verify_professor_dates():
	"""
	API endpoint to verify GL entry dates for each professor
	Access via: /api/method/travel_management.verify_professor_dates
	"""

	# Query all professors with Travel accounts
	sql = """
        SELECT 
            SUBSTRING_INDEX(account, ' ', 1) as professor,
            account,
            MIN(posting_date) as first_transfer,
            MAX(posting_date) as last_transfer,
            COUNT(*) as entry_count,
            ROUND(SUM(CASE WHEN debit > 0 THEN debit ELSE 0 END), 2) as total_debit,
            ROUND(SUM(CASE WHEN credit > 0 THEN credit ELSE 0 END), 2) as total_credit
        FROM `tabGL Entry`
        WHERE 
            is_cancelled = 0
            AND account LIKE '%Travel - IE%'
        GROUP BY 
            SUBSTRING_INDEX(account, ' ', 1),
            account
        ORDER BY professor
    """

	results = frappe.db.sql(sql, as_dict=1)

	# Format response
	output = {"timestamp": datetime.now().isoformat(), "professors": []}

	for row in results:
		prof = {
			"tag": row.get("professor", ""),
			"account": row.get("account", ""),
			"first_transfer_date": str(row.get("first_transfer", "")),
			"last_transfer_date": str(row.get("last_transfer", "")),
			"entry_count": row.get("entry_count", 0),
			"total_debit_in": float(row.get("total_debit", 0)),
			"total_credit_out": float(row.get("total_credit", 0)),
		}
		output["professors"].append(prof)

	return output
