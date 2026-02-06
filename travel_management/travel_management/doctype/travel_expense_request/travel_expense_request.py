import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_link_to_form, today


class TravelExpenserequest(Document):
	def before_save(self):
		# ตั้งชื่อ Title เอกสารให้เป็นชื่อผู้เบิก (อาจารย์)
		if self.instructor:
			self.title = self.instructor

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
			# === กรณีที่ 1: ตั้งหนี้ (Debt Template - 2 ขา) ===
			# ขา Credit: บัญชีเจ้าหนี้/ลูกหนี้ (ชื่ออาจารย์)
			accounts.append(
				{
					"account": self.instructor,
					"credit_in_account_currency": amt,
					"debit_in_account_currency": 0,
					"cost_center": cost_center,
					"company": company,
				}
			)
			# ขา Debit: บัญชีพักหนี้/ค่าใช้จ่าย
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
			# === กรณีที่ 2: เคลียร์ยอด (Travel Template - 4 ขา) ===
			# ✅ แก้ไขให้ตรงตามภาพที่ 1 ที่ผู้ใช้ต้องการ

			# 1. Cr. บัญชีอาจารย์ (เพื่อล้างลูกหนี้)
			accounts.append(
				{
					"account": self.instructor,
					"credit_in_account_currency": amt,
					"debit_in_account_currency": 0,
					"cost_center": cost_center,
					"company": company,
				}
			)
			# 2. Dr. ค่าใช้จ่ายเดินทาง (Travel Expenses)
			accounts.append(
				{
					"account": "Travel Expenses - IE",  # ⚠️ เช็คชื่อบัญชี
					"debit_in_account_currency": amt,
					"credit_in_account_currency": 0,
					"cost_center": cost_center,
					"company": company,
				}
			)
			# 3. Cr. เงินสด/ธนาคาร (IE Travel Money - จ่ายเงินออก)
			accounts.append(
				{
					"account": "IE Travel Money - IE",  # ⚠️ เช็คชื่อบัญชี
					"credit_in_account_currency": amt,
					"debit_in_account_currency": 0,
					"cost_center": cost_center,
					"company": company,
				}
			)
			# 4. Dr. บัญชีพักหนี้/ตั้งหนี้ (IE Travel Debt - ล้างยอดตั้งหนี้)
			accounts.append(
				{
					"account": "IE Travel Debt - IE",  # ⚠️ เช็คชื่อบัญชี
					"debit_in_account_currency": amt,
					"credit_in_account_currency": 0,
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
