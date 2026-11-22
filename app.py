import streamlit as st
import pandas as pd
import requests
import calendar
from datetime import datetime
import pytz
from database import get_product_by_code, insert_sale, get_sales_by_date_range, delete_sale_by_id

st.set_page_config(page_title="Multi-Shop POS", page_icon="🛒", layout="wide")
st.session_state.setdefault("cart", [])
st.session_state.setdefault("lang", "E")

today_br = datetime.now(pytz.timezone("America/Sao_Paulo")).date()
st.session_state.setdefault("f_start", today_br)
st.session_state.setdefault("f_end", today_br)

SHOPS = ["Main Shop", "Second Shop"]
PAY_KEYS = ["Dinheiro", "Pix", "Débito", "Crédito à Vista", "Crédito Parcelado"]
PAY_LABELS = {
    "E": {"Dinheiro": "Cash", "Pix": "Pix", "Débito": "Debit Card", "Crédito à Vista": "Credit Card (1x)", "Crédito Parcelado": "Credit Card (Installments)"},
    "P": {"Dinheiro": "Dinheiro", "Pix": "Pix", "Débito": "Débito", "Crédito à Vista": "Crédito à Vista", "Crédito Parcelado": "Crédito Parcelado"},
}

T = {
    "E": {
        "title": "🛒 Multi-Shop POS System", "shop": "Select Shop", "date": "POS Sale Date (Brazil)",
        "add_hdr": "1. Add Products", "code": "Product Code", "qty": "Qty", "add_btn": "Add Item",
        "not_found": "Product '{c}' not found.", "cart_hdr": "Current Cart", "clear": "🗑️ Clear Cart",
        "empty": "Cart is empty.", "cols": ["Code", "Product", "Price", "Qty", "Total"], "rm_item": "Remove Item",
        "pay_hdr": "2. Checkout & Payment", "sub": "Subtotal", "disc": "Discount (Integer)",
        "tot": "Total Bill", "pm": "Payment Method", "inst": "Installments (Parcelas)",
        "cash": "Cash Given", "troco": "Change (Troco): R$ {v:,}", "low_cash": "Missing: R$ {v:,}",
        "save_btn": "✅ Complete & Save Sale", "saved": "Sale saved!", "err_cart": "Cart is empty.",
        "hist_hdr": "📊 Sales History & Reports — {s}", "s_date": "Start Date", "e_date": "End Date",
        "month_btn": "📅 Full Current Month", "grand": "Grand Total", "csv": "📥 Download CSV",
        "del_id": "Sale ID", "del_btn": "🗑️ Delete Bill", "del_ok": "Sale #{id} deleted.",
        "del_no": "Sale #{id} not found.", "rep_hdr": "📧 End of Day / Month Email Report",
        "d_rep": "📧 Send Daily Report", "m_rep": "📆 Send Monthly Report",
        "rep_ok": "{t} report sent!", "no_hook": "MAKE_WEBHOOK_URL missing in secrets.", "no_sales": "No sales found.",
    },
    "P": {
        "title": "🛒 Sistema PDV Multi-Lojas", "shop": "Selecionar Loja", "date": "Data da Venda (Brasil)",
        "add_hdr": "1. Adicionar Produtos", "code": "Código do Produto", "qty": "Qtd", "add_btn": "Adicionar",
        "not_found": "Produto '{c}' não encontrado.", "cart_hdr": "Carrinho Atual", "clear": "🗑️ Limpar Carrinho",
        "empty": "Carrinho vazio.", "cols": ["Código", "Produto", "Preço", "Qtd", "Total"], "rm_item": "Remover Item",
        "pay_hdr": "2. Finalizar e Pagamento", "sub": "Subtotal", "disc": "Desconto (Inteiro)",
        "tot": "Total da Conta", "pm": "Forma de Pagamento", "inst": "Parcelas",
        "cash": "Valor Recebido", "troco": "Troco: R$ {v:,}", "low_cash": "Faltam: R$ {v:,}",
        "save_btn": "✅ Finalizar e Salvar Venda", "saved": "Venda salva!", "err_cart": "Carrinho vazio.",
        "hist_hdr": "📊 Histórico e Relatórios — {s}", "s_date": "Data Inicial", "e_date": "Data Final",
        "month_btn": "📅 Mês Atual Completo", "grand": "Total Geral", "csv": "📥 Baixar CSV",
        "del_id": "ID Venda", "del_btn": "🗑️ Excluir Venda", "del_ok": "Venda #{id} excluída.",
        "del_no": "Venda #{id} não encontrada.", "rep_hdr": "📧 Relatório por E-mail (Dia / Mês)",
        "d_rep": "📧 Send Daily Report", "m_rep": "📆 Send Monthly Report",
        "rep_ok": "Relatório ({t}) enviado!", "no_hook": "MAKE_WEBHOOK_URL ausente nos secrets.", "no_sales": "Nenhuma venda encontrada.",
    },
}

