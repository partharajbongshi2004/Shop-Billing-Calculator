import hashlib
import random
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import streamlit as st
from google import genai
from google.genai import types
import database as db


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _send_email(recipient: str, subject: str, body: str) -> tuple[bool, str]:
    try:
        sender_email = st.secrets["SENDER_EMAIL"]
        sender_password = st.secrets["SENDER_APP_PASSWORD"]
    except KeyError as e:
        return False, f"Missing secret key: {e}"

    try:
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP_SSL("://gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient, msg.as_string())
        return True, "Email sent successfully."
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"


def _get_gemini_client():
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def _get_sales_metrics(shop_name: str, email: str, days: int = 1) -> dict:
    total_revenue = 0
    total_orders = 0

    if days == 1:
        try:
            summary = db.get_today_sales_summary(shop_name) or {}
            total_revenue = int(round(float(summary.get("total_sales", summary.get("total_bill", 0)) or 0)))
            total_orders = int(summary.get("total_orders", summary.get("count", 0)) or 0)
        except Exception:
            total_revenue = 0
            total_orders = 0
    else:
        try:
            supabase = db.init_supabase()
            start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            response = (
                supabase.table("sales")
                .select("total_bill")
                .eq("shop_name", shop_name)
                .gte("created_at", start_date)
                .execute()
            )
            rows = response.data or []
            total_orders = len(rows)
            total_revenue = int(round(sum(float(r.get("total_bill", 0) or 0) for r in rows)))
        except Exception:
            total_revenue = 0
            total_orders = 0

    try:
        settings = db.get_store_settings(email) or {}
    except Exception:
        settings = {}

    daily_rent = int(round(float(settings.get("daily_rent", 0) or 0)))
    daily_staff = int(round(float(settings.get("daily_staff_cost", 0) or 0)))
    whatsapp = str(settings.get("whatsapp", "") or "")

    period_rent = int(daily_rent * days)
    period_staff = int(daily_staff * days)
    total_expenses = int(period_rent + period_staff)
    gross_profit = int(round(total_revenue * 0.50))
    net_profit = int(gross_profit - total_expenses)

    return {
        "days": int(days),
        "total_orders": int(total_orders),
        "total_revenue": int(total_revenue),
        "gross_profit": int(gross_profit),
        "daily_rent": int(daily_rent),
        "daily_staff": int(daily_staff),
        "period_rent": int(period_rent),
        "period_staff": int(period_staff),
        "total_expenses": int(total_expenses),
        "net_profit": int(net_profit),
        "whatsapp": whatsapp,
    }


def _generate_ai_advice(shop_name: str, metrics: dict, user_question: str, language: str) -> str:
    client = _get_gemini_client()
    if not client:
        return "Error: GEMINI_API_KEY is missing or invalid in st.secrets."

    system_instruction = (
        f"You are an expert AI Retail Business Manager and Financial Consultant for '{shop_name}'. "
        f"You MUST respond strictly in {language}. "
        "CRITICAL RULE: Use ONLY whole integer numbers in your response (no decimals, no cents, no floating-point numbers). "
        "Base all financial analysis strictly on the provided shop figures:\n"
        f"- Total Orders Today: {metrics['total_orders']}\n"
        f"- Total Sales Revenue (total_bill): {metrics['total_revenue']}\n"
        f"- Gross Profit (50% of total_bill): {metrics['gross_profit']}\n"
        f"- Daily Shop Rent: {metrics['daily_rent']}\n"
        f"- Daily Staff & Utility Cost: {metrics['daily_staff']}\n"
        f"- Total Daily Fixed Expenses: {metrics['total_expenses']}\n"
        f"- Net Profit (Gross Profit minus Daily Expenses): {metrics['net_profit']}\n"
        "Give practical, actionable, concise advice to improve profit margins, manage expenses, and boost sales."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_question,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.4,
            ),
        )
        return response.text or "No response generated."
    except Exception as e:
        return f"AI Consultant Error: {str(e)}"


