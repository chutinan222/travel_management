import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_link_to_form, today


class TravelExpenserequest(Document):
	def before_save(self):
		# ตั้งชื่อ Title เอกสารให้เป็นชื่อผู้เบิก (อาจารย์)
		if self.instructor:
			self.title = self.instructor

	def get_instructor_balance(self, instructor_account):
		"""
		ดึง balance ปัจจุบันของบัญชีอาจารย์
		Balance = sum of credits - sum of debits (ไม่รวมวันที่อนาคต)
		"""
		if not instructor_account:
			return 0

		sql = """
			SELECT
				COALESCE(SUM(CASE WHEN credit > 0 THEN credit ELSE 0 END), 0) as total_credit,
				COALESCE(SUM(CASE WHEN debit > 0 THEN debit ELSE 0 END), 0) as total_debit
			FROM `tabGL Entry`
			WHERE
				is_cancelled = 0
				AND posting_date <= CURDATE()
				AND account = %s
		"""

		result = frappe.db.sql(sql, (instructor_account,), as_dict=1)

		if result:
			balance = result[0].get("total_credit", 0) - result[0].get("total_debit", 0)
			return max(0, balance)  # Return 0 if balance is negative

		return 0

	def on_submit(self):
		# ทำงานทันทีเมื่อกด Submit
		# ตรวจสอบว่าเคยสร้าง JE ไปแล้วหรือยัง ป้องกันการสร้างซ้ำ
		if not self.journal_entry_created:
			self.create_journal_entry()
		else:
			frappe.msgprint(_("รายการนี้ถูกบันทึกบัญชี (Journal Entry) ไปเรียบร้อยแล้ว"))

	def create_journal_entry(self):
		# --- 1. ส่วนดึงข้อมูลและตรวจสอบความถูกต้อง (Validation) ---

		if not self.from_template:
			frappe.throw(_("กรุณาเลือกรูปแบบการเบิก (From Template) ก่อนกด Submit"))

		if not self.travel_amount or self.travel_amount <= 0:
			frappe.throw(_("กรุณาระบุยอดเงิน (Travel Amount) ที่มากกว่า 0"))

		# ดึงยอดเงินมาเก็บไว้ในตัวแปร amt
		amt = self.travel_amount

		# ดึงข้อมูล "กองทุน" ที่เลือกจากหน้าจอ
		cost_center = self.custom_กองทน
		if not cost_center:
			frappe.throw(_("กรุณาระบุ กองทุน (Cost Center)"))

		company = self.company
		if not company:
			frappe.throw(_("ไม่พบข้อมูลบริษัท (Company) กรุณาตรวจสอบ"))

		accounts = []

		# --- 2. ส่วนกำหนดขาบัญชีตาม Template ที่เลือก ---
		# ⚠️ สำคัญมาก: ชื่อ Account ในเครื่องหมาย "" ต้องมีอยู่จริงในระบบ!

		if self.from_template == "Debt Template":
			# === Template 1: Debt Template - ตั้งหนี้ (2 ขา) ===
			# ทำการตั้งหนี้เมื่ออาจารย์เบิกจากระบบ
			# เพื่อติดตามว่าอาจารย์เบิกเงินไปเท่าไร
			#
			# Journal Entry:
			#   Cr. บัญชีอาจารย์ (ลูกหนี้ / บัญชีเบิกเงิน)
			#   Dr. IE Travel Debt - IE (บัญชีหนี้ระบบ)
			#
			# ผลลัพธ์: บัญชีอาจารย์ + amt (เพิ่มยอดหนี้)

			# ขา 1: Credit บัญชีอาจารย์ (ตั้งหนี้)
			accounts.append(
				{
					"account": self.instructor,
					"credit_in_account_currency": amt,
					"debit_in_account_currency": 0,
					"cost_center": cost_center,
					"company": company,
				}
			)
			# ขา 2: Debit IE Travel Debt - IE (บัญชีหนี้ระบบ)
			accounts.append(
				{
					"account": "IE Travel Debt - IE",  # ⚠️ เช็คชื่อบัญชี
					"debit_in_account_currency": amt,
					"credit_in_account_currency": 0,
					"cost_center": cost_center,
					"company": company,
				}
			)

		elif self.from_template == "Travel Template":
			# === Template 2: Travel Template - เคลียร์และหัก (4 ขา) ===
			# ทำการหักค่าใช้จ่ายจากเงินที่เบิก และล้างหนี้
			# นำเงินสดออกจากระบบและบันทึกค่าใช้จ่าย
			#
			# Journal Entry:
			#   Cr. บัญชีอาจารย์ (หักเงิน)
			#   Dr. Travel Expenses - IE (ค่าใช้จ่าย)
			#   Cr. IE Travel Money - IE (เงินสดลด)
			#   Dr. IE Travel Debt - IE (ล้างหนี้)
			#
			# ผลลัพธ์: บัญชีอาจารย์ = 0, ค่าใช้จ่ายขึ้น, เงินสดลด, หนี้ล้าง

			# ขา 1: Credit บัญชีอาจารย์ (หักเงิน)
			accounts.append(
				{
					"account": self.instructor,
					"credit_in_account_currency": amt,
					"debit_in_account_currency": 0,
					"cost_center": cost_center,
					"company": company,
				}
			)
			# ขา 2: Debit Travel Expenses - IE (บันทึกค่าใช้จ่าย)
			accounts.append(
				{
					"account": "Travel Expenses - IE",  # ⚠️ เช็คชื่อบัญชี
					"debit_in_account_currency": amt,
					"credit_in_account_currency": 0,
					"cost_center": cost_center,
					"company": company,
				}
			)
			# ขา 3: Credit IE Travel Money - IE (เงินสด/ธนาคารลด)
			accounts.append(
				{
					"account": "IE Travel Money - IE",  # ⚠️ เช็คชื่อบัญชี
					"credit_in_account_currency": amt,
					"debit_in_account_currency": 0,
					"cost_center": cost_center,
					"company": company,
				}
			)
			# ขา 4: Debit IE Travel Debt - IE (ล้างอัตหนี้)
			accounts.append(
				{
					"account": "IE Travel Debt - IE",  # ⚠️ เช็คชื่อบัญชี
					"debit_in_account_currency": amt,
					"credit_in_account_currency": 0,
					"cost_center": cost_center,
					"company": company,
				}
			)

		elif self.from_template == "return money to system":
			# === Template 3: Return Money to System - เบิกเงินคืนระบบ (2 ขา) ===
			# เมื่ออาจารย์คืนเงินที่เบิกมาแล้ว ระบบจะ Reset บัญชีอาจารย์เป็น 0
			# ล้างทั้งหนี้และจำนวนเงินที่ทำการเบิก
			#
			# Journal Entry:
			#   Cr. บัญชีอาจารย์ (หักเงินคืนทั้งหมด)
			#   Dr. IE Travel Debt - IE (ล้างหนี้)
			#
			# ผลลัพธ์: บัญชีอาจารย์ = 0 (รีเซ็ตเป็นศูนย์)
			#         หนี้ระบบล้าง = 0

			# ขา 1: Credit บัญชีอาจารย์ (หักเงินคืน = รีเซ็ตบัญชี)
			accounts.append(
				{
					"account": self.instructor,
					"credit_in_account_currency": amt,
					"debit_in_account_currency": 0,
					"cost_center": cost_center,
					"company": company,
				}
			)
			# ขา 2: Debit IE Travel Debt - IE (ล้างหนี้ระบบ)
			accounts.append(
				{
					"account": "IE Travel Debt - IE",  # ⚠️ เช็คชื่อบัญชี
					"debit_in_account_currency": amt,
					"credit_in_account_currency": 0,
					"cost_center": cost_center,
					"company": company,
				}
			)

		elif self.from_template == "เงินเข้า 120000":
			# === Template 4: Budget In 120000 - เงินเข้า (2 ขา) ===
			# ทำการบันทึกเมื่อเงินอุดหนุนเข้า
			# จำนวนเงินจะตามที่กรอกใน Travel Amount (อาจไม่ใช่ 120,000 ตรงๆ)
			#
			# Journal Entry:
			#   Dr. บัญชีอาจารย์ (เงินเข้า)
			#   Cr. IE Travel Debt - IE (บัญชีหนี้)
			#
			# ผลลัพธ์: บัญชีอาจารย์ + amt (ยอดเงินเข้า)
			#         หนี้ระบบ - amt (ลดลง)

			# ขา 1: Debit บัญชีอาจารย์ (เงินเข้า)
			accounts.append(
				{
					"account": self.instructor,
					"debit_in_account_currency": amt,
					"credit_in_account_currency": 0,
					"cost_center": cost_center,
					"company": company,
				}
			)
			# ขา 2: Credit IE Travel Debt - IE (หักหนี้ระบบ)
			accounts.append(
				{
					"account": "IE Travel Debt - IE",  # ⚠️ เช็คชื่อบัญชี
					"credit_in_account_currency": amt,
					"debit_in_account_currency": 0,
					"cost_center": cost_center,
					"company": company,
				}
			)

		# --- 3. ส่วนสร้างและบันทึก Journal Entry ---
		try:
			# เตรียมข้อมูลสำหรับสร้าง JE
			je_doc = {
				"doctype": "Journal Entry",
				"voucher_type": "Journal Entry",
				"posting_date": self.posting_date or today(),
				"company": company,
				"accounts": accounts,
				"user_remark": f"สร้างอัตโนมัติจากใบเบิก: {self.name} | รูปแบบ: {self.from_template} | ผู้เบิก: {self.instructor}",
			}

			# สร้างเอกสาร JE ในหน่วยความจำ
			je = frappe.get_doc(je_doc)

			# บันทึก (Insert) และ ยืนยัน (Submit) JE ทันที
			je.insert(ignore_permissions=True)
			je.submit()

			# --- 4. อัปเดตสถานะกลับมาที่ใบเบิก ---
			# ติ๊กถูกช่อง "Journal Entry Created"
			self.db_set("journal_entry_created", 1)

			# สร้างลิ้งค์สำหรับแจ้งเตือน (แก้ Error 'get_desk_link')
			je_link = get_link_to_form(je.doctype, je.name)

			# แจ้งเตือนสำเร็จ
			frappe.msgprint(
				_("บันทึกบัญชีสำเร็จ! สร้าง Journal Entry เรียบร้อยแล้ว: {0}").format(je_link),
				title=_("Success"),
				indicator="green",
			)

		except Exception as e:
			# กรณีเกิด Error ให้บันทึก Log และแจ้งเตือน
			frappe.log_error(frappe.get_traceback(), _("Journal Entry Creation Failed"))
			error_msg = str(e)
			if "Account" in error_msg and "not found" in error_msg:
				frappe.throw(_("ไม่พบชื่อบัญชีที่ระบุในโค้ด Python กรุณาตรวจสอบชื่อบัญชีในระบบและในโค้ดให้ตรงกัน"))
			else:
				frappe.throw(_("เกิดข้อผิดพลาดในการสร้าง Journal Entry: {0}").format(error_msg))
