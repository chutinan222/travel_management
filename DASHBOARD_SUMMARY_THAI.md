# รายงาน Dashboard Summary - เอกสารเทคนิค

## ภาพรวม

รายงานนี้แสดงงบประมาณค่าใช้จ่ายการเดินทางสำหรับอาจารย์แต่ละคน พร้อมการแบ่งประเภทค่าใช้จ่ายโดยอัตโนมัติ โดยคำนวณช่วงวันที่ถูกต้องตามจำนวนเงินโอนเข้า และแบ่งค่าใช้จ่ายออกเป็น 4 กรณี

---

## ตำแหน่งไฟล์

```
travel_management/travel_management/report/dashboard_summary/dashboard_summary.py
```

---

## สถาปัตยกรรม

### ฟังก์ชันหลัก 2 ตัว

#### 1. `calculate_periods_by_budget(tag)`

**บรรทัด: 8-45**

**วัตถุประสงค์**: คำนวณช่วงวันที่ถูกต้องสำหรับอาจารย์โดยอิงจากการโอนเงิน 120,000 บาท

**อัลกอริทึม**:

```
1. ค้นหา GL Entry สำหรับการจ่ายเงิน 120,000 บาท (Debit)
2. ดึงวันที่ลงรายการตามลำดับเวลา
3. สำหรับแต่ละวันที่โอนเงิน สร้างช่วงวันที่ถูกต้อง:
   - ช่วงที่ 1: วันโอนแรก → 2 ปีต่อมา (หรือจนกว่าจะมีการโอนครั้งถัดไป)
   - ช่วงที่ 2+: แต่ละการโอนครั้งต่อไปจะสร้างช่วง 2 ปีใหม่
4. ส่งกลับลิสต์ของ (start_date, end_date, trigger_date)
```

**ตัวอย่าง**:

```
โอนเงิน 1: 1 สิงหาคม 2567 → ช่วง 1: 1 สิงหาคม 2567 ถึง 31 กรกฎาคม 2569
โอนเงิน 2: 15 กันยายน 2568 → ช่วง 2: 15 กันยายน 2568 ถึง 14 กันยายน 2570
โอนเงิน 3: 20 ตุลาคม 2569 → ช่วง 3: 20 ตุลาคม 2569 ถึง 19 ตุลาคม 2571
```

**คำสั่ง SQL ที่ใช้**:

```sql
SELECT posting_date
FROM `tabGL Entry`
WHERE is_cancelled = 0
  AND debit = 120000
  AND account LIKE '%AB Travel - IE%'  -- สำหรับอาจารย์ "AB"
ORDER BY posting_date ASC
```

---

#### 2. `execute(filters)` - ฟังก์ชันรายงานหลัก

**บรรทัด: 50-220**

**วัตถุประสงค์**: สร้างรายงาน Dashboard ที่สมบูรณ์พร้อมการแบ่งค่าใช้จ่าย

---

## ขั้นตอนการดำเนินการ

### ขั้นตอนที่ 1: กำหนดประเภทค่าใช้จ่าย

**บรรทัด: 51-67**

```python
T_CAT1 = ["Template ในประเทศ (เบิกภาค)"]
         # ค่าใช้จ่ายการเดินทางในประเทศ

T_CAT21 = [
    "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน",
    "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน (ขอทุนคณะ/มช.)"
]
          # ต่างประเทศกับนำเสนอผลงาน

T_CAT22 = [
    "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน ไม่เกิน 60000",
    "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน เกิน 60000"
]
          # ต่างประเทศกับขีดจำกัดจำนวนเงิน

T_CAT3 = ["Template ต่างประเทศ (เบิกภาค) ไม่นำเสนอผลงาน ไม่เกิน 40,000 บาท"]
         # ต่างประเทศโดยไม่นำเสนอผลงาน
```

### ขั้นตอนที่ 2: ดึงข้อมูลแท็กอาจารย์ทั้งหมด

**บรรทัด: 69-81**

**คำสั่ง SQL**:

```sql
SELECT DISTINCT SUBSTRING_INDEX(account, ' ', 1) as tag
FROM `tabGL Entry`
WHERE is_cancelled = 0
  AND account LIKE '% Travel - IE%'
  AND SUBSTRING_INDEX(account, ' ', 1) != 'IE'
ORDER BY tag ASC
```

