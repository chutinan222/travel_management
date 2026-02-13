// Copyright (c) 2026, Chilly and contributors
// For license information, please see license.txt

frappe.query_reports["Article Submission"] = {
	"filters": [
		{
			"fieldname": "instructor_name",
			"label": "Instructor Name",
			"fieldtype": "Link",
			"options": "Employee",
			"width": "100px",
			"default": "",
			"get_query": function() {
				return {
					"query": "travel_management.travel_management.report.article_submission.article_submission.get_employee_list"
				}
			}
		}
	]
};