def _generate_ai_report(shop_name: str, metrics: dict, period_label: str) -> str:
    client = _get_gemini_client()
    summary_header = (
        f"=== {shop_name.upper()} - {period_label.upper()} BUSINESS REPORT ===\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"Total Orders: {metrics['total_orders']}\n"
        f"Total Revenue: {metrics['total_revenue']}\n"
        f"Gross Profit (50%): {metrics['gross_profit']}\n"
        f"Rent Expense: {metrics['period_rent']}\n"
        f"Staff & Utility Expense: {metrics['period_staff']}\n"
        f"Total Expenses: {metrics['total_expenses']}\n"
        f"Net Profit: {metrics['net_profit']}\n"
        "==================================================\n\n"
    )

    if not client:
        return summary_header + "AI Insights unavailable (missing GEMINI_API_KEY)."

    prompt = (
        f"Write a concise executive {period_label} retail performance summary and 3 actionable recommendations "
        f"for shop '{shop_name}' using ONLY whole integer numbers (no decimals). "
        f"Metrics: Orders={metrics['total_orders']}, Revenue={metrics['total_revenue']}, "
        f"Gross Profit={metrics['gross_profit']}, Total Expenses={metrics['total_expenses']}, "
        f"Net Profit={metrics['net_profit']}."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.4),
        )
        ai_text = response.text or ""
        return summary_header + ai_text
    except Exception as e:
        return summary_header + f"Could not generate AI commentary: {str(e)}"


