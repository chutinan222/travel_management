frappe.query_reports["Dashboard summary"] = {
    "filters": [
        {
            "fieldname": "budget_period",
            "label": __("ช่วงงบประมาณ"),
            "fieldtype": "Select",
            "default": "All Years",
            "options": "" 
        },
        {
            "fieldname": "professor_tag",
            "label": __("อาจารย์"),
            "fieldtype": "Select",
            "default": "ทั้งหมด",
            "options": "ทั้งหมด"
        }
    ],

    "after_datatable_render": function(datatable_obj) {
        // Add description text above the table
        let $report = $('.frappe-list');
        let $message_container = $('.report-message-container');
        
        if ($message_container.length === 0) {
            let message_html = `
                <div class="report-message-container" style="
                    background: linear-gradient(135deg, #e0eff9 0%, #fff3cc 100%);
                    border: 1px solid #0a131c;
                    border-radius: 8px;
                    padding: 12px 20px;
                    margin-bottom: 15px;
                    font-size: 13px;
                    line-height: 1.4;
                ">
                    <div style="font-weight: bold; color: #171307;
                     margin-bottom: 6px; font-size: 14px;">
                        กรณีการใช้ Template:
                    </div>
                    <div style="color: #0f0e0b;">
                        <strong style="color: #303a71;">กรณีที่ 1:
                        </strong> Template ในประเทศ (เบิกภาค)<br>
                        <strong style="color: #303a71;">กรณีที่ 2.1:
                        </strong> Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน อยู่ในฐาน Scopus<br>
                        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                        &nbsp;&nbsp;Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน (ขอทุนคณะ/มช.)<br>
                        <strong style="color: #303a71;">กรณีที่ 2.2:
                        </strong> Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน ไม่เกิน 60,000 ไม่อยู่ในฐาน Scopus<br>
                        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                        Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน เกิน 60,000 ไม่อยู่ในฐาน Scopus<br>
                        <strong style="color: #303a71;">กรณีที่ 3:
                        </strong> Template ต่างประเทศ (เบิกภาค) ไม่นำเสนอผลงาน ไม่เกิน 40,000 บาท
                    </div>
                </div>
            `;
            
            // Insert before the datatable
            $('.datatable').before(message_html);
        }

        // 🔤 Make table font smaller
        $('.datatable').css('font-size', '12px');
        $('.dt-cell').css('font-size', '12px');
    },

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

        // 🔥 Load professor options from server
        frappe.call({
            method: 'travel_management.travel_management.report.dashboard_summary.dashboard_summary.get_professor_tags',
            async: false,
            callback: function(r) {
                if (r.message) {
                    let prof_options = "ทั้งหมด\n" + r.message.join("\n");
                    let prof_filter = report.page.fields_dict['professor_tag'];
                    if (prof_filter) {
                        prof_filter.df.options = prof_options;
                        prof_filter.refresh();
                    }
                }
            }
        });

        // 🧹 Remove extra buttons for cleaner UI
        report.page.inner_toolbar.find('.btn-xs').remove();

        // 🎨 Style the filter buttons
        setTimeout(function() {
            let $filter = report.page.fields_dict['budget_period'].$wrapper;
            if ($filter) {
                $filter.find('select, .form-control').css({
                    'background-color': '#fbfdff',
                    'border-color': '#000000',
                    'color': '#00078b'
                });
            }
            let $prof_filter = report.page.fields_dict['professor_tag'].$wrapper;
            if ($prof_filter) {
                $prof_filter.find('select, .form-control').css({
                    'background-color': '#fbfdff',
                    'border-color': '#000000',
                    'color': '#00078b'
                });
            }
        }, 100);
    }
};