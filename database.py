import streamlit as st
from supabase import create_client, Client
from typing import Optional, List, Dict, Any

@st.cache_resource
def init_supabase() -> Client:
    """Initializes and caches the Supabase client using Streamlit secrets."""
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def get_product_by_code(code: str) -> Optional[Dict[str, Any]]:
    """Fetches a single product from the 'products' table by its primary key 'code'."""
    supabase = init_supabase()
    clean_code = str(code).strip()
    if not clean_code:
        return None

    response = (
        supabase.table("products")
        .select("*")
        .eq("code", clean_code)
        .execute()
    )
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

def insert_sale(sale_data: Dict[str, Any]) -> bool:
    """Inserts a new sale record into the 'sales' table."""
    supabase = init_supabase()
    response = supabase.table("sales").insert(sale_data).execute()
    return bool(response.data)

def get_sales_by_date_range(start_date: str, end_date: str, shop_name: str) -> List[Dict[str, Any]]:
    """Retrieves all sales between start_date and end_date (inclusive, YYYY-MM-DD) for a shop."""
    supabase = init_supabase()
    response = (
        supabase.table("sales")
        .select("*")
        .gte("sale_date", start_date)
        .lte("sale_date", end_date)
        .eq("shop_name", shop_name)
        .order("sale_date", desc=True)
        .order("id", desc=True)
        .execute()
    )
    return response.data if response.data else []

def delete_sale_by_id(sale_id: int, shop_name: str) -> bool:
    """Deletes a sale by its ID, restricted to the currently selected shop."""
    supabase = init_supabase()
    response = (
        supabase.table("sales")
        .delete()
        .eq("id", int(sale_id))
        .eq("shop_name", shop_name)
        .execute()
    )
    return bool(response.data)

from datetime import date

def save_store_settings(email: str, whatsapp: str = "", daily_rent: int = 0, daily_staff_cost: int = 0) -> bool:
    """Saves or updates owner email, WhatsApp, and daily store expenses."""
    supabase = init_supabase()
    clean_email = str(email).strip().lower()
    if not clean_email:
        return False
    
    data = {
        "owner_email": clean_email,
        "whatsapp_number": str(whatsapp).strip(),
        "daily_rent": int(daily_rent),
        "daily_staff_cost": int(daily_staff_cost)
    }
    response = supabase.table("store_settings").upsert(data, on_conflict="owner_email").execute()
    return bool(response.data)

def get_store_settings(email: str) -> Optional[Dict[str, Any]]:
    """Fetches store settings and expenses for a verified owner email."""
    supabase = init_supabase()
    clean_email = str(email).strip().lower()
    response = supabase.table("store_settings").select("*").eq("owner_email", clean_email).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

def get_today_sales_summary(shop_name: str) -> Dict[str, Any]:
    """Fetches today's sales list for the AI Manager to analyze profit and trends."""
    supabase = init_supabase()
    today_str = str(date.today())
    response = (
        supabase.table("sales")
        .select("*")
        .eq("sale_date", today_str)
        .eq("shop_name", shop_name)
        .execute()
    )
    sales_list = response.data if response.data else []
    return {
        "date": today_str,
        "shop_name": shop_name,
        "total_bills": len(sales_list),
        "sales_records": sales_list
    }
