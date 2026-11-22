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

def get_daily_sales(sale_date: str, shop_name: str) -> List[Dict[str, Any]]:
    """Retrieves all sales for a given date (YYYY-MM-DD) and shop."""
    supabase = init_supabase()
    response = (
        supabase.table("sales")
        .select("*")
        .eq("sale_date", sale_date)
        .eq("shop_name", shop_name)
        .order("id", desc=True)
        .execute()
    )
    return response.data if response.data else []

def delete_sale_by_id(sale_id: int, shop_name: str) -> bool:
    """Deletes a sale by its ID, restricted to the currently selected shop for safety."""
    supabase = init_supabase()
    response = (
        supabase.table("sales")
        .delete()
        .eq("id", int(sale_id))
        .eq("shop_name", shop_name)
        .execute()
    )
    return bool(response.data)
