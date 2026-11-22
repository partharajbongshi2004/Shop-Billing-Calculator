import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
from database import (
    get_product_by_code,
    insert_sale,
    get_daily_sales,
    delete_sale_by_id,
)

# Page Configuration
st.set_page_config(page_title="Multi-Shop POS System", page_icon="🛒", layout="wide")

# Initialize Session State for Cart
if "cart" not in st.session_state:
    st.session_state.cart = []

# Constants
SHOPS = ["Main Shop", "Second Shop"]
PAYMENT_METHODS = [
    "Dinheiro",
    "Pix",
    "Débito",
    "Crédito à Vista",
    "Crédito Parcelado",
]
BRAZIL_TZ = pytz.timezone("America/Sao_Paulo")
default_brazil_date = datetime.now(BRAZIL_TZ).date()

# --- HEADER & TOP CONTROLS ---
st.title("🛒 Multi-Shop POS Billing System")

top_col1, top_col2 = st.columns(2)
with top_col1:
    selected_shop = st.selectbox("Select Shop", SHOPS)
with top_col2:
    selected_date = st.date_input("Sale Date (Brazil Time)", value=default_brazil_date)

selected_date_str = selected_date.strftime("%Y-%m-%d")
st.divider()

# --- BILLING & CHECKOUT SECTION ---
left_col, right_col = st.columns([1.3, 1], gap="large")

with left_col:
    st.subheader("1. Add Products to Cart")
    
    with st.form("add_product_form", clear_on_submit=True):
        p_col1, p_col2, p_col3 = st.columns([2, 1, 1])
        with p_col1:
            prod_code = st.text_input("Product Code", placeholder="Enter code...")
        with p_col2:
            prod_qty = st.number_input("Quantity", min_value=1, step=1, value=1)
        with p_col3:
            st.write("")  # Vertical spacing alignment
            st.write("")
            add_submitted = st.form_submit_button("Add Item", use_container_width=True)

    if add_submitted:
        if not prod_code.strip():
            st.warning("Please enter a valid product code.")
        else:
            product = get_product_by_code(prod_code)
            if product:
                unit_price = int(product["price"])
                qty_int = int(prod_qty)
                line_total = unit_price * qty_int

                # Check if product already exists in cart to aggregate quantity
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
                            "total": line_total,
                        }
                    )
                st.success(f"Added {qty_int}x {product['name']} to cart.")
            else:
                st.error(f"Product code '{prod_code}' not found in database.")

    # Display Current Cart
    st.subheader("Current Cart")
    if st.session_state.cart:
        cart_df = pd.DataFrame(st.session_state.cart)
        cart_df.columns = ["Code", "Product Name", "Unit Price", "Qty", "Total"]
        st.dataframe(cart_df, use_container_width=True, hide_index=True)

        if st.button("🗑️ Clear Cart", type="secondary"):
            st.session_state.cart = []
            st.rerun()
    else:
        st.info("Cart is currently empty.")

with right_col:
    st.subheader("2. Checkout & Payment")

    subtotal = int(sum(item["total"] for item in st.session_state.cart))
    st.metric("Subtotal", f"R$ {subtotal:,}")

    discount = st.number_input(
        "Discount (Whole Integer)",
        min_value=0,
        max_value=subtotal if subtotal > 0 else 0,
        step=1,
        value=0,
    )
    discount_int = int(discount)
    total_bill = int(max(0, subtotal - discount_int))

    st.metric("Total Bill", f"R$ {total_bill:,}")

    payment_method = st.selectbox("Payment Method", PAYMENT_METHODS)

    installments = 1
    if payment_method == "Crédito Parcelado":
        installments = int(
            st.number_input("Installments (Parcelas)", min_value=2, max_value=24, step=1, value=2)
        )

    if payment_method == "Dinheiro":
        cash_given = int(
            st.number_input("Cash Given (Valor Recebido)", min_value=0, step=1, value=total_bill)
        )
        change_troco = cash_given - total_bill
        if change_troco >= 0:
            st.success(f"Change (Troco): R$ {change_troco:,}")
        else:
            st.error(f"Insufficient Cash! Missing: R$ {abs(change_troco):,}")

    # Complete Sale Button
    if st.button("✅ Complete & Save Sale", type="primary", use_container_width=True):
        if not st.session_state.cart:
            st.error("Cannot complete sale: Cart is empty.")
        elif payment_method == "Dinheiro" and cash_given < total_bill:
            st.error("Cash given is less than the total bill.")
        else:
            items_summary = ", ".join(
                [f"{item['qty']}x {item['name']} ({item['code']})" for item in st.session_state.cart]
            )
            sale_payload = {
                "sale_date": selected_date_str,
                "shop_name": selected_shop,
                "items_summary": items_summary,
                "subtotal": int(subtotal),
                "discount": int(discount_int),
                "total_bill": int(total_bill),
                "payment_method": payment_method,
                "installments": int(installments),
            }

            try:
                if insert_sale(sale_payload):
                    st.session_state.cart = []
                    st.success("Sale recorded successfully!")
                    st.rerun()
                else:
                    st.error("Failed to save sale to Supabase.")
            except Exception as e:
                st.error(f"Database error: {e}")

