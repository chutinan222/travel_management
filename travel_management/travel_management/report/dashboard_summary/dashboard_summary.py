# Copyright (c) 2026, Administrator and contributors


from datetime import datetime, timedelta
import re

import frappe

from frappe.utils import flt, getdate


# =========================================================

# SPLIT PERIOD BY BUDGET TRANSFER (120000)

# =========================================================


def calculate_periods_by_budget(tag):

	account_exact = f"{tag} Travel - IE"

	sql = """
        SELECT
            posting_date,
            debit,
            creation,
            voucher_no,
            name
        FROM `tabGL Entry`
        WHERE
            is_cancelled = 0
            AND posting_date <= CURDATE()
            AND account = %s
        ORDER BY
            posting_date ASC,
            voucher_no ASC,
            creation ASC,
            name ASC
    """

	rows = frappe.db.sql(sql, (account_exact,), as_dict=1)

	if not rows:
		return []

	periods = []
	current_start = None

	for r in rows:
		dt = getdate(r.get("posting_date"))
		debit = flt(r.get("debit"))

		# ⭐ เงินเข้า = เปิดรอบใหม่
		if debit == 120000:
			# ปิดรอบก่อนหน้า
			if current_start:
				end_date = dt
				periods.append((current_start, end_date, current_start))

			# เปิดรอบใหม่
			current_start = dt

	# ⭐ รอบสุดท้าย
	if current_start:
		periods.append(
			(
				current_start,
				current_start + timedelta(days=365 * 2 - 1),
				current_start,
			)
		)

	return periods


# =========================================================

# API: Get Professor Tags for Filter

# =========================================================


@frappe.whitelist()
def get_professor_tags():
	"""Return list of professor tags for filter dropdown"""
	sql_get_tags = """
        SELECT DISTINCT 
            SUBSTRING_INDEX(account, ' ', 1) as tag
        FROM `tabGL Entry`
        WHERE 
            is_cancelled = 0
            AND posting_date <= CURDATE()
            AND account LIKE '% Travel - IE%'
            AND SUBSTRING_INDEX(account, ' ', 1) != 'IE'
        ORDER BY tag ASC
    """
	tag_results = frappe.db.sql(sql_get_tags, as_dict=1)
	return [row.get("tag") for row in tag_results if row.get("tag")]


# =========================================================

# MAIN REPORT

# =========================================================