**ผลลัพธ์**: `['AB', 'AC', 'AL', 'AP', 'AS', 'CB', ...]`

**ตรรกะ**:

- ดึงคำแรกจากชื่อบัญชี (เช่น "AB Travel - IE" → "AB")
- กรองออก "IE" (ไม่ใช่แท็กอาจารย์)
- เรียงลำดับตัวอักษร

### ขั้นตอนที่ 3: กำหนดคอลัมน์รายงาน

**บรรทัด: 83-97**

```
อาจารย์ (Tag) | รอบวันที่ | เงินเข้า | ยอดใช้รวม |
กรณี 1 | กรณี 2.1 | กรณี 2.2 | กรณี 3 | เงินคงเหลือ |
ครั้งที่ 1-5 (ประวัติการเดินทาง)
```

### ขั้นตอนที่ 4: ลูปหลัก - ประมวลผลอาจารย์แต่ละคน

**บรรทัด: 101-209**

```python
for prof_tag in PROFESSOR_TAGS:  # เช่น "AB", "AC"

    # ดึงช่วงวันที่ถูกต้องทั้งหมดสำหรับอาจารย์
    validity_periods = calculate_periods_by_budget(prof_tag)

    # ประมวลผลแต่ละช่วง
    for start_dt, end_dt, trigger_date in validity_periods:

        # คำนวณเงินเข้า
        # คำนวณค่าใช้จ่าย
        # แบ่งประเภทตามชนิด
        # สร้างแถวรายงาน
```

---

## การประมวลผลโดยละเอียดสำหรับแต่ละช่วง

### A. การคำนวณเงินเข้า

**บรรทัด: 113-118**

```python
sql_income = """
    SELECT debit
    FROM `tabGL Entry`
    WHERE is_cancelled = 0
      AND posting_date = %s          # trigger_date เท่านั้น
      AND debit = 120000
      AND account LIKE %s            # "%AB Travel - IE%"
"""

total_in = sum(d["debit"] for d in income_list)
```

**จุดสำคัญ**: นับเฉพาะเงินที่ได้รับในวันที่โอนเงิน (วันที่โอนเข้า)

### B. การคำนวณค่าใช้จ่ายและแบ่งประเภท

**บรรทัด: 125-142**

```python
sql_expenses = """
    SELECT
        gle.posting_date,
        gle.credit,                    # จำนวนเงินที่ใช้
        src.name as travel_name,
        proj.project_template,         # ⭐ ชื่อ Template สำหรับแบ่งประเภท
        proj.country
    FROM `tabGL Entry` gle
    LEFT JOIN `tabJournal Entry` je
        ON gle.voucher_no = je.name
        AND gle.voucher_type = 'Journal Entry'
    LEFT JOIN `tabTravel Expense request` src
        ON je.cheque_no = src.name
    LEFT JOIN `tabProject` proj
        ON src.relate_project = proj.name
    WHERE
        gle.is_cancelled = 0
        AND gle.posting_date BETWEEN %s AND %s   # ช่วงวันที่เต็ม
        AND gle.credit > 0
        AND gle.account LIKE %s                  # "%AB Travel - IE%"
"""
```

**ขั้นตอนการไหลของข้อมูล**:

```
GL Entry (credit > 0)
    ↓
Journal Entry (ผ่าน voucher_no)
    ↓
Travel Expense Request (ผ่าน cheque_no)
    ↓
Project (ผ่าน relate_project)
    ↓
project_template (สำหรับแบ่งประเภท)
```

### C. การกำหนดประเภท

**บรรทัด: 149-161**

```python
for entry in expense_list:
    credit = entry.get("credit") or 0
    template = entry.get("project_template") or ""

    if template in T_CAT1:
        val_c1 += credit
    elif template in T_CAT21:
        val_c21 += credit
    elif template in T_CAT22:
        val_c22 += credit
    elif template in T_CAT3:
        val_c3 += credit
```

**ยอดรวม**:

- `total_out` = val_c1 + val_c21 + val_c22 + val_c3
- `balance` = total_in - total_out

### D. ประวัติการเดินทาง

**บรรทัด: 166-179**

