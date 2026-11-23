import streamlit as st
import smtplib
import random
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date
from google import genai
from google.genai import types
import database as db
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()
def send_email_notification(to_email: str, subject: str, body: str) -> bool:
    try:
        sender_email = st.secrets["SENDER_EMAIL"]
        sender_password = st.secrets["SENDER_APP_PASSWORD"]
        msg = MIMEMultipart()
        msg["From"] = f"AI Business Manager <{sender_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP_SSL("://gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Email Error: {e}")
        return False
def get_monthly_sales_data(shop_name: str):
    supabase = db.init_supabase()
    today = date.today()
    first_day = today.replace(day=1).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")
    res = (
        supabase.table("sales")
        .select("*")
        .gte("sale_date", first_day)
        .lte("sale_date", today_str)
        .eq("shop_name", shop_name)
        .execute()
    )
    return res.data if res.data else []
def ask_business_ai(user_question: str, financial_context: str) -> str:
    try:
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        system_instruction = f"""
        You are a world-class Retail Business Manager and Financial Consultant.
        RULES:
        1. Products sold at 30 Riyals cost 12-15 Riyals (approx 50% cost, 50% Gross Profit).
        2. Deduct Shop Rent, Electricity, Water, and Employee Salaries from Gross Profit to find Net Profit.
        3. Give global retail strategies to grow sales and profit.
        4. Only answer business, sales, and accounting questions. Refuse non-business topics.
        5. Reply in the user's language (Bengali, English, or Portuguese).
        DATA:
        {financial_context}
        """
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_question,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.4
            )
        )
        return response.text
    except Exception as e:
        return f"AI Connection Error: {e}"
@st.dialog("✨ AI Business Manager", width="large")
def open_ai_manager_dialog(shop_name: str):
    if "ai_verified_email" not in st.session_state:
        st.session_state.ai_verified_email = None
    if "pending_otp" not in st.session_state:
        st.session_state.pending_otp = None
    if "pending_user_data" not in st.session_state:
        st.session_state.pending_user_data = {}
    if "ai_chat_history" not in st.session_state:
        st.session_state.ai_chat_history = []

    if not st.session_state.ai_verified_email:
        tab_login, tab_register = st.tabs(["🔑 Login", "📝 Create Account"])
        with tab_register:
            reg_name = st.text_input("Owner Name", key="reg_name")
            reg_email = st.text_input("Email Address", key="reg_email").strip().lower()
            reg_pass = st.text_input("Password", type="password", key="reg_pass")
            reg_whatsapp = st.text_input("WhatsApp Number", key="reg_wa")
          if st.button("Send Verification Code", use_container_width=True):
                if reg_name and reg_email and reg_pass:
                    otp = str(random.randint(100000, 999999))
                    body = f"Hello {reg_name},\nYour verification code is: {otp}"
                    if send_email_notification(reg_email, "AI Manager Verification Code", body):
                        st.session_state.pending_otp = otp
                        st.session_state.pending_user_data = {"email": reg_email, "whatsapp": reg_whatsapp}
                        st.success(f"Code sent to {reg_email}!")
                else:
                    st.warning("Please fill Name, Email, and Password.")

            if st.session_state.pending_otp:
                entered_otp = st.text_input("Enter 6-Digit Code", max_chars=6)
                if st.button("Verify & Activate", type="primary"):
                    if entered_otp.strip() == st.session_state.pending_otp:
                        udata = st.session_state.pending_user_data
                        db.save_store_settings(email=udata["email"], whatsapp=udata["whatsapp"])
                        st.session_state.ai_verified_email = udata["email"]
                        st.session_state.pending_otp = None
                        st.rerun()
                    else:
                        st.error("Invalid code!")
                          with tab_login:
                log_email = st.text_input("Registered Email", key="log_email").strip().lower()
                if st.button("Access AI Manager", type="primary", use_container_width=True):
                    if db.get_store_settings(log_email):
                        st.session_state.ai_verified_email = log_email
                        st.rerun()
                else:
                        st.error("Email not found! Please create an account first.")
            return

    owner_email = st.session_state.ai_verified_email
    settings = db.get_store_settings(owner_email) or {}
    c1, c2 = st.columns([4, 1])
    c1.caption(f"Owner: *{owner_email}* | Shop: *{shop_name}*")
    if c2.button("Logout", use_container_width=True):
        st.session_state.ai_verified_email = None
        st.rerun()
