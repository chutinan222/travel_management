# Dashboard Summary Report - Code Documentation

## Overview

This report displays travel expense budgets for each professor with automatic categorization by expense type. It dynamically calculates validity periods based on money transfers and categorizes expenses into 4 case types.

---

## File Location

```
travel_management/travel_management/report/dashboard_summary/dashboard_summary.py
```

---

## Architecture

### Two Main Functions

#### 1. `calculate_periods_by_budget(tag)`

**Lines: 8-45**

**Purpose**: Calculate validity periods for a professor based on 120,000 THB transfers

**Algorithm**:

```
1. Query GL Entry for all 120,000 THB debits (money transfers)
2. Extract posting dates in chronological order
3. For each transfer date, create a validity period:
   - Period 1: First transfer date → 2 years later (or until next transfer)
   - Period 2+: Each subsequent transfer starts new 2-year period
4. Return list of (start_date, end_date, trigger_date) tuples
```

**Example**:

```
Transfer 1: 2024-08-01 → Period 1: 2024-08-01 to 2026-07-31
Transfer 2: 2025-09-15 → Period 2: 2025-09-15 to 2027-09-14
Transfer 3: 2026-10-20 → Period 3: 2026-10-20 to 2028-10-19
```

**SQL Query Used**:

```sql
SELECT posting_date
FROM `tabGL Entry`
WHERE is_cancelled = 0
  AND debit = 120000
  AND account LIKE '%AB Travel - IE%'  -- For professor "AB"
ORDER BY posting_date ASC
```

---

#### 2. `execute(filters)` - Main Report Function

**Lines: 50-220**

**Purpose**: Generate the complete dashboard report with expense breakdown

---

## Execution Flow

### Step 1: Define Expense Categories

**Lines: 51-67**

```python
T_CAT1 = ["Template ในประเทศ (เบิกภาค)"]
         # Domestic travel

T_CAT21 = [
    "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน",
    "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน (ขอทุนคณะ/มช.)"
]
          # International with presentation

T_CAT22 = [
    "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน ไม่เกิน 60000",
    "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน เกิน 60000"
]
          # International with amount limits

T_CAT3 = ["Template ต่างประเทศ (เบิกภาค) ไม่นำเสนอผลงาน ไม่เกิน 40,000 บาท"]
         # International without presentation
```

### Step 2: Fetch All Professor Tags

**Lines: 69-81**

**SQL Query**:

```sql
SELECT DISTINCT SUBSTRING_INDEX(account, ' ', 1) as tag
FROM `tabGL Entry`
WHERE is_cancelled = 0
  AND account LIKE '% Travel - IE%'
  AND SUBSTRING_INDEX(account, ' ', 1) != 'IE'
ORDER BY tag ASC
```

**Result**: `['AB', 'AC', 'AL', 'AP', 'AS', 'CB', ...]`

**Logic**:

- Extracts first word from account name (e.g., "AB Travel - IE" → "AB")
- Filters out "IE" (not a professor tag)
- Sorts alphabetically

### Step 3: Define Report Columns

**Lines: 83-97**

```
อาจารย์ (Tag) | รอบวันที่ | เงินเข้า | ยอดใช้รวม |
กรณี 1 | กรณี 2.1 | กรณี 2.2 | กรณี 3 | เงินคงเหลือ |
ครั้งที่ 1-5 (Trip history)
```

### Step 4: Main Loop - Process Each Professor

**Lines: 101-209**

```python
for prof_tag in PROFESSOR_TAGS:  # e.g., "AB", "AC"

    # Get all validity periods for this professor
    validity_periods = calculate_periods_by_budget(prof_tag)

    # Process each period
    for start_dt, end_dt, trigger_date in validity_periods:

        # Calculate income
        # Calculate expenses
        # Categorize by template
        # Create report row
```

---

## Detailed Processing for Each Period

### A. Income Calculation

**Lines: 113-118**

```python
sql_income = """
    SELECT debit
    FROM `tabGL Entry`
    WHERE is_cancelled = 0
      AND posting_date = %s          # trigger_date only
      AND debit = 120000
      AND account LIKE %s            # "%AB Travel - IE%"
"""

total_in = sum(d["debit"] for d in income_list)
```

**Key Point**: Only counts money received on the trigger date (transfer date)

### B. Expense Calculation & Categorization

**Lines: 125-142**

```python
sql_expenses = """
    SELECT
        gle.posting_date,
        gle.credit,                    # Amount spent
        src.name as travel_name,
        proj.project_template,         # ⭐ Template name for categorization
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
        AND gle.posting_date BETWEEN %s AND %s   # Full period range
        AND gle.credit > 0
        AND gle.account LIKE %s                  # "%AB Travel - IE%"
"""
```

**Data Flow**:

```
GL Entry (credit > 0)
    ↓
Journal Entry (via voucher_no)
    ↓
Travel Expense Request (via cheque_no)
    ↓
Project (via relate_project)
    ↓
project_template (for categorization)
```

### C. Category Assignment

**Lines: 149-161**

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

**Totals**:

- `total_out` = val_c1 + val_c21 + val_c22 + val_c3
- `balance` = total_in - total_out

