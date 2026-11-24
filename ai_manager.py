import hashlib
import calendar
from datetime import datetime
import pytz
import streamlit as st
import extra_streamlit_components as stx
from google import genai
from google.genai import types
from database import init_supabase, get_sales_by_date_range

def get_cookie_manager():
    return stx.CookieManager(key="ai_mgr_cookies")

def _make_auth_token(email: str, password: str) -> str:
    salt = st.secrets.get("SUPABASE_KEY", "pos_ai_salt")[:16]
    return hashlib.sha256(f"{email.lower().strip()}:{password}:{salt}".encode()).hexdigest()
def _fetch_stock_summary() -> tuple[int, str]:
    """Reads live stock/products from Supabase safely."""
    try:
        sb = init_supabase()
        res = sb.table("products").select("*").execute()
        rows = res.data or []
        if not rows:
            return 0, "No products registered."
        lines = []
        total_units = 0
        for r in rows:
            qty = r.get("stock", r.get("quantity", "N/A"))
            if isinstance(qty, int):
                total_units += qty
            lines.append(f"- {r.get('name')} (Code: {r.get('code')}): Price R$ {r.get('price')}, Stock: {qty}")
        return total_units, "\n".join(lines[:40])
    except Exception as e:
        return 0, f"Stock read note: {e}"

def _compute_financials(shop: str, ref_date) -> dict:
    """Computes live Daily, Monthly, and Yearly revenue & integer Net Profit in R$."""
    d_str = ref_date.strftime("%Y-%m-%d")
    m_start = ref_date.replace(day=1).strftime("%Y-%m-%d")
    m_end = ref_date.replace(day=calendar.monthrange(ref_date.year, ref_date.month)[1]).strftime("%Y-%m-%d")
    y_start = f"{ref_date.year}-01-01"
    y_end = f"{ref_date.year}-12-31"

    daily_sales = get_sales_by_date_range(d_str, d_str, shop)
    monthly_sales = get_sales_by_date_range(m_start, m_end, shop)
    yearly_sales = get_sales_by_date_range(y_start, y_end, shop)

    d_rev = int(sum(int(x.get("total_bill", 0)) for x in daily_sales))
    m_rev = int(sum(int(x.get("total_bill", 0)) for x in monthly_sales))
    y_rev = int(sum(int(x.get("total_bill", 0)) for x in yearly_sales))

    d_units = max(len(daily_sales), round(d_rev / 30)) if d_rev > 0 else 0
    m_units = max(len(monthly_sales), round(m_rev / 30)) if m_rev > 0 else 0
    y_units = max(len(yearly_sales), round(y_rev / 30)) if y_rev > 0 else 0

    return {
        "d_rev": d_rev, "m_rev": m_rev, "y_rev": y_rev,
        "d_tx": len(daily_sales), "m_tx": len(monthly_sales), "y_tx": len(yearly_sales),
        "d_units": d_units, "m_units": m_units, "y_units": y_units,
    }