st.divider()

# --- LIVE DAILY SALES SUMMARY SECTION ---
st.header(f"📊 Live Daily Sales Summary — {selected_shop} ({selected_date_str})")

daily_sales = get_daily_sales(selected_date_str, selected_shop)

if daily_sales:
    sales_df = pd.DataFrame(daily_sales)

    # Calculate totals per payment method
    method_totals = {method: 0 for method in PAYMENT_METHODS}
    for row in daily_sales:
        pm = row.get("payment_method")
        amt = int(row.get("total_bill", 0))
        if pm in method_totals:
            method_totals[pm] += amt

    grand_total = int(sum(method_totals.values()))

    # Display Metric Cards
    m_cols = st.columns(6)
    for idx, method in enumerate(PAYMENT_METHODS):
        with m_cols[idx]:
            st.metric(method, f"R$ {method_totals[method]:,}")
    with m_cols[5]:
        st.metric("Grand Total", f"R$ {grand_total:,}")

    # Sales Table
    st.subheader("Transactions Log")
    display_cols = [
        "id",
        "sale_date",
        "shop_name",
        "items_summary",
        "subtotal",
        "discount",
        "total_bill",
        "payment_method",
        "installments",
    ]
    available_cols = [c for c in display_cols if c in sales_df.columns]
    st.dataframe(sales_df[available_cols], use_container_width=True, hide_index=True)

    # Action Row: CSV Export, Delete Entry, and End of Day Webhook
    act_col1, act_col2, act_col3 = st.columns([1, 1.2, 1.3], gap="medium")

    with act_col1:
        st.subheader("Export Data")
        csv_data = sales_df[available_cols].to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Daily Sales CSV",
            data=csv_data,
            file_name=f"sales_{selected_shop.replace(' ', '_').lower()}_{selected_date_str}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with act_col2:
        st.subheader("Delete Entry")
        del_col_a, del_col_b = st.columns([1.2, 1])
        with del_col_a:
            delete_id = st.number_input(
                "Sale ID to Delete", min_value=1, step=1, label_visibility="collapsed"
            )
        with del_col_b:
            if st.button("🗑️ Delete Sale", use_container_width=True):
                try:
                    if delete_sale_by_id(int(delete_id), selected_shop):
                        st.success(f"Sale ID {delete_id} deleted.")
                        st.rerun()
                    else:
                        st.warning(f"Sale ID {delete_id} not found for {selected_shop}.")
                except Exception as e:
                    st.error(f"Error deleting sale: {e}")

    with act_col3:
        st.subheader("End of Day Closing")
        if st.button("📤 Final Bill & Close Day / Send Report Now", type="primary", use_container_width=True):
            webhook_url = st.secrets.get("MAKE_WEBHOOK_URL", "")
            if not webhook_url:
                st.error("MAKE_WEBHOOK_URL is not configured in st.secrets.")
            else:
                report_payload = {
                    "date": selected_date_str,
                    "shop": selected_shop,
                    "total_sales": int(grand_total),
                    "transactions_count": int(len(daily_sales)),
                }
                try:
                    resp = requests.post(webhook_url, json=report_payload, timeout=10)
                    if resp.status_code in (200, 201, 202, 204):
                        st.success("Daily closing report sent successfully to webhook!")
                    else:
                        st.error(f"Webhook returned status {resp.status_code}: {resp.text}")
                except requests.RequestException as e:
                    st.error(f"Failed to send report: {e}")

else:
    st.info(f"No sales recorded yet for {selected_shop} on {selected_date_str}.")