lang = st.session_state.lang
t = T[lang]

# --- TOP BAR: TITLE & LANGUAGE TOGGLE ("E" / "P") ---
h1, h2, h3 = st.columns([6, 0.6, 0.6])
h1.title(t["title"])
if h2.button("E", type="primary" if lang == "E" else "secondary", use_container_width=True):
    st.session_state.lang = "E"
    st.rerun()
if h3.button("P", type="primary" if lang == "P" else "secondary", use_container_width=True):
    st.session_state.lang = "P"
    st.rerun()

c_shop, c_date = st.columns(2)
shop = c_shop.selectbox(t["shop"], SHOPS)
pos_date = c_date.date_input(t["date"], value=today_br)
pos_date_str = pos_date.strftime("%Y-%m-%d")
st.divider()

# --- BILLING & CHECKOUT ---
col_left, col_right = st.columns([1.3, 1], gap="large")

with col_left:
    st.subheader(t["add_hdr"])
    with st.form("add_form", clear_on_submit=True):
        f1, f2, f3 = st.columns([2, 1, 1.2])
        p_code = f1.text_input(t["code"])
        p_qty = f2.number_input(t["qty"], min_value=1, step=1, value=1)
        f3.write(""); f3.write("")
        submitted = f3.form_submit_button(t["add_btn"], use_container_width=True)

    if submitted and p_code.strip():
        prod = get_product_by_code(p_code.strip())
        if prod:
            price, qty = int(prod["price"]), int(p_qty)
            existing = next((i for i in st.session_state.cart if i["code"] == prod["code"]), None)
            if existing:
                existing["qty"] += qty
                existing["total"] = existing["qty"] * price
            else:
                st.session_state.cart.append({"code": prod["code"], "name": prod["name"], "price": price, "qty": qty, "total": price * qty})
        else:
            st.error(t["not_found"].format(c=p_code))

    st.subheader(t["cart_hdr"])
    if st.session_state.cart:
        df_cart = pd.DataFrame(st.session_state.cart)
        df_cart.columns = t["cols"]
        st.dataframe(df_cart, use_container_width=True, hide_index=True)
        rm1, rm2, rm3 = st.columns([2, 1, 1])
        rm_code = rm1.selectbox(t["rm_item"], [i["code"] for i in st.session_state.cart], label_visibility="collapsed")
        if rm2.button(f"❌ {t['rm_item']}", use_container_width=True):
            st.session_state.cart = [i for i in st.session_state.cart if i["code"] != rm_code]
            st.rerun()
        if rm3.button(t["clear"], use_container_width=True):
            st.session_state.cart = []
            st.rerun()
    else:
        st.info(t["empty"])

with col_right:
    st.subheader(t["pay_hdr"])
    subtotal = int(sum(i["total"] for i in st.session_state.cart))
    st.metric(t["sub"], f"R$ {subtotal:,}")
    discount = int(st.number_input(t["disc"], min_value=0, max_value=max(0, subtotal), step=1, value=0))
    total_bill = int(max(0, subtotal - discount))
    st.metric(t["tot"], f"R$ {total_bill:,}")

    pay_key = st.selectbox(t["pm"], PAY_KEYS, format_func=lambda k: PAY_LABELS[lang][k])
    installments = int(st.number_input(t["inst"], min_value=2, max_value=24, step=1, value=2)) if pay_key == "Crédito Parcelado" else 1
    cash_given = total_bill
    if pay_key == "Dinheiro":
        cash_given = int(st.number_input(t["cash"], min_value=0, step=1, value=total_bill))
        troco = cash_given - total_bill
        st.success(t["troco"].format(v=troco)) if troco >= 0 else st.error(t["low_cash"].format(v=abs(troco)))

    if st.button(t["save_btn"], type="primary", use_container_width=True):
        if not st.session_state.cart:
            st.error(t["err_cart"])
        elif pay_key == "Dinheiro" and cash_given < total_bill:
            st.error(t["low_cash"].format(v=total_bill - cash_given))
        else:
            summary = ", ".join(f"{i['qty']}x {i['name']} ({i['code']})" for i in st.session_state.cart)
            payload = {
                "sale_date": pos_date_str, "shop_name": shop, "items_summary": summary,
                "subtotal": subtotal, "discount": discount, "total_bill": total_bill,
                "payment_method": pay_key, "installments": installments,
            }
            if insert_sale(payload):
                st.session_state.cart = []
                st.success(t["saved"])
                st.rerun()

