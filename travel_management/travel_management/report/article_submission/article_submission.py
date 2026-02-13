# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = build_column()
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