```python
for i in range(5):
    field_name = f"trip_{i + 1}"
    if i < len(history_list):
        rec = history_list[i]
        c_name = rec.get("country") or "ไม่ระบุ"
        amt = flt(rec.get("credit") or 0)
        row[field_name] = f"{c_name}: {amt:,.0f}"
        # ตัวอย่าง: "Thailand: 50,000"
```

**เรียงตามลำดับ**: posting_date (ตามลำดับเวลา)

### E. สร้างแถวรายงาน

**บรรทัด: 183-194**

```python
row = {
    "professor": "AB",
    "cycle_period": "01/08/24 - 31/07/26",
    "budget": 120000,
    "used_total": 95000,
    "used_c1": 30000,
    "used_c21": 45000,
    "used_c22": 20000,
    "used_c3": 0,
    "balance": 25000,
    "trip_1": "Thailand: 50,000",
    "trip_2": "Japan: 30,000",
    ...
}
```

---

## ขั้นตอนที่ 5: ผลลัพธ์

**บรรทัด: 211-220**

ส่งกลับ:

```python
(
    columns,      # คำจำกัดความคอลัมน์
    data,         # แถวทั้งหมดจากอาจารย์และช่วงทั้งหมด
    None,         # ข้อความ (ไม่ใช้)
    chart         # แผนภูมิแท่ง: ใช้ไป vs คงเหลือต่ออาจารย์
)
```

---

## แนวคิดหลัก

### 1. ช่วงวันที่ถูกต้องแบบไดนามิก

- **ไม่ได้เขียนล่วงหน้า** - ขึ้นอยู่กับการโอนเงิน 120,000 บาท จริงๆ ใน GL Entry
- **ช่วงหลายรอบต่ออาจารย์** - แต่ละการโอนเงินสร้างช่วงใหม่
- **ระยะเวลา 2 ปี** - แต่ละช่วงยาวประมาณ 2 ปี

### 2. แท็กอาจารย์แบบไดนามิก

- **ดึงมาจาก GL Entry accounts** - ไม่ได้เขียนล่วงหน้า
- **อัปเดตอัตโนมัติ** - อาจารย์คนใหม่ปรากฏเองโดยอัตโนมัติ
- **กรองออก** - ยกเว้นแท็ก "IE"

### 3. การแบ่งประเภทค่าใช้จ่าย

- **ขึ้นอยู่กับ Template** - ใช้ฟิลด์ project_template
- **4 ประเภทกรณี** - ขึ้นอยู่กับประเภทการเดินทางและการนำเสนอผลงาน
- **อัตโนมัติ** - ไม่ต้องกำหนดเอง

### 4. ลิงก์ข้อมูล

```
GL Entry (credit)
  → Journal Entry
  → Travel Expense Request
  → Project
  → project_template
```

---

## ตัวอย่างผลลัพธ์รายงาน

| อาจารย์ | รอบวันที่           | เงินเข้า | ยอดใช้รวม | กรณี 1 | กรณี 2.1 | กรณี 2.2 | กรณี 3 | เงินคงเหลือ |
| ------- | ------------------- | -------- | --------- | ------ | -------- | -------- | ------ | ----------- |
| AB      | 01/08/24 - 31/07/26 | 120,000  | 95,000    | 30,000 | 45,000   | 20,000   | 0      | 25,000      |
| AB      | 13/01/25 - 12/01/27 | 120,000  | 20,334    | 0      | 0        | 0        | 20,334 | 99,666      |
| AC      | 01/08/24 - 14/11/24 | 120,000  | 120,000   | 50,000 | 70,000   | 0        | 0      | 0           |
| AC      | 15/11/24 - 14/11/26 | 120,000  | 0         | 0      | 0        | 0        | 0      | 120,000     |

---

## หมายเหตุการตั้งค่า

### เพิ่มประเภทค่าใช้จ่ายใหม่

เพิ่มเข้าในพจนานุกรม `T_CAT*`:

```python
T_CAT_NEW = [
    "ชื่อ Template ใหม่ 1",
    "ชื่อ Template ใหม่ 2"
]
```

จากนั้นเพิ่มตรรกะการจับคู่ในลูปการแบ่งประเภท:

```python
elif template in T_CAT_NEW:
    val_c_new += credit
```

### เปลี่ยนจำนวนเงินโอน

แก้ไขในทั้งสองฟังก์ชัน:

