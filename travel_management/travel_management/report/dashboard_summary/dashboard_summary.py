# Copyright (c) 2026, Administrator and contributors

from datetime import datetime, timedelta
import frappe
from frappe.utils import flt, getdate
import logging

# Setup logging for debugging
logger = logging.getLogger(__name__)


def add_years(date_obj, years):
	try:
		return date_obj.replace(year=date_obj.year + years)
	except ValueError:
		return date_obj.replace(month=2, day=28, year=date_obj.year + years)


def get_first_transfer_date(tag):
	"""
	Get the first money transfer date (debit > 0) for a professor tag
	from the GL Entry that matches the Travel - IE account
	"""
	# Build the pattern in Python to avoid % conflicts
	pattern = f"%{tag} Travel%"
	sql = """
		SELECT MIN(gle.posting_date) as first_transfer_date
		FROM `tabGL Entry` gle
		WHERE 
			gle.is_cancelled = 0
			AND gle.debit > 0
			AND gle.account LIKE %s
	"""
	result = frappe.db.sql(sql, (pattern,), as_dict=1)
	if result and result[0].get("first_transfer_date"):
		return getdate(result[0]["first_transfer_date"])
	return None


def get_all_transfer_dates(tag):
	"""
	Get all money transfer dates (debit > 0) for a professor tag
	Returns them in chronological order
	"""
	# Build the pattern in Python to avoid % conflicts
	pattern = f"%{tag} Travel%"
	sql = """
		SELECT DISTINCT gle.posting_date
		FROM `tabGL Entry` gle
		WHERE 
			gle.is_cancelled = 0
			AND gle.debit > 0
			AND gle.account LIKE %s
		ORDER BY gle.posting_date ASC
	"""
	result = frappe.db.sql(sql, (pattern,), as_dict=1)
	return [getdate(row["posting_date"]) for row in result]


def calculate_validity_periods(tag):
	"""
	Calculate validity periods based on money transfers

	Rules:
	1. First transfer date starts the first 2-year period
	2. If a new transfer happens WITHIN the period, create a NEW period starting when current period ENDS
	3. Each transfer gets its own 2-year validity period (separate, not extended)
	4. Return list of (start_date, end_date) tuples
	"""
	transfer_dates = get_all_transfer_dates(tag)

	# Log the transfer dates found
	frappe.logger().info(f"[VALIDITY] Tag: {tag} - Found {len(transfer_dates)} transfer dates")
	if transfer_dates:
		frappe.logger().info(
			f"[VALIDITY] Tag: {tag} - Dates: {[d.strftime('%Y-%m-%d') for d in transfer_dates]}"
		)

	if not transfer_dates:
		frappe.logger().warning(f"[VALIDITY] Tag: {tag} - No transfer dates found, returning empty periods")
		return []

	periods = []
	current_start = transfer_dates[0]
	current_trigger = transfer_dates[0]  # 🔥 Track which transfer triggers this period
	# 🔥 Valid for 2 years - 1 day (as per business rule)
	current_end = add_years(current_start, 2) - timedelta(days=1)

	frappe.logger().info(
		f"[VALIDITY] Tag: {tag} - Period 1 initialized: {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')} [Triggered by: {current_trigger.strftime('%Y-%m-%d')}]"
	)

	# Process each subsequent transfer date
	for i, transfer_date in enumerate(transfer_dates[1:], 1):
		frappe.logger().debug(
			f"[VALIDITY] Tag: {tag} - Processing transfer {i + 1}: {transfer_date.strftime('%Y-%m-%d')}"
		)

		if transfer_date <= current_end:
			# Mid-period transfer: Save current period and create NEW period starting when current ends
			frappe.logger().info(
				f"[VALIDITY] Tag: {tag} - 🔴 MID-PERIOD TRANSFER! Transfer {transfer_date.strftime('%Y-%m-%d')} is within period (ends {current_end.strftime('%Y-%m-%d')})"
			)
			frappe.logger().info(
				f"[VALIDITY] Tag: {tag} - Saving period: {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')} [Triggered by: {current_trigger.strftime('%Y-%m-%d')}]"
			)

			periods.append((current_start, current_end, current_trigger))

			# NEW period starts the day AFTER current period ends
			current_start = current_end + timedelta(days=1)
			current_trigger = transfer_date  # 🔥 This transfer triggers the new period
			current_end = add_years(current_start, 2) - timedelta(days=1)

			frappe.logger().info(
				f"[VALIDITY] Tag: {tag} - New period for transfer {transfer_date.strftime('%Y-%m-%d')}: {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}"
			)
		else:
			# Transfer after current period - save current and start new
			frappe.logger().info(
				f"[VALIDITY] Tag: {tag} - Transfer {transfer_date.strftime('%Y-%m-%d')} is AFTER period ends"
			)
			frappe.logger().info(
				f"[VALIDITY] Tag: {tag} - Saving period: {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')} [Triggered by: {current_trigger.strftime('%Y-%m-%d')}]"
			)

			periods.append((current_start, current_end, current_trigger))
			current_start = transfer_date
			current_trigger = transfer_date  # 🔥 This transfer triggers the new period
			current_end = add_years(current_start, 2) - timedelta(days=1)

			frappe.logger().info(
				f"[VALIDITY] Tag: {tag} - New period started: {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}"
			)

	# Add the last period
	periods.append((current_start, current_end, current_trigger))
	frappe.logger().info(
		f"[VALIDITY] Tag: {tag} - Final period added: {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')} [Triggered by: {current_trigger.strftime('%Y-%m-%d')}]"
	)
	frappe.logger().info(f"[VALIDITY] Tag: {tag} - Total periods: {len(periods)}")
	for idx, (start, end, trigger) in enumerate(periods, 1):
		frappe.logger().info(
			f"[VALIDITY] Tag: {tag} - Period {idx}: {start.strftime('%Y-%m-%d')} → {end.strftime('%Y-%m-%d')} [Triggered by: {trigger.strftime('%Y-%m-%d')}]"
		)

	return periods