st.divider()

# --- SALES HISTORY, FILTERS & EMAIL REPORTS ---
st.header(t["hist_hdr"].format(s=shop))
r1, r2, r3 = st.columns([1, 1, 1.2])
start_d = r1.date_input(t["s_date"], key="f_start")
end_d = r2.date_input(t["e_date"], key="f_end")
r3.write(""); r3.write("")
if r3.button(t["month_btn"], use_container_width=True):
    st.session_state.f_start = today_br.replace(day=1)
    st.session_state.f_end = today_br.replace(day=calendar.monthrange(today_br.year, today_br.month)[1])
    st.rerun()

s_str, e_str = start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d")
sales = get_sales_by_date_range(s_str, e_str, shop)

if sales:
    df_sales = pd.DataFrame(sales)
    totals = {k: sum(int(r["total_bill"]) for r in sales if r.get("payment_method") == k) for k in PAY_KEYS}
    m_cols = st.columns(6)
    for idx, k in enumerate(PAY_KEYS):
        m_cols[idx].metric(PAY_LABELS[lang][k], f"R$ {totals[k]:,}")
    m_cols[5].metric(t["grand"], f"R$ {sum(totals.values()):,}")

    df_view = df_sales.copy()
    df_view["payment_method"] = df_view["payment_method"].map(lambda k: PAY_LABELS[lang].get(k, k))
    st.dataframe(df_view, use_container_width=True, hide_index=True)
else:
    st.info(t["no_sales"])

a1, a2, a3 = st.columns([1, 1.1, 1.5], gap="medium")
with a1:
    csv_bytes = pd.DataFrame(sales).to_csv(index=False).encode("utf-8") if sales else b""
    st.download_button(t["csv"], data=csv_bytes, file_name=f"sales_{shop}_{s_str}_{e_str}.csv", mime="text/csv", disabled=not sales, use_container_width=True)

with a2:
    d1, d2 = st.columns([1, 1.2])
    del_id = d1.number_input(t["del_id"], min_value=1, step=1, label_visibility="collapsed")
    if d2.button(t["del_btn"], use_container_width=True):
        if delete_sale_by_id(int(del_id), shop):
            st.success(t["del_ok"].format(id=del_id)); st.rerun()
        else:
            st.warning(t["del_no"].format(id=del_id))

with a3:
    def trigger_webhook(rep_type: str, period: str, records: list):
        webhook_url = st.secrets.get("MAKE_WEBHOOK_URL", "")
        if not webhook_url:
            st.warning("Webhook URL not set")
            return
        if not records:
            st.info(t["no_sales"])
            return
        payload = {
            "report_type": rep_type,
            "period": period,
            "shop": shop,
            "total_sales": int(sum(int(r["total_bill"]) for r in records)),
            "transactions_count": len(records)
        }
        requests.post(webhook_url, json=payload)
        st.success("Report Sent!")

    if a3.button("📧 Daily Report", use_container_width=True):
        trigger_webhook("daily", f"{s_str} to {e_str}", sales)

    m_start = today_br.replace(day=1)
    m_last_day = calendar.monthrange(today_br.year, today_br.month)[1]
    m_end = today_br.replace(day=m_last_day)
    if a3.button("📅 Monthly Report", use_container_width=True):
        m_sales = get_sales_by_date_range(str(m_start), str(m_end), shop)
        trigger_webhook("monthly", f"{m_start} to {m_end}", m_sales)

