import streamlit as st
import pandas as pd
import requests
import calendar
from datetime import datetime
import pytz
from database import (
    get_product_by_code,
    insert_sale,
    get_sales_by_date_range,
    delete_sale_by_id,
)

# Page Configuration
st.set_page_config(page_title="Multi-Shop POS System", page_icon="🛒", layout="wide")

# Initialize Session State
if "cart" not in st.session_state:
    st.session_state.cart = []
if "lang" not in st.session_state:
    st.session_state.lang = "E"  # "E" = English, "P" = Português

# Timezone & Default Date
BRAZIL_TZ = pytz.timezone("America/Sao_Paulo")
today_br = datetime.now(BRAZIL_TZ).date()

# Constants
SHOPS = ["Main Shop", "Second Shop"]

# Standardized database keys for payment methods (always saved in Portuguese for DB consistency)
PAYMENT_KEYS = [
    "Dinheiro",
    "Pix",
    "Débito",
    "Crédito à Vista",
    "Crédito Parcelado",
]

PAYMENT_LABELS = {
    "E": {
        "Dinheiro": "Cash",
        "Pix": "Pix",
        "Débito": "Debit Card",
        "Crédito à Vista": "Credit Card (1x)",
        "Crédito Parcelado": "Credit Card (Installments)",
    },
    "P": {
        "Dinheiro": "Dinheiro",
        "Pix": "Pix",
        "Débito": "Débito",
        "Crédito à Vista": "Crédito à Vista",
        "Crédito Parcelado": "Crédito Parcelado",
    },
}

# Bilingual UI Dictionary
TEXT = {
    "E": {
        "title": "🛒 Multi-Shop POS Billing System",
        "select_shop": "Select Shop",
        "sale_date": "POS Sale Date (Brazil Time)",
        "add_products_header": "1. Add Products to Cart",
        "prod_code": "Product Code",
        "prod_code_ph": "Enter code...",
        "qty": "Quantity",
        "add_item_btn": "Add Item",
        "warn_enter_code": "Please enter a valid product code.",
        "added_msg": "Added {qty}x {name} to cart.",
        "not_found_msg": "Product code '{code}' not found in database.",
        "current_cart": "Current Cart",
        "cart_cols": ["Code", "Product Name", "Unit Price", "Qty", "Total"],
        "clear_cart": "🗑️ Clear Cart",
        "empty_cart": "Cart is currently empty.",
        "checkout_header": "2. Checkout & Payment",
        "subtotal": "Subtotal",
        "discount": "Discount (Whole Integer)",
        "total_bill": "Total Bill",
        "payment_method": "Payment Method",
        "installments": "Installments (Parcelas)",
        "cash_given": "Cash Given",
        "change_label": "Change (Troco): R$ {amt:,}",
        "insufficient_cash": "Insufficient Cash! Missing: R$ {amt:,}",
        "complete_sale_btn": "✅ Complete & Save Sale",
        "err_empty_cart": "Cannot complete sale: Cart is empty.",
        "err_less_cash": "Cash given is less than the total bill.",
        "sale_saved": "Sale recorded successfully!",
        "sale_failed": "Failed to save sale to Supabase.",
        "db_error": "Database error: {err}",
        "summary_header": "📊 Sales Summary & Reports — {shop}",
        "start_date": "Start Date",
        "end_date": "End Date",
        "this_month_btn": "📅 Select Full Current Month",
        "err_date_range": "Start Date cannot be after End Date.",
        "grand_total": "Grand Total",
        "tx_count": "Transactions",
        "tx_log": "Transactions & Sold Items Log",
        "export_header": "Export Data",
        "download_csv": "📥 Download Filtered Sales CSV",
        "delete_header": "Delete Entry",
        "delete_id_label": "Sale ID to Delete",
        "delete_btn": "🗑️ Delete Sale",
        "deleted_ok": "Sale ID {id} deleted.",
        "delete_not_found": "Sale ID {id} not found for {shop}.",
        "delete_err": "Error deleting sale: {err}",
        "eod_header": "End of Day & Email Report",
        "daily_report_btn": "📧 Send Daily Report Email",
        "monthly_report_btn": "📆 Send Monthly Report Email",
        "err_no_webhook": "MAKE_WEBHOOK_URL is not configured in st.secrets.",
        "webhook_ok": "{type} report sent successfully to webhook!",
        "webhook_fail": "Webhook returned status {code}: {text}",
        "webhook_err": "Failed to send report: {err}",
        "no_sales": "No sales recorded for {shop} between {start} and {end}.",
    },
    "P": {
        "title": "🛒 Sistema PDV Multi-Lojas",
        "select_shop": "Selecionar Loja",
        "sale_date": "Data da Venda PDV (Horário de Brasília)",
        "add_products_header": "1. Adicionar Produtos ao Carrinho",
        "prod_code": "Código do Produto",
        "prod_code_ph": "Digite o código...",
        "qty": "Quantidade",
        "add_item_btn": "Adicionar Item",
        "warn_enter_code": "Por favor, digite um código de produto válido.",
        "added_msg": "Adicionado {qty}x {name} ao carrinho.",
        "not_found_msg": "Código de produto '{code}' não encontrado no banco de dados.",
        "current_cart": "Carrinho Atual",
        "cart_cols": ["Código", "Produto", "Preço Unit.", "Qtd", "Total"],
        "clear_cart": "🗑️ Limpar Carrinho",
        "empty_cart": "O carrinho está vazio.",
        "checkout_header": "2. Finalizar Venda e Pagamento",
        "subtotal": "Subtotal",
        "discount": "Desconto (Valor Inteiro)",
        "total_bill": "Total da Conta",
        "payment_method": "Forma de Pagamento",
        "installments": "Parcelas",
        "cash_given": "Valor Recebido em Dinheiro",
        "change_label": "Troco: R$ {amt:,}",
        "insufficient_cash": "Valor insuficiente! Faltam: R$ {amt:,}",
        "complete_sale_btn": "✅ Finalizar e Salvar Venda",
        "err_empty_cart": "Não é possível finalizar: o carrinho está vazio.",
        "err_less_cash": "O valor recebido é menor que o total da conta.",
        "sale_saved": "Venda registrada com sucesso!",
        "sale_failed": "Falha ao salvar a venda no Supabase.",
        "db_error": "Erro no banco de dados: {err}",
        "summary_header": "📊 Resumo de Vendas e Relatórios — {shop}",
        "start_date": "Data Inicial",
        "end_date": "Data Final",
        "this_month_btn": "📅 Selecionar Mês Atual Completo",
        "err_date_range": "A Data Inicial não pode ser maior que a Data Final.",
        "grand_total": "Total Geral",
        "tx_count": "Transações",
        "tx_log": "Histórico de Vendas e Itens Vendidos",
        "export_header": "Exportar Dados",
        "download_csv": "📥 Baixar CSV de Vendas",
        "delete_header": "Excluir Lançamento",
        "delete_id_label": "ID da Venda para Excluir",
        "delete_btn": "🗑️ Excluir Venda",
        "deleted_ok": "Venda ID {id} excluída.",
        "delete_not_found": "Venda ID {id} não encontrada para {shop}.",
        "delete_err": "Erro ao excluir venda: {err}",
        "eod_header": "Fechamento e Relatório por E-mail",
        "daily_report_btn": "📧 Enviar Relatório Diário (E-mail)",
        "monthly_report_btn": "📆 Enviar Relatório Mensal (E-mail)",
        "err_no_webhook": "MAKE_WEBHOOK_URL não está configurado em st.secrets.",
        "webhook_ok": "Relatório ({type}) enviado com sucesso!",
        "webhook_fail": "O webhook retornou status {code}: {text}",
        "webhook_err": "Falha ao enviar relatório: {err}",
        "no_sales": "Nenhuma venda registrada para {shop} entre {start} e {end}.",
    },
}

