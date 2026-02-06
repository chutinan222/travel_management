#!/usr/bin/env python
"""
Verification script to check GL entries and calculated validity periods
for each professor in the Dashboard Summary report
"""

import sys
import os
from datetime import datetime, timedelta

# Setup Frappe environment
sys.path.insert(0, "/home/chilly/erp")
os.chdir("/home/chilly/erp")

import frappe

frappe.init(user="Administrator")

from travel_management.travel_management.report.dashboard_summary.dashboard_summary import (
	get_all_transfer_dates,
	calculate_validity_periods,
	add_years,
)

# List of all professor tags
PROFESSOR_TAGS = [
	"AS",
	"WI",
	"WW",
	"KG",
	"ST",
	"RC",
	"WL",
	"SR",
	"WR",
	"CN",
	"CB",
	"WP",
	"US",
	"AC",
	"KR",
	"WS",
	"SN",
	"NR",
	"CS",
	"PC",
	"AL",
	"WM",
	"TP",
	"RP",
	"KP",
	"AB",
	"PO",
	"TO",
	"PM",
	"ND",
	"NP",
]

print("\n" + "=" * 100)
print("DASHBOARD SUMMARY - DATABASE VERIFICATION REPORT")
print("=" * 100)
print(f"Current Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

for prof_tag in PROFESSOR_TAGS:
	print("-" * 100)
	print(f"\n📊 PROFESSOR: {prof_tag}")
	print("-" * 100)

	# Get account pattern
	account_pattern = f"%{prof_tag} Travel - IE%"
	print(f"Account Pattern: {account_pattern}")

	# Query to find matching GL Entry accounts
	sql_accounts = """
        SELECT DISTINCT gle.account
        FROM `tabGL Entry` gle
        WHERE gle.is_cancelled = 0
        AND gle.account LIKE %s
        ORDER BY gle.account
    """
	accounts = frappe.db.sql(sql_accounts, (account_pattern,), as_dict=1)

	if accounts:
		print(f"✅ Found {len(accounts)} account(s):")
		for acc in accounts:
			print(f"   - {acc['account']}")
	else:
		print("❌ No accounts found in GL Entry")
		continue

	# Get transfer dates
	transfer_dates = get_all_transfer_dates(prof_tag)

	if transfer_dates:
		print(f"\n✅ Found {len(transfer_dates)} transfer date(s):")
		for i, date in enumerate(transfer_dates, 1):
			print(f"   {i}. {date.strftime('%d-%m-%Y')} (posting_date)")

			# Show GL entries for this date
			sql_entries = """
                SELECT gle.posting_date, gle.debit, gle.credit, gle.voucher_type, gle.voucher_no
                FROM `tabGL Entry` gle
                WHERE gle.is_cancelled = 0
                AND gle.posting_date = %s
                AND gle.account LIKE %s
                ORDER BY gle.debit DESC, gle.credit DESC
            """
			entries = frappe.db.sql(sql_entries, (date, account_pattern), as_dict=1)
			for entry in entries:
				debit = entry.get("debit") or 0
				credit = entry.get("credit") or 0
				if debit > 0:
					print(f"      ├─ Debit: ฿{debit:,.2f} ({entry['voucher_type']} {entry['voucher_no']})")
				if credit > 0:
					print(f"      └─ Credit: ฿{credit:,.2f} ({entry['voucher_type']} {entry['voucher_no']})")
	else:
		print("❌ No transfer dates found")
		continue

	# Calculate and show validity periods
	print(f"\n📅 CALCULATED VALIDITY PERIODS:")
	validity_periods = calculate_validity_periods(prof_tag)

	if validity_periods:
		for idx, (start, end) in enumerate(validity_periods, 1):
			days_remaining = (end - datetime.now().date()).days
			status = "🔴 EXPIRED" if days_remaining < 0 else "🟢 ACTIVE" if days_remaining >= 0 else ""
			print(f"\n   Period {idx}:")
			print(f"   Start Date: {start.strftime('%d-%m-%Y')}")
			print(f"   End Date:   {end.strftime('%d-%m-%Y')} {status}")
			print(f"   Duration:   2 years - 1 day")
			print(f"   Days Left:  {days_remaining} days")
	else:
		print("   ❌ No validity periods calculated")

	print()

print("\n" + "=" * 100)
print("END OF VERIFICATION REPORT")
print("=" * 100 + "\n")

frappe.destroy()
