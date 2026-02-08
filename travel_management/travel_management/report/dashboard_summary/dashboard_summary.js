frappe.query_reports["Dashboard summary"] = {
    "filters": [
        {
            "fieldname": "budget_period",
            "label": __("ช่วงงบประมาณ"),
            "fieldtype": "Select",
            "default": "All Years",
            "options": "" 
        }
    ],

    "onload": function (report) {
        // -------------------------------------------------
        // Create filter options with Gregorian years
        // (Convert Thai year to Gregorian: Thai 69 = Gregorian 2023, Thai 70 = Gregorian 2024, etc.)
        // -------------------------------------------------
        let start_year = 2023;  // Thai year 66
        let end_year = 2041;    // Thai year 84 (can adjust as needed)

        let options_str = "All Years\n";  // 🔥 Add "All Years" option

        for (let y = start_year; y < end_year; y++) {
            let next_y = y + 1;
            let thai_year_start = y - 1957;  // Convert to Thai year (2023 = 66)
            let thai_year_end = next_y - 1957;
            let p_name = `${y}-${next_y} (${thai_year_start}-${thai_year_end})`;
            options_str += p_name + "\n";
        }

        // Update filter options
        let filter_field = report.page.fields_dict['budget_period'];
        if (filter_field) {
            filter_field.df.options = options_str;
            filter_field.refresh(); 
        }

        // 🧹 Remove extra buttons for cleaner UI
        report.page.inner_toolbar.find('.btn-xs').remove();

        // 🎨 Style the filter button with pink color
        setTimeout(function() {
            let $filter = report.page.fields_dict['budget_period'].$wrapper;
            if ($filter) {
                $filter.find('select, .form-control').css({
                    'background-color': '#ffdfe4',
                    'border-color': '#000000',
                    'color': '#8B0045'
                });
            }
        }, 100);
    }
};