lang = st.session_state.lang
t = TEXT[lang]

# --- TOP HEADER & LANGUAGE TOGGLE ("E" / "P") ---
head_col1, head_col2 = st.columns([5, 1])
with head_col1:
    st.title(t["title"])
with head_col2:
    st.write("")  # Vertical alignment
    lang_col1, lang_col2 = st.columns(2)
    with lang_col1:
        if st.button(
            "E",
            type="primary" if lang == "E" else "secondary",
            use_container_width=True,
            help="English",
        ):
            st.session_state.lang = "E"
            st.rerun()
    with lang_col2:
        if st.button(
            "P",
            type="primary" if lang == "P" else "secondary",
            use_container_width=True,
            help="Português",
        ):
            st.session_state.lang = "P"
            st.rerun()

# Top Shop & POS Date Selectors
top_col1, top_col2 = st.columns(2)
with top_col1:
    selected_shop = st.selectbox(t["select_shop"], SHOPS)
with top_col2:
    pos_date = st.date_input(t["sale_date"], value=today_br)

pos_date_str = pos_date.strftime("%Y-%m-%d")
st.divider()

# --- BILLING & CHECKOUT SECTION ---
left_col, right_col = st.columns([1.3, 1], gap="large")

with left_col:
    st.subheader(t["add_products_header"])

    with st.form("add_product_form", clear_on_submit=True):
        p_col1, p_col2, p_col3 = st.columns([2, 1, 1.2])
        with p_col1:
            prod_code = st.text_input(t["prod_code"], placeholder=t["prod_code_ph"])
        with p_col2:
            prod_qty = st.number_input(t["qty"], min_value=1, step=1, value=1)
        with p_col3:
            st.write("")
            st.write("")
            add_submitted = st.form_submit_button(t["add_item_btn"], use_container_width=True)

    if add_submitted:
        if not prod_code.strip():
            st.warning(t["warn_enter_code"])
        else:
            product = get_product_by_code(prod_code)
            if product:
                unit_price = int(product["price"])
                qty_int = int(prod_qty)
                line_total = unit_price * qty_int

                existing_item = next(
                    (item for item in st.session_state.cart if item["code"] == product["code"]),
                    None,
                )
                if existing_item:
                    existing_item["qty"] += qty_int
                    existing_item["total"] = existing_item["qty"] * existing_item["price"]
                else:
                    st.session_state.cart.append(
                        {
                            "code": product["code"],
                            "name": product["name"],
                            "price": unit_price,
                            "qty": qty_int,