### D. Trip History

**Lines: 166-179**

```python
for i in range(5):
    field_name = f"trip_{i + 1}"
    if i < len(history_list):
        rec = history_list[i]
        c_name = rec.get("country") or "ไม่ระบุ"
        amt = flt(rec.get("credit") or 0)
        row[field_name] = f"{c_name}: {amt:,.0f}"
        # Example: "Thailand: 50,000"
```

**Sorted by**: posting_date (chronological order)

### E. Create Report Row

**Lines: 183-194**

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

## Step 5: Output

**Lines: 211-220**

Returns:

```python
(
    columns,      # Column definitions
    data,         # All rows from all professors and periods
    None,         # Message (unused)
    chart         # Bar chart: Used vs Balance per professor
)
```

---

## Key Concepts

### 1. Dynamic Validity Periods

- **Not hardcoded** - Based on actual 120,000 THB transfers in GL Entry
- **Multiple periods per professor** - Each transfer creates new period
- **2-year validity** - Each period lasts ~2 years

### 2. Dynamic Professor Tags

- **Extracted from GL Entry accounts** - No hardcoded list
- **Self-updating** - New professors appear automatically
- **Filtered** - Excludes "IE" tag

### 3. Expense Categorization

- **Template-based** - Uses project_template field
- **4 case types** - Based on travel type and presentation
- **Automatic** - No manual assignment needed

### 4. Data Linking Chain

```
GL Entry (credit)
  → Journal Entry
  → Travel Expense Request
  → Project
  → project_template
```

---

## Example Report Output

| อาจารย์ | รอบวันที่           | เงินเข้า | ยอดใช้รวม | กรณี 1 | กรณี 2.1 | กรณี 2.2 | กรณี 3 | เงินคงเหลือ |
| ------- | ------------------- | -------- | --------- | ------ | -------- | -------- | ------ | ----------- |
| AB      | 01/08/24 - 31/07/26 | 120,000  | 95,000    | 30,000 | 45,000   | 20,000   | 0      | 25,000      |
| AB      | 13/01/25 - 12/01/27 | 120,000  | 20,334    | 0      | 0        | 0        | 20,334 | 99,666      |
| AC      | 01/08/24 - 14/11/24 | 120,000  | 120,000   | 50,000 | 70,000   | 0        | 0      | 0           |
| AC      | 15/11/24 - 14/11/26 | 120,000  | 0         | 0      | 0        | 0        | 0      | 120,000     |

---

## Configuration Notes

### To Add New Expense Category

Add to `T_CAT*` dictionary:

```python
T_CAT_NEW = [
    "New Template Name 1",
    "New Template Name 2"
]
```

Then add matching logic in categorization loop:

```python
elif template in T_CAT_NEW:
    val_c_new += credit
```

### To Change Transfer Amount

Modify in both functions:

```python
# Line 18: calculate_periods_by_budget()
AND debit = 120000  # Change this

# Line 117: execute() income query
AND debit = 120000  # Change this
```

### To Change Period Duration

Modify in `calculate_periods_by_budget()`:

```python
end_date = start_date + timedelta(days=365 * 2 - 1)  # 2 years
# Change to:
end_date = start_date + timedelta(days=365 * 3 - 1)  # 3 years
```

---

## SQL Queries Used

### Query 1: Get Transfer Dates

```sql
SELECT posting_date
FROM `tabGL Entry`
WHERE is_cancelled = 0
  AND debit = 120000
  AND account LIKE '%AB Travel - IE%'
ORDER BY posting_date ASC
```

### Query 2: Get All Professor Tags

```sql
SELECT DISTINCT SUBSTRING_INDEX(account, ' ', 1) as tag
FROM `tabGL Entry`
WHERE is_cancelled = 0
  AND account LIKE '% Travel - IE%'
  AND SUBSTRING_INDEX(account, ' ', 1) != 'IE'
ORDER BY tag ASC
```

### Query 3: Get Income for Period

```sql
SELECT debit
FROM `tabGL Entry`
WHERE is_cancelled = 0
  AND posting_date = '2024-08-01'
  AND debit = 120000
  AND account LIKE '%AB Travel - IE%'
```

### Query 4: Get Expenses for Period (Complex Join)

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

## Troubleshooting

### No data appears

1. Check if 120,000 THB transfers exist in GL Entry
2. Verify account naming: `{TAG} Travel - IE`
3. Confirm GL Entry entries are not cancelled

### Wrong category amounts

1. Check project_template spelling in Travel Expense Request
2. Verify template names match T_CAT\* definitions
3. Check if expense is linked to correct Project

### Missing professor

1. Verify they have at least one 120,000 THB transfer
2. Check account format in GL Entry
3. Ensure account is not marked cancelled

---

## Performance Considerations

- **Time Complexity**: O(n_professors × n_periods × n_expenses)
- **Database Queries**: 4 main queries per report execution
- **Recommendations**:
  - Add index on `GL Entry.account` and `GL Entry.posting_date`
  - Add index on `Travel Expense request.relate_project`
  - Limit period range with filter if many years of data

---

## Version History

- **v1.0** (Feb 2026): Initial implementation with 4 expense categories