def render_ai_manager(shop: str, lang: str):
    """Renders the One-Time Login gate and the Live Business-Only AI Manager."""
    cookies = get_cookie_manager()
    st.session_state.setdefault("ai_logged_in", False)
    st.session_state.setdefault("ai_user_email", "")
    st.session_state.setdefault("ai_chat", [])

    saved_token = cookies.get("ai_mgr_token")
    saved_email = cookies.get("ai_mgr_email")
    if saved_token and saved_email:
        st.session_state.ai_logged_in = True
        st.session_state.ai_user_email = saved_email

    L = {
        "E": {
            "hdr": "🤖 AI Business Manager & Global Strategist",
            "login_sub": "One-Time Manager Access (Remembered Automatically)",
            "email": "Manager Email", "pw": "Password", "login_btn": "Unlock AI Manager",
            "login_err": "Please enter a valid email and password (min 4 chars).",
            "fixed_hdr": "Monthly Fixed Costs & Unit Cost (R$ Integers)",
            "buy_cost": "Avg Buying Cost / Unit (R$)", "rent": "Shop Rent / Month (R$)",
            "water": "Water Bill / Month (R$)", "elec": "Electricity Bill / Month (R$)",
            "staff": "Staff Salaries / Month (R$)", "d_net": "Daily Net Profit",
            "m_net": "Monthly Net Profit", "y_net": "Yearly Net Profit",
            "rev_lbl": "Revenue: R$ {r:,} ({tx} sales)",
            "chat_hdr": "Executive Strategy Chat (Business Topics Only)",
            "chat_ph": "Ask about profit margins, stock, pricing, or global expansion...",
            "quick_btn": "📊 Run Full Profit & Growth Audit Now",
            "no_key": "GEMINI_API_KEY is missing in .streamlit/secrets.toml.",
        },
        "P": {
            "hdr": "🤖 Gerente Executivo de IA & Estrategista Global",
            "login_sub": "Acesso Único do Gerente (Salvo Automaticamente)",
            "email": "E-mail do Gerente", "pw": "Senha", "login_btn": "Desbloquear Gerente IA",
            "login_err": "Digite um e-mail válido e senha (mínimo 4 caracteres).",
            "fixed_hdr": "Custos Fixos Mensais e Custo Unitário (R$ Inteiros)",
            "buy_cost": "Custo Médio Compra / Unid. (R$)", "rent": "Aluguel da Loja / Mês (R$)",
            "water": "Conta de Água / Mês (R$)", "elec": "Conta de Luz / Mês (R$)",
            "staff": "Salários Equipe / Mês (R$)", "d_net": "Lucro Líquido Diário",
            "m_net": "Lucro Líquido Mensal", "y_net": "Lucro Líquido Anual",
            "rev_lbl": "Faturamento: R$ {r:,} ({tx} vendas)",
            "chat_hdr": "Consultoria Executiva (Apenas Negócios)",
            "chat_ph": "Pergunte sobre lucro, estoque, preços ou expansão global...",
            "quick_btn": "📊 Gerar Auditoria Completa de Lucro e Crescimento",
            "no_key": "GEMINI_API_KEY ausente em .streamlit/secrets.toml.",
        },
    }[lang]

    st.header(L["hdr"])

    if not st.session_state.ai_logged_in:
        with st.form("ai_one_time_login"):
            st.subheader(L["login_sub"])
            email_in = st.text_input(L["email"], placeholder="manager@shop.com")
            pw_in = st.text_input(L["pw"], type="password")
            if st.form_submit_button(L["login_btn"], type="primary"):
                if "@" in email_in and len(pw_in.strip()) >= 4:
                    token = _make_auth_token(email_in, pw_in)
                    exp = datetime(2035, 12, 31)
                    cookies.set("ai_mgr_token", token, expires_at=exp, key="set_tok")
                    cookies.set("ai_mgr_email", email_in.strip(), expires_at=exp, key="set_em")
                    st.session_state.ai_logged_in = True
                    st.session_state.ai_user_email = email_in.strip()
                    st.rerun()
                else:
                    st.error(L["login_err"])
        return

    today_br = datetime.now(pytz.timezone("America/Sao_Paulo")).date()
    fin = _compute_financials(shop, today_br)
    total_stock_units, stock_text = _fetch_stock_summary()

    with st.expander(L["fixed_hdr"], expanded=True):
        c1, c2, c3, c4, c5 = st.columns(5)
        avg_buy = int(c1.number_input(L["buy_cost"], min_value=1, max_value=500, value=14, step=1))
        rent = int(c2.number_input(L["rent"], min_value=0, value=2500, step=100))
        water = int(c3.number_input(L["water"], min_value=0, value=180, step=10))
        elec = int(c4.number_input(L["elec"], min_value=0, value=450, step=10))
        staff = int(c5.number_input(L["staff"], min_value=0, value=3200, step=100))

    monthly_fixed = int(rent + water + elec + staff)
    days_in_month = calendar.monthrange(today_br.year, today_br.month)[1]
    daily_fixed = int(round(monthly_fixed / days_in_month))
    yearly_fixed = int(monthly_fixed * 12)

    d_cogs = int(fin["d_units"] * avg_buy)
    m_cogs = int(fin["m_units"] * avg_buy)
    y_cogs = int(fin["y_units"] * avg_buy)

    d_net = int(fin["d_rev"] - d_cogs - daily_fixed)
    m_net = int(fin["m_rev"] - m_cogs - monthly_fixed)
    y_net = int(fin["y_rev"] - y_cogs - yearly_fixed)

    k1, k2, k3 = st.columns(3)
    k1.metric(L["d_net"], f"R$ {d_net:,}", delta=L["rev_lbl"].format(r=fin["d_rev"], tx=fin["d_tx"]))
    k2.metric(L["m_net"], f"R$ {m_net:,}", delta=L["rev_lbl"].format(r=fin["m_rev"], tx=fin["m_tx"]))
    k3.metric(L["y_net"], f"R$ {y_net:,}", delta=L["rev_lbl"].format(r=fin["y_rev"], tx=fin["y_tx"]))

    st.divider()
    st.subheader(L["chat_hdr"])
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key:
        st.error(L["no_key"])
        return

    target_lang = "English" if lang == "E" else "Portuguese (Português do Brasil)"
    system_prompt = f"""
You are a seasoned, real-world Executive Business Manager and Global Market Strategist advising the owner of '{shop}' in Brazil.
STRICT RULES:
1. Respond EXCLUSIVELY in {target_lang}. Never switch to any other language.
2. Act strictly as a sharp, practical human business executive—never mention being an AI or language model.
3. Discuss ONLY business, retail operations, profit/loss, pricing, inventory, cash flow, and global/local market scaling strategies. If the user asks about anything non-business (sports, movies, casual trivia, coding, politics, personal life, etc.), politely decline in 1 sentence and redirect back to store profitability.
4. Always use whole-integer R$ values in your financial breakdowns.

LIVE STORE FINANCIAL SNAPSHOT ({today_br}):
- Shop: {shop}
- Daily Revenue: R$ {fin['d_rev']:,} ({fin['d_tx']} sales) | Daily COGS: R$ {d_cogs:,} | Daily Fixed Prorated: R$ {daily_fixed:,} | Daily Net Profit: R$ {d_net:,}
- Monthly Revenue: R$ {fin['m_rev']:,} ({fin['m_tx']} sales) | Monthly COGS: R$ {m_cogs:,} | Monthly Fixed Costs: R$ {monthly_fixed:,} (Rent R$ {rent:,}, Water R$ {water:,}, Electricity R$ {elec:,}, Staff R$ {staff:,}) | Monthly Net Profit: R$ {m_net:,}
- Yearly Revenue: R$ {fin['y_rev']:,} ({fin['y_tx']} sales) | Yearly COGS: R$ {y_cogs:,} | Yearly Fixed Costs: R$ {yearly_fixed:,} | Yearly Net Profit: R$ {y_net:,}
- Unit Economics Assumption: Avg Sale ~R$ 30, Avg Buying Cost R$ {avg_buy}
- Live Catalog & Stock:\n{stock_text}
""".strip()

    def ask_gemini(user_msg: str) -> str:
        try:
            client = genai.Client(api_key=api_key)
            history_text = "\n".join(
                f"{'Owner' if m['role'] == 'user' else 'Manager'}: {m['content']}"
                for m in st.session_state.ai_chat[-6:]
            )
            full_prompt = f"{history_text}\nOwner: {user_msg}" if history_text else user_msg
            active_model = next(
                (m.name for m in client.models.list() if "flash" in m.name and "generateContent" in (m.supported_actions or [])),
                "gemini-3.8-flash-lite"
            )
            resp = client.models.generate_content(
                model=active_model,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.4,
                ),
            )
            return resp.text
        except Exception as e:
            return f"⚠️ AI Error: {e}"
    
    if st.button(L["quick_btn"], type="primary"):
        audit_q = (
            "Analyze my current daily, monthly, and yearly net profit, break-even point, and give 3 high-impact scaling actions."
            if lang == "E"
            else "Analise meu lucro líquido diário, mensal e anual atual, ponto de equilíbrio e dê 3 ações práticas para escalar."
        )
        st.session_state.ai_chat.append({"role": "user", "content": audit_q})
        with st.spinner("..."):
            st.session_state.ai_chat.append({"role": "assistant", "content": ask_gemini(audit_q)})
        st.rerun()

    for msg in st.session_state.ai_chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input(L["chat_ph"]):
        st.session_state.ai_chat.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("..."):
                reply = ask_gemini(prompt)
                st.markdown(reply)
        st.session_state.ai_chat.append({"role": "assistant", "content": reply})
