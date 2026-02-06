# Copyright (c) 2026, Administrator and contributors

from datetime import datetime
import frappe
from frappe.utils import flt


def add_years(date_obj, years):
	try:
		return date_obj.replace(year=date_obj.year + years)
	except ValueError:
		return date_obj.replace(month=2, day=28, year=date_obj.year + years)


def execute(filters=None):
	if not filters:
		filters = {}

	period = filters.get("budget_period", "งบ 69-70")

	PERIOD_SHIFT = {
		"งบ 69-70": 0,
		"งบ 70-71": 2,
		"งบ 71-72": 4,
		"งบ 72-73": 6,
		"งบ 73-74": 8,
	}

	shift_year = PERIOD_SHIFT.get(period, 0)

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
	# 🟡 รายชื่อ TAG
	# ---------------------------------------------------------
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

	cycle_dates = {
		"AS": ("2025-11-15", "2027-11-14"),
		"WI": ("2024-03-07", "2026-03-06"),
		"WW": ("2025-11-15", "2027-11-14"),
		"KG": ("2025-11-13", "2027-11-12"),
		"ST": ("2025-12-03", "2027-12-02"),
		"RC": ("2025-04-07", "2027-04-06"),
		"WL": ("2024-03-07", "2026-03-06"),
		"SR": ("2024-09-05", "2026-09-04"),
		"WR": ("2024-11-15", "2026-11-14"),
		"CN": ("2024-12-08", "2026-12-07"),
		"CB": ("2025-09-14", "2027-09-13"),
		"WP": ("2024-03-17", "2026-03-16"),
		"US": ("2024-11-09", "2026-11-08"),
		"AC": ("2024-11-15", "2026-11-14"),
		"KR": ("2024-11-15", "2026-11-14"),
		"WS": ("2024-03-07", "2026-03-06"),
		"SN": ("2025-11-15", "2027-11-14"),
		"NR": ("2024-11-19", "2026-11-18"),
		"CS": ("2025-10-29", "2027-10-28"),
		"PC": ("2025-11-15", "2027-11-14"),
		"AL": ("2025-09-15", "2027-09-14"),
		"WM": ("2025-03-03", "2027-03-02"),
		"TP": ("2025-05-05", "2027-05-04"),
		"RP": ("2025-12-13", "2027-12-12"),
		"KP": ("2025-03-26", "2027-03-25"),
		"AB": ("2025-01-13", "2027-01-12"),
		"PO": ("2024-11-16", "2026-11-15"),
		"TO": ("2024-06-10", "2026-06-09"),
		"PM": ("2025-03-16", "2027-03-15"),
		"ND": ("2024-11-10", "2026-11-09"),
		"NP": ("2025-05-06", "2027-05-05"),
	}

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
		if prof_tag not in cycle_dates:
			continue

		base_start = datetime.strptime(cycle_dates[prof_tag][0], "%Y-%m-%d").date()
		base_end = datetime.strptime(cycle_dates[prof_tag][1], "%Y-%m-%d").date()
		start_dt = add_years(base_start, shift_year)
		end_dt = add_years(base_end, shift_year)

		# -------------------------------------------------------------
		# 🔥 แก้ไขชื่อ Field: relate_project (ไม่มีตัว d)
		# -------------------------------------------------------------
		sql_summary = """
            SELECT
                IFNULL(SUM(gle.debit), 0) as total_in,
                IFNULL(SUM(gle.credit), 0) as total_out,
                IFNULL(SUM(CASE WHEN src.project_template IN %(t_c1)s THEN gle.credit ELSE 0 END), 0) as val_c1,
                IFNULL(SUM(CASE WHEN src.project_template IN %(t_c21)s THEN gle.credit ELSE 0 END), 0) as val_c21,
                IFNULL(SUM(CASE WHEN src.project_template IN %(t_c22)s THEN gle.credit ELSE 0 END), 0) as val_c22,
                IFNULL(SUM(CASE WHEN src.project_template IN %(t_c3)s THEN gle.credit ELSE 0 END), 0) as val_c3
            FROM `tabGL Entry` gle
            LEFT JOIN `tabJournal Entry` je 
                ON gle.voucher_no = je.name AND gle.voucher_type = 'Journal Entry'
            LEFT JOIN `tabTravel Expense request` src 
                ON je.cheque_no = src.name 
                OR (src.name IS NOT NULL AND je.user_remark LIKE CONCAT('%%', src.name, '%%'))
            
            -- 🔥 relate_project
            LEFT JOIN `tabProject` p
                ON src.relate_project = p.name

            WHERE 
                gle.is_cancelled = 0
                AND gle.posting_date BETWEEN %(start)s AND %(end)s
                AND gle.account LIKE '%%Travel - IE' 
                AND (
                    p._user_tags LIKE CONCAT('%%,', %(tag)s, ',%%')
                    OR je._user_tags LIKE CONCAT('%%,', %(tag)s, ',%%')
                    OR gle.account LIKE CONCAT('%%', %(tag)s, ' Travel%%')
                )
        """

		sql_history = """
            SELECT 
                p.country as country_name, 
                gle.credit as amount
            FROM `tabGL Entry` gle
            LEFT JOIN `tabJournal Entry` je 
                ON gle.voucher_no = je.name AND gle.voucher_type = 'Journal Entry'
            LEFT JOIN `tabTravel Expense request` src 
                ON je.cheque_no = src.name 
                OR (src.name IS NOT NULL AND je.user_remark LIKE CONCAT('%%', src.name, '%%'))
            
            -- 🔥 relate_project
            LEFT JOIN `tabProject` p
                ON src.relate_project = p.name

            WHERE 
                gle.is_cancelled = 0
                AND gle.credit > 0 
                AND gle.posting_date BETWEEN %(start)s AND %(end)s
                AND gle.account LIKE '%%Travel - IE'
                AND (
                    p._user_tags LIKE CONCAT('%%,', %(tag)s, ',%%')
                    OR je._user_tags LIKE CONCAT('%%,', %(tag)s, ',%%')
                    OR gle.account LIKE CONCAT('%%', %(tag)s, ' Travel%%')
                )
            ORDER BY gle.posting_date ASC
        """

		params = {
			"tag": prof_tag,
			"start": start_dt,
			"end": end_dt,
			"t_c1": safe_tuple(T_CAT1),
			"t_c21": safe_tuple(T_CAT21),
			"t_c22": safe_tuple(T_CAT22),
			"t_c3": safe_tuple(T_CAT3),
		}

		# รัน Query
		res_list = frappe.db.sql(sql_summary, params, as_dict=1)
		res = res_list[0] if res_list else {}
		history_list = frappe.db.sql(sql_history, params, as_dict=1)

		total_in = res.get("total_in") or 0
		total_out = res.get("total_out") or 0

		row = {
			"professor": prof_tag,
			"cycle_period": f"{start_dt.strftime('%d/%m/%y')} - {end_dt.strftime('%d/%m/%y')}",
			"budget": total_in,
			"used_total": total_out,
			"used_c1": res.get("val_c1") or 0,
			"used_c21": res.get("val_c21") or 0,
			"used_c22": res.get("val_c22") or 0,
			"used_c3": res.get("val_c3") or 0,
			"balance": total_in - total_out,
		}

		for i in range(5):
			field_name = f"trip_{i + 1}"
			if i < len(history_list):
				rec = history_list[i]
				c_name = rec.get("country_name") or "ไม่ระบุ"
				amt = flt(rec.get("amount"))
				row[field_name] = f"{c_name}: {amt:,.0f}"
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