@st.dialog("✨ AI Business Manager", width="large")
def open_ai_manager_dialog(shop_name: str):
    if "ai_mgr_authenticated" not in st.session_state:
        st.session_state.ai_mgr_authenticated = False
    if "ai_mgr_email" not in st.session_state:
        st.session_state.ai_mgr_email = ""
    if "ai_mgr_chat" not in st.session_state:
        st.session_state.ai_mgr_chat = []
    if "ai_mgr_pending_signup" not in st.session_state:
        st.session_state.ai_mgr_pending_signup = None

    if not st.session_state.ai_mgr_authenticated:
        st.caption(f"Store: **{shop_name}** | Owner Authentication")
        login_tab, signup_tab = st.tabs(["🔐 Login", "📝 Create Account"])

        with login_tab:
            with st.form("ai_mgr_login_form"):
                login_email = st.text_input("Owner Email", placeholder="owner@example.com").strip().lower()
                login_password = st.text_input("Password", type="password")
                login_submit = st.form_submit_button("Login", use_container_width=True)

            if login_submit:
                if not login_email or not login_password:
                    st.error("Please enter both email and password.")
                else:
                    try:
                        supabase = db.init_supabase()
                        res = (
                            supabase.table("store_owners")
                            .select("*")
                            .eq("email", login_email)
                            .execute()
                        )
                        records = res.data or []
                        if not records:
                            st.error("No account found with this email.")
                        else:
                            user_row = records[0]
                            stored_hash = user_row.get("password_hash", "")
                            if stored_hash == _hash_password(login_password):
                                st.session_state.ai_mgr_authenticated = True
                                st.session_state.ai_mgr_email = login_email
                                st.rerun()
                            else:
                                st.error("Incorrect password.")
                    except Exception as e:
                        st.error(f"Database login error: {str(e)}")

        with signup_tab:
            if st.session_state.ai_mgr_pending_signup is None:
                with st.form("ai_mgr_signup_form"):
                    new_email = st.text_input("Owner Email", placeholder="owner@example.com").strip().lower()
                    new_password = st.text_input("Create Password", type="password")
                    confirm_password = st.text_input("Confirm Password", type="password")
                    send_otp_btn = st.form_submit_button("Send 6-Digit Verification OTP", use_container_width=True)

                if send_otp_btn:
                    if not new_email or "@" not in new_email:
                        st.error("Please enter a valid email address.")
                    elif len(new_password) < 6:
                        st.error("Password must be at least 6 characters.")
                    elif new_password != confirm_password:
                        st.error("Passwords do not match.")
                    else:
                        otp = str(random.randint(100000, 999999))
                        ok, msg = _send_email(new_email, "AI Manager Verification OTP", f"Your 6-digit verification code is: {otp}")
                        if ok:
                            st.session_state.ai_mgr_pending_signup = {
                                "email": new_email,
                                "password_hash": _hash_password(new_password),
                                "otp": otp,
                                "expires": datetime.utcnow() + timedelta(minutes=10),
                            }
                            st.success(f"OTP sent to {new_email}!")
                            st.rerun()
                        else:
                            st.error(msg)
        else:
            pdata = st.session_state.ai_mgr_pending_signup
            st.info(f"Enter the 6-digit OTP sent to *{pdata['email']}*")
            with st.form("ai_mgr_otp_form"):
                user_otp = st.text_input("6-Digit OTP", max_chars=6).strip()
                c_ver, c_can = st.columns(2)
                verify_btn = c_ver.form_submit_button("Verify & Create Account", type="primary", use_container_width=True)
                cancel_btn = c_can.form_submit_button("Cancel", use_container_width=True)

            if verify_btn:
                if user_otp == pdata["otp"]:
                    db.save_store_settings(email=pdata["email"], password_hash=pdata["password_hash"])
                    st.session_state.ai_mgr_authenticated = True
                    st.session_state.ai_mgr_email = pdata["email"]
                    st.session_state.ai_mgr_pending_signup = None
                    st.success("Account verified!")
                    st.rerun()
                else:
                    st.error("Invalid OTP code.")
            if cancel_btn:
                st.session_state.ai_mgr_pending_signup = None
                st.rerun()
        return

    email = st.session_state.ai_mgr_email
    c_top1, c_top2 = st.columns([3, 1])
    c_top1.caption(f"Owner: *{email}* | Store: *{shop_name}*")
    if c_top2.button("Logout", use_container_width=True):
        st.session_state.ai_mgr_authenticated = False
        st.session_state.ai_mgr_email = ""
        st.rerun()

    tab_chat, tab_expenses, tab_reports = st.tabs(["🤖 AI Consultant", "💸 Shop Expenses", "📧 Daily & Monthly Reports"])

    with tab_chat:
        lang = st.selectbox("Language / ভাষা / Idioma", ["Bengali", "English", "Portuguese"])
        metrics = _get_sales_metrics(shop_name, email, days=1)
        m1, m2, m3 = st.columns(3)
        m1.metric("Today Sales", f"{metrics['total_revenue']}")
        m2.metric("Daily Fixed Cost", f"{metrics['total_expenses']}")
        m3.metric("Net Profit", f"{metrics['net_profit']}")

        for msg in st.session_state.ai_mgr_chat:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        if user_q := st.chat_input("Ask about profit, expenses, or business growth..."):
            st.session_state.ai_mgr_chat.append({"role": "user", "content": user_q})
            with st.chat_message("user"):
                st.write(user_q)
            with st.chat_message("assistant"):
                reply = _generate_ai_advice(shop_name, metrics, user_q, lang)
                st.write(reply)
                st.session_state.ai_mgr_chat.append({"role": "assistant", "content": reply})

    with tab_expenses:
        curr = _get_sales_metrics(shop_name, email, days=1)
        with st.form("expense_form"):
            inp_rent = st.number_input("Daily Shop Rent (Whole Integer)", min_value=0, value=int(curr["daily_rent"]), step=1)
            inp_staff = st.number_input("Daily Staff + Electricity + Water Cost (Whole Integer)", min_value=0, value=int(curr["daily_staff"]), step=1)
            inp_wa = st.text_input("Owner WhatsApp Number", value=curr["whatsapp"])
            if st.form_submit_button("Save Shop Expenses", type="primary"):
                db.save_store_settings(email=email, whatsapp=inp_wa, daily_rent=int(inp_rent), daily_staff_cost=int(inp_staff))
                st.success("Expenses updated!")
                st.rerun()

    with tab_reports:
        rep_lang = st.selectbox("Report Language", ["Bengali", "English", "Portuguese"], key="rep_lang")
        if st.button("📩 Send Today's AI Summary to Email", use_container_width=True):
            m_day = _get_sales_metrics(shop_name, email, days=1)
            rep_text = _generate_executive_report(shop_name, m_day, "Daily", rep_lang)
            ok, msg = _send_email(email, f"Daily AI Report - {shop_name}", rep_text)
            st.success(msg) if ok else st.error(msg)

        if st.button("📊 Send 30-Day Monthly AI Summary to Email", use_container_width=True):
            m_mon = _get_sales_metrics(shop_name, email, days=30)
            rep_text = _generate_executive_report(shop_name, m_mon, "Monthly (30 Days)", rep_lang)
            ok, msg = _send_email(email, f"Monthly AI Report - {shop_name}", rep_text)
            st.success(msg) if ok else st.error(msg)