```python
# บรรทัด 18: calculate_periods_by_budget()
AND debit = 120000  # เปลี่ยนตรงนี้

# บรรทัด 117: execute() income query
AND debit = 120000  # เปลี่ยนตรงนี้
```

### เปลี่ยนระยะเวลาช่วง

แก้ไขใน `calculate_periods_by_budget()`:

```python
end_date = start_date + timedelta(days=365 * 2 - 1)  # 2 ปี
# เปลี่ยนเป็น:
end_date = start_date + timedelta(days=365 * 3 - 1)  # 3 ปี
```

---

## คำสั่ง SQL ที่ใช้

### คำสั่ง 1: ดึงวันที่โอนเงิน

```sql
SELECT posting_date
FROM `tabGL Entry`
WHERE is_cancelled = 0
  AND debit = 120000
  AND account LIKE '%AB Travel - IE%'
ORDER BY posting_date ASC
```

### คำสั่ง 2: ดึงแท็กอาจารย์ทั้งหมด

```sql
SELECT DISTINCT SUBSTRING_INDEX(account, ' ', 1) as tag
FROM `tabGL Entry`
WHERE is_cancelled = 0
  AND account LIKE '% Travel - IE%'
  AND SUBSTRING_INDEX(account, ' ', 1) != 'IE'
ORDER BY tag ASC
```

### คำสั่ง 3: ดึงเงินเข้าสำหรับช่วง

```sql
SELECT debit
FROM `tabGL Entry`
WHERE is_cancelled = 0
  AND posting_date = '2024-08-01'
  AND debit = 120000
  AND account LIKE '%AB Travel - IE%'
```

### คำสั่ง 4: ดึงค่าใช้จ่ายสำหรับช่วง (การเชื่อมต่อที่ซับซ้อน)

```sql
SELECT
    gle.posting_date,
    gle.credit,
    src.name as travel_name,
    proj.project_template,
    proj.country
FROM `tabGL Entry` gle
LEFT JOIN `tabJournal Entry` je
    ON gle.voucher_no = je.name
    AND gle.voucher_type = 'Journal Entry'
LEFT JOIN `tabTravel Expense request` src
    ON je.cheque_no = src.name
LEFT JOIN `tabProject` proj
    ON src.relate_project = proj.name
WHERE
    gle.is_cancelled = 0
    AND gle.posting_date BETWEEN '2024-08-01' AND '2026-07-31'
    AND gle.credit > 0
    AND gle.account LIKE '%AB Travel - IE%'
```

---

## แก้ไขปัญหา

### ไม่มีข้อมูลปรากฏ

1. ตรวจสอบว่ามีการโอนเงิน 120,000 บาท ใน GL Entry หรือไม่
2. ตรวจสอบการตั้งชื่อบัญชี: `{TAG} Travel - IE`
3. ยืนยันว่า GL Entry ไม่ถูกยกเลิก

### จำนวนเงินประเภทผิด

1. ตรวจสอบการสะกดชื่อ project_template ใน Travel Expense Request
2. ตรวจสอบว่าชื่อ template ตรงกับคำจำกัดความ T_CAT\* หรือไม่
3. ตรวจสอบว่าค่าใช้จ่ายเชื่อมโยงกับ Project ที่ถูกต้องหรือไม่

### อาจารย์หายไป

1. ตรวจสอบว่ามีการโอนเงิน 120,000 บาท อย่างน้อยหนึ่งครั้งหรือไม่
2. ตรวจสอบรูปแบบบัญชีใน GL Entry
3. ตรวจสอบว่าบัญชีไม่ถูกทำเครื่องหมายว่ายกเลิก

---

## พิจารณาด้านประสิทธิภาพ

- **ความซับซ้อนของเวลา**: O(n_professors × n_periods × n_expenses)
- **คำสั่ง Database**: 4 คำสั่งหลักต่อการดำเนินการรายงาน
- **คำแนะนำ**:
  - เพิ่มดัชนีใน `GL Entry.account` และ `GL Entry.posting_date`
  - เพิ่มดัชนีใน `Travel Expense request.relate_project`
  - จำกัดช่วงช่วงเวลาด้วยตัวกรองหากมีข้อมูลหลายปี

---

## ประวัติเวอร์ชัน

- **v1.0** (กุมภาพันธ์ 2569): การนำไปปฏิบัติครั้งแรกพร้อมประเภทค่าใช้จ่าย 4 ประเภท