def execute(filters=None):
	if not filters:
		filters = {}

	# Get the period filter - now in Gregorian year format
	period = filters.get("budget_period")

	# Parse Gregorian year range from period string (e.g., "2024-2025 (งบ 70-71)" → years 2024-2025)
	filtered_years = None
	if period and period != "All Years":
		try:
			# Extract Gregorian years from "2024-2025 (...)" format
			import re

			match = re.search(r"(\d{4})-(\d{4})", period)
			if match:
				gregorian_start = int(match.group(1))
				gregorian_end = int(match.group(2))
				filtered_years = (gregorian_start, gregorian_end)
				frappe.logger().info(
					f"[FILTER] Budget period: {period} → Gregorian years {gregorian_start}-{gregorian_end}"
				)
		except Exception as e:
			frappe.logger().warning(f"[FILTER] Error parsing period '{period}': {e}")

	# ---------------------------------------------------------
	# 🔵 TEMPLATE GROUPS
	# ---------------------------------------------------------
	T_CAT1 = ["Template ในประเทศ (เบิกภาค)", "ในประเทศ (เบิกภาค)"]
	T_CAT21 = [
		"Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน",
		"Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน (ขอทุนคณะ/มช.)",
		"ต่างประเทศ (เบิกภาค) นำเสนอผลงาน",
		"ต่างประเทศ (เบิกภาค) นำเสนอผลงาน (ขอทุนคณะ/มช.)",
	]
	T_CAT22 = [
		"Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน ไม่เกิน 60000",
		"Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน เกิน 60000",
		"Template ต่างประเทศ  (เบิกภาค) นำเสนอผลงาน ไม่เกิน 60000",
	]
	T_CAT3 = ["Template ต่างประเทศ (เบิกภาค) ไม่นำเสนอผลงาน ไม่เกิน 40,000 บาท"]

	def safe_tuple(lst):
		if not lst:
			return ("", "")
		return tuple(lst) if len(lst) > 1 else (lst[0], lst[0])

	# ---------------------------------------------------------
	# 🟡 Get professor tags dynamically from GL Entry accounts
	# ---------------------------------------------------------
	sql_get_tags = """
		SELECT DISTINCT 
			SUBSTRING_INDEX(gle.account, ' ', 1) as tag
		FROM `tabGL Entry` gle
		WHERE 
			gle.is_cancelled = 0
			AND gle.account LIKE '% Travel - IE%'
			AND SUBSTRING_INDEX(gle.account, ' ', 1) != 'IE'
		ORDER BY tag ASC
	"""
	tag_results = frappe.db.sql(sql_get_tags, as_dict=1)
	PROFESSOR_TAGS = [row.get("tag") for row in tag_results if row.get("tag")]
	
	if not PROFESSOR_TAGS:
		frappe.logger().warning("[REPORT] No professor tags found in GL Entry")
		return columns, [], None, {}

	columns = [
		{"label": "อาจารย์ (Tag)", "fieldname": "professor", "fieldtype": "Data", "width": 100},
		{"label": "รอบวันที่", "fieldname": "cycle_period", "fieldtype": "Data", "width": 180},
		{"label": "เงินเข้า ", "fieldname": "budget", "fieldtype": "Currency", "width": 110},
		{"label": "ยอดใช้รวม", "fieldname": "used_total", "fieldtype": "Currency", "width": 110},
		{"label": "กรณี 1", "fieldname": "used_c1", "fieldtype": "Currency", "width": 110},
		{"label": "กรณี 2.1", "fieldname": "used_c21", "fieldtype": "Currency", "width": 110},
		{"label": "กรณี 2.2", "fieldname": "used_c22", "fieldtype": "Currency", "width": 110},
		{"label": "กรณี 3", "fieldname": "used_c3", "fieldtype": "Currency", "width": 100},
		{"label": "เงินคงเหลือ", "fieldname": "balance", "fieldtype": "Currency", "width": 110},
		{"label": "ครั้งที่ 1", "fieldname": "trip_1", "fieldtype": "Data", "width": 140},
		{"label": "ครั้งที่ 2", "fieldname": "trip_2", "fieldtype": "Data", "width": 140},
		{"label": "ครั้งที่ 3", "fieldname": "trip_3", "fieldtype": "Data", "width": 140},
		{"label": "ครั้งที่ 4", "fieldname": "trip_4", "fieldtype": "Data", "width": 140},
		{"label": "ครั้งที่ 5", "fieldname": "trip_5", "fieldtype": "Data", "width": 140},
	]

	data = []

	for prof_tag in PROFESSOR_TAGS:
		# 🔥 NEW LOGIC: ALWAYS fetch from GL first - get actual first transfer date (with month/day)
		# Get the validity periods from GL entries
		validity_periods = calculate_validity_periods(prof_tag)

		if not validity_periods:
			# NO fallback to hardcoded dates - if no GL data, skip this professor
			frappe.logger().warning(f"[REPORT] {prof_tag}: NO GL entries found, SKIPPING")
			continue

		# 🔥 Show ALL periods for this professor, not just the last one
		for period_idx, (start_dt, end_dt, trigger_date) in enumerate(validity_periods, 1):
			frappe.logger().info(
				f"[REPORT] {prof_tag}: Processing period {period_idx}/{len(validity_periods)}: {start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')} [Triggered by: {trigger_date.strftime('%Y-%m-%d')}]"
			)

			# 🔥 INCOME: Query transfers that triggered THIS period (debit on trigger_date)
			# EXPENSES: Query all credits within the period date range
			account_pattern = f"%{prof_tag} Travel - IE%"

			# Query 1: INCOME - Only on trigger date (money coming in)
			sql_income = """
                SELECT
                    gle.posting_date,
                    gle.debit,
                    gle.account
                FROM `tabGL Entry` gle
                WHERE 
                    gle.is_cancelled = 0
                    AND gle.posting_date = %s
                    AND gle.debit > 0
                    AND gle.account LIKE %s
            """

			income_list = frappe.db.sql(sql_income, (trigger_date, account_pattern), as_dict=1)

			# Query 2: EXPENSES - Within the validity period (money going out)
			sql_expenses = """
                SELECT
                    gle.posting_date,
                    src.project_template,
                    gle.credit,
                    p.country
                FROM `tabGL Entry` gle
                LEFT JOIN `tabJournal Entry` je 
                    ON gle.voucher_no = je.name AND gle.voucher_type = 'Journal Entry'
                LEFT JOIN `tabTravel Expense request` src 
                    ON je.cheque_no = src.name 
                    OR (src.name IS NOT NULL AND je.user_remark LIKE CONCAT(%s, src.name, %s))
                LEFT JOIN `tabProject` p
                    ON src.relate_project = p.name
                WHERE 
                    gle.is_cancelled = 0
                    AND gle.posting_date BETWEEN %s AND %s
                    AND gle.credit > 0
                    AND gle.account LIKE %s
            """

			expense_list = frappe.db.sql(
				sql_expenses,
				(
					"%",
					"%",
					start_dt,
					end_dt,  # 🔥 Full period range for expenses
					account_pattern,
				),
				as_dict=1,
			)

			frappe.logger().info(
				f"[REPORT] {prof_tag}: Period {period_idx} - Income on {trigger_date.strftime('%Y-%m-%d')}: {len(income_list)} entries | Expenses {start_dt.strftime('%Y-%m-%d')}-{end_dt.strftime('%Y-%m-%d')}: {len(expense_list)} entries"
			)

			# Process results
			total_in = 0
			total_out = 0
			val_c1 = 0
			val_c21 = 0
			val_c22 = 0
			val_c3 = 0
			history_list = []

			# Add income
			for entry in income_list:
				total_in += entry.get("debit") or 0

			# Add expenses and categorize
			for entry in expense_list:
				credit = entry.get("credit") or 0
				total_out += credit

				template = entry.get("project_template") or ""

				if template in T_CAT1:
					val_c1 += credit
				elif template in T_CAT21:
					val_c21 += credit
				elif template in T_CAT22:
					val_c22 += credit
				elif template in T_CAT3:
					val_c3 += credit

				# Add to history if it has credit
				if credit > 0:
					history_list.append(entry)

			# Sort history by posting date
			history_list.sort(key=lambda x: x.get("posting_date") or "")

			# Log summary for this professor
			frappe.logger().info(
				f"[REPORT] {prof_tag}: Summary - In: {total_in:,.2f} | Out: {total_out:,.2f} | Balance: {total_in - total_out:,.2f}"
			)
			frappe.logger().info(
				f"[REPORT] {prof_tag}: Categories - C1: {val_c1:,.2f} | C2.1: {val_c21:,.2f} | C2.2: {val_c22:,.2f} | C3: {val_c3:,.2f}"
			)

			row = {
				"professor": prof_tag,
				"cycle_period": f"{start_dt.strftime('%d/%m/%y')} - {end_dt.strftime('%d/%m/%y')}",
				"budget": total_in,
				"used_total": total_out,
				"used_c1": val_c1,
				"used_c21": val_c21,
				"used_c22": val_c22,
				"used_c3": val_c3,
				"balance": total_in - total_out,
			}

			for i in range(5):
				field_name = f"trip_{i + 1}"
				if i < len(history_list):
					rec = history_list[i]
					c_name = rec.get("country") or "ไม่ระบุ"
					amt = flt(rec.get("credit") or 0)
					row[field_name] = f"{c_name}: {amt:,.0f}"
				else:
					row[field_name] = ""

			# 🔥 Apply budget_period filter if set
			if filtered_years:
				# Extract year range from cycle_period (e.g., "01/08/24 - 31/07/26" → 24-26)
				cycle_period_str = row.get("cycle_period", "")
				try:
					period_parts = cycle_period_str.split(" - ")
					if len(period_parts) == 2:
						start_date_str = period_parts[0]  # "DD/MM/YY"
						end_date_str = period_parts[1]  # "DD/MM/YY"

						# Extract years
						start_year_str = start_date_str.split("/")[2]  # "YY"
						end_year_str = end_date_str.split("/")[2]  # "YY"

						start_year_greg = int(start_year_str) + 2000
						end_year_greg = int(end_year_str) + 2000

						# Check if this period's year range matches the filtered years
						# For "24-26" period to match filter "70-71" (2026-2027):
						# The period should contain those years (24-26 contains 26)
						year_start, year_end = filtered_years

						# Period matches if it overlaps with filtered range
						if start_year_greg <= year_end and end_year_greg >= year_start:
							data.append(row)
							frappe.logger().debug(
								f"[FILTER] Including {prof_tag} {cycle_period_str} ({start_year_greg}-{end_year_greg} overlaps {year_start}-{year_end})"
							)
						else:
							frappe.logger().debug(
								f"[FILTER] Excluding {prof_tag} {cycle_period_str} ({start_year_greg}-{end_year_greg} doesn't overlap {year_start}-{year_end})"
							)
				except Exception as e:
					frappe.logger().warning(
						f"[FILTER] Error parsing cycle_period '{cycle_period_str}': {e}, appending anyway"
					)
					data.append(row)
			else:
				# No filter - include all rows
				data.append(row)

	# Log final summary
	frappe.logger().info("\n" + "=" * 100)
	frappe.logger().info("DASHBOARD SUMMARY REPORT - FINAL VERIFICATION")
	frappe.logger().info("=" * 100)
	frappe.logger().info(f"Total Professors: {len(data)}")
	frappe.logger().info(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
	frappe.logger().info("\nProfessor Summary:")
	frappe.logger().info(
		f"{'Tag':<10} {'Period Start':<15} {'Period End':<15} {'Budget':<15} {'Used':<15} {'Balance':<15}"
	)
	frappe.logger().info("-" * 100)
	for row in data:
		tag = row.get("professor", "")
		period = row.get("cycle_period", "").split(" - ")
		start = period[0] if len(period) > 0 else "N/A"
		end = period[1] if len(period) > 1 else "N/A"
		budget = row.get("budget", 0)
		used = row.get("used_total", 0)
		balance = row.get("balance", 0)
		frappe.logger().info(
			f"{tag:<10} {start:<15} {end:<15} {budget:<15,.2f} {used:<15,.2f} {balance:<15,.2f}"
		)
	frappe.logger().info("=" * 100 + "\n")

	chart = {
		"data": {
			"labels": [d["professor"] for d in data],
			"datasets": [
				{"name": "ใช้ไป", "values": [d["used_total"] for d in data]},
				{"name": "คงเหลือ", "values": [d["balance"] for d in data]},
			],
		},
		"type": "bar",
		"colors": ["#FA4F70", "#4895EF"],
	}

	return columns, data, None, chart
