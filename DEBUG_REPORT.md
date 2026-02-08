# 🔴 DEBUG REPORT - Dashboard Summary Code Issues

## Issues Found

### 🔴 ISSUE 1: Missing Template Category Lists (CRITICAL)

**Location**: `execute()` function start
**Problem**: The code is missing the T_CAT1, T_CAT21, T_CAT22, T_CAT3 list definitions
**Current Code**: Uses keyword matching instead of exact list matching
**Impact**: Category matching logic was completely replaced without defining the lists

**What's Missing**:

```python
# These should be defined at the start of execute()
T_CAT1 = normalize_list([
    "Template ในประเทศ (เบิกภาค)",
])

T_CAT21 = normalize_list([
    "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน",
    "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน (ขอทุนคณะ/มช.)",
])

T_CAT22 = normalize_list([
    "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน ไม่เกิน 60000",
    "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน เกิน 60000",
])

T_CAT3 = normalize_list([
    "Template ต่างประเทศ (เบิกภาค) ไม่นำเสนอผลงาน ไม่เกิน 40,000 บาท"
])
```

### 🔴 ISSUE 2: Missing `normalize_list()` Function

**Location**: `execute()` function
**Problem**: Code calls `normalize_list()` but function is not defined
**Current State**: Function was removed

**What's Missing**:

```python
def normalize_list(lst):
    return [x.strip().lower() for x in lst]
```

### 🟡 ISSUE 3: Changed SQL Query for Expenses

**Location**: Line ~145-160 (sql_expenses query)
**Problem**: SQL query was completely changed to use direct `gle.project` join instead of:

- GL Entry → Journal Entry
- Journal Entry → Travel Expense Request
- Travel Expense Request → Project

**Current Query**:

```sql
SELECT ... FROM `tabGL Entry` gle
LEFT JOIN `tabProject` proj ON gle.project = proj.name
```

**Issue**: GL Entry may not have direct `project` field. Need to verify if this link exists.

### 🟡 ISSUE 4: Keyword Matching Instead of Exact List Matching

**Location**: Lines ~172-190 (categorization logic)
**Problem**: Code switched from exact template list matching to keyword-based matching

**Original Logic** (correct):

```python
if template in T_CAT1:
    val_c1 += credit
elif template in T_CAT21:
    val_c21 += credit
```

**Current Logic** (may miss or misclassify):

```python
if "ในประเทศ" in template:
    val_c1 += credit
elif "ต่างประเทศ" in template and "นำเสนอ" in template and ("60000" in template):
    val_c22 += credit
```

**Problem**: Keyword matching can cause false positives/negatives

---

## Recommended Fixes

### Fix 1: Restore Template Lists

Add at the start of `execute()` function:

```python
def normalize_list(lst):
    return [x.strip().lower() for x in lst]

T_CAT1 = normalize_list([
    "Template ในประเทศ (เบิกภาค)",
])

T_CAT21 = normalize_list([
    "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน",
    "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน (ขอทุนคณะ/มช.)",
])

T_CAT22 = normalize_list([
    "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน ไม่เกิน 60000",
    "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน เกิน 60000",
])

T_CAT3 = normalize_list([
    "Template ต่างประเทศ (เบิกภาค) ไม่นำเสนอผลงาน ไม่เกิน 40,000 บาท"
])
```

### Fix 2: Restore Exact Matching Logic

Replace keyword matching with:

```python
# 🔥 NORMALIZE template ก่อน compare (lowercase + trim)
template = (entry.get("project_template") or "").strip().lower()

if template in T_CAT1:
    val_c1 += credit
elif template in T_CAT21:
    val_c21 += credit
elif template in T_CAT22:
    val_c22 += credit
elif template in T_CAT3:
    val_c3 += credit
```

### Fix 3: Verify SQL Query

Check if GL Entry has direct `project` field:

```sql
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME='tabGL Entry' AND COLUMN_NAME='project';
```

If it doesn't exist, revert to original complex join:

```sql
SELECT ... FROM `tabGL Entry` gle
LEFT JOIN `tabJournal Entry` je ON gle.voucher_no = je.name
LEFT JOIN `tabTravel Expense request` src ON je.cheque_no = src.name
LEFT JOIN `tabProject` proj ON src.relate_project = proj.name
```

---

## Test Cases to Verify

1. **Test Template Matching**:
   - Input: "template ในประเทศ (เบิกภาค)"
   - Expected: Classified as T_CAT1 ✓

2. **Test Case Sensitive**:
   - Input: "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน"
   - Expected: Classified as T_CAT21 (not T_CAT22) ✓

3. **Test Amount Limit**:
   - Input: "Template ต่างประเทศ (เบิกภาค) นำเสนอผลงาน เกิน 60000"
   - Expected: Classified as T_CAT22 (not T_CAT21) ✓

---

## Summary

| Issue                    | Severity    | Status                   |
| ------------------------ | ----------- | ------------------------ |
| Missing T_CAT lists      | 🔴 CRITICAL | NOT FIXED                |
| Missing normalize_list() | 🔴 CRITICAL | NOT FIXED                |
| Changed SQL query        | 🟡 MEDIUM   | Need verification        |
| Keyword matching         | 🟡 MEDIUM   | Not ideal but functional |

**Result**: Categories will NOT display correctly because the T_CAT lists are missing!
