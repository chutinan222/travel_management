frappe.query_reports["Dashboard summary"] = {
    "filters": [
        {
            "fieldname": "budget_period",
            "label": __("ช่วงงบประมาณ"),
            "fieldtype": "Select",
            "default": "งบ 69-70",
            "options": "" 
        }
    ],

    "onload": function (report) {
        // -------------------------------------------------
        // 1. สร้างตัวเลือกปีอัตโนมัติ (Dropdown Only)
        // -------------------------------------------------
        let start_year = 69;
        let end_year = 90; // อยากได้ถึงปีไหน แก้เลขตรงนี้ได้เลย

        let options_str = "";

        for (let y = start_year; y < end_year; y++) {
            let next_y = y + 1;
            let p_name = `งบ ${y}-${next_y}`;
            options_str += p_name + "\n";
        }

        // 2. อัปเดตตัวเลือกเข้าไปใน Dropdown
        let filter_field = report.page.fields_dict['budget_period'];
        if (filter_field) {
            filter_field.df.options = options_str;
            filter_field.refresh(); 
        }

        // 3. 🧹 คลีนปุ่ม: ลบปุ่มกดด้านบนทิ้งให้หมด (จะได้ไม่รก)
        report.page.inner_toolbar.find('.btn-xs').remove();
    }
};