def execute(filters=None):
	# ดึง Tag อาจารย์ทั้งหมด

	sql_get_tags = """

        SELECT DISTINCT 

            SUBSTRING_INDEX(account, ' ', 1) as tag

        FROM `tabGL Entry`

        WHERE 

            is_cancelled = 0

            AND posting_date <= CURDATE()

            AND account LIKE '% Travel - IE%'

            AND SUBSTRING_INDEX(account, ' ', 1) != 'IE'

        ORDER BY tag ASC

    """

	tag_results = frappe.db.sql(sql_get_tags, as_dict=1)

	PROFESSOR_TAGS = [row.get("tag") for row in tag_results if row.get("tag")]

	# ⭐ Filter by professor tag if selected
	filter_professor = None
	if filters:
		filter_professor = filters.get("professor_tag")
		if filter_professor and filter_professor != "ทั้งหมด":
			PROFESSOR_TAGS = [tag for tag in PROFESSOR_TAGS if tag == filter_professor]

	columns = [
		{"label": "อาจารย์ (Tag)", "fieldname": "professor", "fieldtype": "Data", "width": 100},
		{"label": "รอบวันที่", "fieldname": "cycle_period", "fieldtype": "Data", "width": 180},
		{"label": "เงินเข้า", "fieldname": "budget", "fieldtype": "Currency", "width": 110},
		{"label": "ยอดใช้รวม", "fieldname": "used_total", "fieldtype": "Currency", "width": 110},
		{"label": "กรณี 1", "fieldname": "used_c1", "fieldtype": "Currency", "width": 110},
		{"label": "กรณี 2.1", "fieldname": "used_c21", "fieldtype": "Currency", "width": 110},
		{"label": "กรณี 2.2", "fieldname": "used_c22", "fieldtype": "Currency", "width": 110},
		{"label": "กรณี 3", "fieldname": "used_c3", "fieldtype": "Currency", "width": 100},
		{"label": "เบิกคืน", "fieldname": "withdrawn", "fieldtype": "Currency", "width": 110},
		{"label": "เงินคงเหลือ", "fieldname": "balance", "fieldtype": "Currency", "width": 110},
		{"label": "ครั้งที่ 1", "fieldname": "trip_1", "fieldtype": "Data", "width": 140},
		{"label": "ครั้งที่ 2", "fieldname": "trip_2", "fieldtype": "Data", "width": 140},
		{"label": "ครั้งที่ 3", "fieldname": "trip_3", "fieldtype": "Data", "width": 140},
		{"label": "ครั้งที่ 4", "fieldname": "trip_4", "fieldtype": "Data", "width": 140},
		{"label": "ครั้งที่ 5", "fieldname": "trip_5", "fieldtype": "Data", "width": 140},
	]

	# ⭐ Parse budget_period filter to get year range
	# Format: "2025-2026 (68-69)" or "All Years"
	filter_start_year = None
	filter_end_year = None

	if filters:
		budget_period = filters.get("budget_period", "All Years")
		if budget_period and budget_period != "All Years":
			# Parse format "2025-2026 (68-69)"
			year_match = re.match(r"(\d{4})-(\d{4})", budget_period)
			if year_match:
				filter_start_year = int(year_match.group(1))
				filter_end_year = int(year_match.group(2))

	data = []

	for prof_tag in PROFESSOR_TAGS:
		validity_periods = calculate_periods_by_budget(prof_tag)

		if not validity_periods:
			continue

		# ⭐ FIXED: Use EXACT account match, not LIKE pattern
		# This prevents matching "IE Central Travel - IE" for tag "AL"
		account_exact = f"{prof_tag} Travel - IE"

		for start_dt, end_dt, trigger_date in validity_periods:
			# ⭐ Filter by budget period (year range)
			# If filter is set, skip cycles outside the selected year range
			if filter_start_year and filter_end_year:
				cycle_start_year = start_dt.year
				# Check if cycle falls within selected fiscal year range
				# Cycle should start in or between filter_start_year and filter_end_year
				if not (filter_start_year <= cycle_start_year <= filter_end_year):
					continue

			# 1. หาเงินเข้า (Budget) - only from trigger date

			sql_income = """

                SELECT debit

                FROM `tabGL Entry`

                WHERE 

                    is_cancelled = 0

                    AND posting_date = %s

                    AND posting_date <= CURDATE()

                    AND debit = 120000

                    AND account = %s

            """

			income_list = frappe.db.sql(sql_income, (trigger_date, account_exact), as_dict=1)

			total_in = sum((d.get("debit") or 0) for d in income_list)

			# ⭐ FIX: Use <= end_dt to INCLUDE expenses on period end date
			# Expenses = sum of ALL credits within the cycle period
			# Period 1: posting_date > start AND posting_date <= end
			# Period 2: starts the day after Period 1 ends

			sql_balance = """

                SELECT 

                    COALESCE(SUM(CASE WHEN debit > 0 THEN debit ELSE 0 END), 0) as total_debit,

                    COALESCE(SUM(CASE WHEN credit > 0 THEN credit ELSE 0 END), 0) as total_credit

                FROM `tabGL Entry` gle

                WHERE 

                    gle.is_cancelled = 0

                    AND gle.posting_date > %s

                    AND gle.posting_date <= %s

                    AND gle.posting_date <= CURDATE()

                    AND gle.account = %s

            """

			balance_result = frappe.db.sql(sql_balance, (start_dt, end_dt, account_exact), as_dict=1)

			total_debit_in_period = balance_result[0].get("total_debit") or 0

			total_credit_in_period = balance_result[0].get("total_credit") or 0

			# ⭐ Check if there's a next 120,000 budget transfer AFTER this period
			# If yes: last credit before next budget = withdrawn, other credits = used
			# If no: check if there are "return money to system" credits → those are withdrawn
			sql_next_budget = """

                SELECT COUNT(*) as has_next FROM `tabGL Entry`

                WHERE 

                    is_cancelled = 0

                    AND posting_date >= %s

                    AND posting_date <= CURDATE()

                    AND debit = 120000

                    AND account = %s

            """

			next_budget = frappe.db.sql(sql_next_budget, (end_dt, account_exact), as_dict=1)

			has_next_period = (next_budget[0].get("has_next") or 0) > 0 if next_budget else False

			# Get expense history FIRST to check for "return money to system"
			sql_expense_history = """

                SELECT

                    gle.posting_date,

                    gle.credit,

                    ter.project_template,

                    ter.from_template,

                    je.user_remark

                FROM `tabGL Entry` gle

                LEFT JOIN `tabJournal Entry` je 

                    ON gle.voucher_no = je.name

                LEFT JOIN `tabTravel Expense request` ter 

                    ON LOCATE('TER-', je.user_remark) > 0

                    AND SUBSTRING_INDEX(

                        SUBSTRING(je.user_remark, LOCATE('TER-', je.user_remark), 10),

                        '|',

                        1

                    ) = ter.name

                WHERE 

                    gle.is_cancelled = 0

                    AND gle.posting_date > %s

                    AND gle.posting_date <= %s

                    AND gle.posting_date <= CURDATE()

                    AND gle.credit > 0

                    AND gle.account = %s

            """

			expense_list = frappe.db.sql(
				sql_expense_history,
				(start_dt, end_dt, account_exact),
				as_dict=1,
			)

			# ⭐ NEW: Separate "return money to system" credits from regular expenses
			withdrawn_from_refund = 0  # Sum of "return money to system" credits
			other_credits_total = 0  # Sum of other template credits

			for entry in expense_list:
				credit = entry.get("credit") or 0
				from_template = (entry.get("from_template") or "").strip()

				if from_template == "return money to system":
					withdrawn_from_refund += credit
				else:
					other_credits_total += credit

			# ⭐ Calculate withdrawn_amount and total_out based on template type
			withdrawn_amount = 0
			total_out = 0

			if has_next_period:
				# ⭐ Next period exists → check if last credit is refund
				# If no refund: last credit = withdrawn, rest = used
				# If refund exists: use refund as withdrawn
				if withdrawn_from_refund > 0:
					withdrawn_amount = withdrawn_from_refund
					total_out = other_credits_total
				else:
					# Old logic: last non-refund credit = withdrawn
					sql_last_credit = """

                        SELECT credit

                        FROM `tabGL Entry`

                        WHERE 

                            is_cancelled = 0

                            AND posting_date > %s

                            AND posting_date <= %s

                            AND posting_date <= CURDATE()

                            AND credit > 0

                            AND account = %s

                        ORDER BY posting_date DESC, creation DESC

                        LIMIT 1

                    """

					last_credit_result = frappe.db.sql(
						sql_last_credit, (start_dt, end_dt, account_exact), as_dict=1
					)

					withdrawn_amount = (last_credit_result[0].get("credit") or 0) if last_credit_result else 0

					total_out = total_credit_in_period - withdrawn_amount

			else:
				# ⭐ No next period yet
				# If refund exists: refund = withdrawn, rest = used
				# If no refund: all credits = used, withdrawn = 0
				if withdrawn_from_refund > 0:
					withdrawn_amount = withdrawn_from_refund
					total_out = other_credits_total
				else:
					withdrawn_amount = 0
					total_out = total_credit_in_period

			# Balance = remaining after used and withdrawn = budget - used - withdrawn
			balance = total_in - total_out - withdrawn_amount

			val_c1 = val_c21 = val_c22 = val_c3 = 0

			history_list = []

			for entry in expense_list:
				credit = entry.get("credit") or 0

				# ⭐ Check from_template FIRST before categorizing
				# If it's "return money to system", skip normal categorization
				from_template = (entry.get("from_template") or "").strip()

				if from_template == "return money to system":
					# This is a refund/withdrawal - don't categorize into cases
					pass

				else:
					# ⭐ FIX 2: Use project_template from Travel Expense Request
					# Convert to lowercase for flexible keyword matching
					template = (entry.get("project_template") or "").strip().lower()

					# --- Logic for categorization (Keyword matching) ---

					# Case 1: Domestic travel with disbursement (ในประเทศ + เบิกภาค)

					if "ในประเทศ" in template and "เบิกภาค" in template:
						val_c1 += credit

					# Case 2.2: Overseas + Presenting + 60000 limit (specific amount)

					# Check most specific condition first

					elif (
						"ต่างประเทศ" in template
						and "นำเสนอ" in template
						and (
							"เกิน 60000" in template
							or "เกิน 60,000" in template
							or "ไม่เกิน 60000" in template
							or "ไม่เกิน 60,000" in template
						)
					):
						val_c22 += credit

					# Case 2.1: Overseas + Presenting (general)

					elif "ต่างประเทศ" in template and "นำเสนอ" in template:
						val_c21 += credit

					# Case 3: Overseas + NOT Presenting (ไม่นำเสนอ)

					elif "ต่างประเทศ" in template and "ไม่นำเสนอ" in template:
						val_c3 += credit

					else:
						# Uncategorized case (enable line below for debugging)

						# frappe.errprint(f"Uncategorized: {template} | {credit}")

						pass

				# -----------------------------------------------

				if credit > 0:
					history_list.append(entry)

			# เรียงลำดับประวัติการเดินทางตามวันที่

			history_list.sort(key=lambda x: x.get("posting_date") or "")

			period_label = f"{start_dt.strftime('%d/%m/%y')} - {end_dt.strftime('%d/%m/%y')}"

			row = {
				"professor": prof_tag,
				"cycle_period": period_label,
				"budget": total_in,
				"used_total": total_out,
				"used_c1": val_c1,
				"used_c21": val_c21,
				"used_c22": val_c22,
				"used_c3": val_c3,
				"withdrawn": withdrawn_amount,
				"balance": balance,
			}

			# ใส่ประวัติ 5 ทริปล่าสุด

			for i in range(5):
				field_name = f"trip_{i + 1}"

				if i < len(history_list):
					rec = history_list[i]

					# Extract location and year from remarks
					remarks = rec.get("user_remark") or ""
					remarks_clean = remarks.strip()

					location = "ไม่ระบุ"
					year = ""

					# Check from_template first
					from_template = (rec.get("from_template") or "").strip()

					if from_template == "return money to system":
						# Display as "เบิกเงินคืน" for refunds
						location = "เบิกเงินคืน"
					else:
						# Try to extract year (2023-2026) first
						year_match = re.search(r"(202[3-6])", remarks_clean)
						if year_match:
							year = year_match.group(1)

						# Try to extract location from parentheses
						# Skip numeric-only parentheses (semester codes like "67", "68")
						if "(" in remarks_clean and ")" in remarks_clean:
							# Get all parentheses content
							all_matches = re.findall(r"\(([^)]+)\)", remarks_clean)
							for match_text in all_matches:
								match_text = match_text.strip()
								# Skip if it's only a number (semester code) or year
								if match_text and not match_text.isdigit() and year not in match_text:
									location = match_text
									break

					# Build display string with location and year
					if year and year != "":
						display_loc = f"{location} {year}"
					else:
						display_loc = location

					amt = flt(rec.get("credit") or 0)

					row[field_name] = f"{display_loc}: {amt:,.0f}"

				else:
					row[field_name] = ""

			data.append(row)

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