tab_chat, tab_expenses, tab_reports = st.tabs(["🤖 AI Consultant", "💸 Shop Expenses", "📧 Reports"])
    today_records = db.get_today_sales_summary(shop_name).get("sales_records", [])
    today_rev = sum(int(i.get("total_bill", i.get("price", 0))) for i in today_records)
    monthly_rev = sum(int(i.get("total_amount", i.get("price", 0))) for i in get_monthly_sales_data(shop_name))

    daily_rent = int(settings.get("daily_rent", 0))
    daily_other = int(settings.get("daily_staff_cost", 0))
    fixed_cost = daily_rent + daily_other
    net_profit = (today_rev - (today_rev // 2)) - fixed_cost

    fin_context = f"Shop: {shop_name} | Today Sales: {today_rev} | 50% Cost: {today_rev // 2} | Fixed Cost (Rent+Staff+Bills): {fixed_cost} | Net Profit: {net_profit} | Monthly Sales: {monthly_rev}"
with tab_chat:
        m1, m2, m3 = st.columns(3)
        m1.metric("আজকের বিক্রি", f"{today_rev}")
        m2.metric("দৈনিক খরচ", f"{fixed_cost}")
        m3.metric("আজকের নিট লাভ", f"{net_profit}")
        for msg in st.session_state.ai_chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
        if user_q := st.chat_input("ব্যবসা বা লাভ-ক্ষতি সম্পর্কে প্রশ্ন করুন..."):
            st.session_state.ai_chat_history.append({"role": "user", "content": user_q})
            with st.chat_message("user"):
                st.write(user_q)
            with st.chat_message("assistant"):
                reply = ask_business_ai(user_q, fin_context)
                st.write(reply)
                st.session_state.ai_chat_history.append({"role": "assistant", "content": reply})
              with tab_expenses:
        inp_rent = st.number_input("দৈনিক দোকান ভাড়া (Daily Rent)", min_value=0, value=daily_rent, step=1)
        inp_other = st.number_input("দৈনিক স্টাফ + কারেন্ট + পানির বিল", min_value=0, value=daily_other, step=1)
        inp_wa = st.text_input("WhatsApp Number", value=settings.get("whatsapp_number", ""))
        if st.button("Save Expenses", type="primary"):
            if db.save_store_settings(owner_email, inp_wa, inp_rent, inp_other):
                st.success("খরচ সেভ হয়েছে!")
                st.rerun()

    with tab_reports:
        if st.button("📩 Send Daily Report to Email", use_container_width=True):
            advice = ask_business_ai("আজকের বিক্রির ওপর ভিত্তি করে মালিককে সংক্ষিপ্ত হিসাব ও বিশ্বমানের ৩টি ব্যবসায়িক পরামর্শ দাও।", fin_context)
            if send_email_notification(owner_email, f"Daily Report - {shop_name}", f"{fin_context}\n\n{advice}"):
                st.success("আজকের রিপোর্ট ইমেইলে পাঠানো হয়েছে!")
        if st.button("📊 Send Monthly Report to Email", use_container_width=True):
            m_advice = ask_business_ai(f"এই মাসে মোট বিক্রি {monthly_rev}। মাসিক লাভ-ক্ষতি ও ব্যবসা উন্নতির পরামর্শ দাও।", fin_context)
            if send_email_notification(owner_email, f"Monthly Report - {shop_name}", f"Monthly Sales: {monthly_rev}\n\n{m_advice}"):
                st.success("মাসিক রিপোর্ট ইমেইলে পাঠানো হয়েছে!")
