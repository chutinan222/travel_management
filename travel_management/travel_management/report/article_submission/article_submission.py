# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = build_column()
	filters = filters or {}
	filters_for_db = []

	# Fetch Article Submission data using filters
	articles = frappe.get_all(
		"Article Submission",
		fields=[
			"name",
			"article_title",
			"is_scopus",
			"date_paper",
			"related_project",
		],
		filters=filters_for_db or None,
	)

	# Process data
	data = []
	for article in articles:
		# Get authors from child table
		authors = frappe.get_all(
			"Article Author",
			filters={"parent": article["name"]},
			fields=["teacher_name"],
		)
		author_names = ", ".join([a["teacher_name"] for a in authors if a.get("teacher_name")])

		# Get attached professors from child table
		professors = frappe.get_all(
			"Attached Professor",
			filters={"parent": article["name"]},
			fields=["professor_name"],
		)
		professor_names = ", ".join([p["professor_name"] for p in professors if p.get("professor_name")])

		# Filter by instructor name if provided
		if filters.get("instructor_name"):
			instructor_filter = filters.get("instructor_name")
			# Get employee IDs that match the middle_name
			matching_employees = frappe.get_all(
				"Employee", filters={"middle_name": instructor_filter}, fields=["name"]
			)
			matching_ids = [emp["name"] for emp in matching_employees]

			# Check if instructor is in either authors or professors
			author_list = [a["teacher_name"] for a in authors if a.get("teacher_name")]
			professor_list = [p["professor_name"] for p in professors if p.get("professor_name")]

			# Check if any matching employee is in the lists
			found = False
			for emp_id in matching_ids:
				if emp_id in author_list or emp_id in professor_list:
					found = True
					break

			if not found:
				continue

		data.append(
			{
				"article_title": article.get("article_title"),
				"author_name": author_names,
				"professor_name": professor_names,
				"is_scopus": article.get("is_scopus"),
				"date_paper": article.get("date_paper"),
				"related_project": article.get("related_project"),
			}
		)

	return columns, data
def build_column():
	column = [
		{
			"fieldname": "article_title",
			"label": "ชื่อบทความ",
			"fieldtype": "Data",
			"width": 300,
		},
		{
			"fieldname": "author_name",
			"label": "ชื่อผู้แต่ง",
			"fieldtype": "Table",
			"width": 200,
		},
		{
			"fieldname": "professor_name",
			"label": "Related Project",
			"fieldtype": "Table",
			"width": 150,
		},
		{
			"fieldname": "is_scopus",
			"label": "วารสารอยู่ใน Scopus หรือไม่",
			"fieldtype": "Select",
			"width": 150,
		},
		{
			"fieldname": "date_paper",
			"label": "วันที่ตีพิมพ์",
			"fieldtype": "Date",
			"width": 150,
		},
	]
	return column

@frappe.whitelist()
def get_employee_list(doctype, txt, searchfield, start, page_len, filters):
	"""Return employee list with middle_name for filter dropdown"""
	# Add "All" option at the start
	result = [["", "All"]]

	employees = frappe.get_all(
		"Employee",
		filters={
			"docstatus": 0,
		},
		fields=["name", "middle_name", "employee_name"],
		limit_start=start,
		limit_page_length=page_len,
	)

	# Filter by search text (search in middle_name)
	if txt:
		employees = [
			emp
			for emp in employees
			if txt.lower() in (emp.get("middle_name") or "").lower()
			or txt.lower() in emp.get("name", "").lower()
		]

	# Format for dropdown display - show only middle_name
	for emp in employees:
		middle_name = emp.get("middle_name") or ""
		if middle_name:  # Only add if middle_name exists
			result.append([middle_name, middle_name])

	return result
