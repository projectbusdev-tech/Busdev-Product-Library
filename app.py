import streamlit as st
import pandas as pd
import os
import re
import urllib.parse
import uuid
from datetime import datetime, timedelta

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Product Recommendation Library", layout="wide")

# --- GITHUB RAW URL CONFIGURATION ---
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/aldre-arch/TN-Product-Reccomendation/main/"

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .stButton button, .stDownloadButton button {
        width: 100% !important;
        height: 42px !important;
    }
    .block-container { padding-top: 2rem; }
    .stContainer {
        min-height: 400px; 
        display: flex;
        flex-direction: column;
        justify-content: space-between; 
    }
    .stContainer img {
        height: 200px; 
        object-fit: contain; 
        width: 100%;
        padding-bottom: 10px; 
    }
    .custom-button {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        height: 42px;
        color: white !important;
        text-decoration: none;
        font-weight: 500;
        border-radius: 8px;
        border: none;
        cursor: pointer;
        font-size: 14px;
        transition: opacity 0.3s;
    }
    .custom-button:hover { opacity: 0.8; color: white !important; }
    .wa-button { background-color: #25D366; }
    .email-button { background-color: #0078D4; }
    .detail-card-content { flex-grow: 1; }
</style>
""", unsafe_allow_html=True)

# --- DATABASE LOGIC ---
ADMIN_USERS = {"admin": {"password": "admintn1", "role": "Admin"}}
USER_DB_FILE = "users_db.csv"
HISTORY_FILE = "login_history.csv"

def load_registered_users():
    cols = ["Username", "Password", "Role", "Verified", "Token"]
    if os.path.exists(USER_DB_FILE):
        try:
            df = pd.read_csv(USER_DB_FILE)
            for col in cols:
                if col not in df.columns:
                    df[col] = None if col != "Verified" else False
            return df
        except:
            if os.path.exists(USER_DB_FILE): os.remove(USER_DB_FILE)
            return pd.DataFrame(columns=cols)
    return pd.DataFrame(columns=cols)

def save_new_user(email):
    users_df = load_registered_users()
    if not users_df.empty and email in users_df['Username'].values:
        return False, "Email sudah terdaftar.", None
    token = str(uuid.uuid4())
    new_user = {"Username": email, "Password": "", "Role": "User", "Verified": False, "Token": token}
    new_df = pd.concat([users_df, pd.DataFrame([new_user])], ignore_index=True)
    new_df.to_csv(USER_DB_FILE, index=False)
    return True, "Berhasil!", token

def update_user_password(token, new_password):
    users_df = load_registered_users()
    if token in users_df['Token'].values:
        users_df.loc[users_df['Token'] == token, 'Password'] = new_password
        users_df.loc[users_df['Token'] == token, 'Verified'] = True
        users_df.to_csv(USER_DB_FILE, index=False)
        return True
    return False

# --- AUTH SCREENS ---
def set_password_screen(token):
    st.markdown("<h2 style='text-align: center;'>🔐 Buat Password Baru</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        users_df = load_registered_users()
        user_data = users_df[users_df['Token'] == token]
        if user_data.empty:
            st.error("Token tidak valid."); st.button("Kembali", on_click=lambda: st.query_params.clear())
            return
        with st.form("set_pass"):
            p1 = st.text_input("Password Baru", type="password")
            p2 = st.text_input("Konfirmasi Password", type="password")
            if st.form_submit_button("Aktifkan Akun"):
                if len(p1) < 6: st.error("Min. 6 karakter.")
                elif p1 != p2: st.error("Password tidak cocok.")
                else:
                    if update_user_password(token, p1):
                        st.success("Akun aktif!"); st.query_params.clear(); st.rerun()

@st.dialog("Sign Up")
def signup_dialog():
    email_input = st.text_input("Email (@traknus.co.id / @gmail.com)")
    if st.button("Daftar"):
        if email_input.endswith(("@traknus.co.id", "@gmail.com")):
            success, msg, token = save_new_user(email_input)
            if success:
                st.session_state.signup_done = True
                st.session_state.temp_token = token
            else: st.warning(msg)
        else: st.error("Email tidak valid.")
    if st.session_state.get('signup_done'):
        st.info("Simulasi Email dikirim!")
        st.markdown(f"[✅ KLIK UNTUK BUAT PASSWORD](/?token={st.session_state.temp_token})")

def login_screen():
    st.markdown("<h2 style='text-align: center;'>Product Library Login</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login"):
            u, p = st.text_input("Email"), st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                if u in ADMIN_USERS and ADMIN_USERS[u]["password"] == p:
                    st.session_state.update({"logged_in": True, "username": u, "role": "Admin"}); st.rerun()
                else:
                    users_df = load_registered_users()
                    match = users_df[(users_df['Username'] == u) & (users_df['Password'] == p) & (users_df['Verified'] == True)]
                    if not match.empty:
                        st.session_state.update({"logged_in": True, "username": u, "role": "User"}); st.rerun()
                    else: st.error("Login Gagal.")
        if st.button("Belum punya akun? Sign Up"): signup_dialog()

# --- PRODUCT LOGIC (FILTERS & HELPERS) ---
def get_actual_col(df, target_name):
    norm_target = re.sub(r'[\s_]+', '', target_name.lower())
    for col in df.columns:
        if re.sub(r'[\s_]+', '', col.lower()) == norm_target: return col
    return None

def clean_list_string(val):
    if pd.isna(val) or str(val).lower() == 'nan': return "-"
    return str(val).replace("[", "").replace("]", "").replace("'", "").strip()

@st.cache_data
def load_data():
    try: df = pd.read_csv("Dataset_Normalized_Complete.csv", sep=";", encoding='latin1')
    except: df = pd.read_csv("Dataset_Normalized_Complete.csv", sep=";")
    df.columns = df.columns.str.strip() 
    return df

def get_image_path(filename):
    if pd.isna(filename): return "https://via.placeholder.com/300x200?text=No+Image"
    base_path = os.path.join("static", "images")
    clean_name = str(filename).strip()
    for ext in [".jpg", ".png"]:
        if os.path.exists(os.path.join(base_path, clean_name + ext)): return os.path.join(base_path, clean_name + ext)
    return "https://via.placeholder.com/300x200?text=No+Image"

# --- PRODUCT POPUPS ---
@st.dialog("Compare Product", width="large")
def show_comparison(base_row, full_df):
    st.write(f"Comparing: **{base_row['Brand']} - {base_row['Model Variations']}**")
    other_products = full_df[full_df['General Specifications'] != base_row['General Specifications']].copy()
    other_products['Display_Name'] = other_products['Brand'] + " - " + other_products['Model Variations'].fillna("")
    selected_names = st.multiselect("Select up to 2 products:", options=other_products['Display_Name'].unique(), max_selections=2)
    
    labels = ["Product Type", "Aisle Width", "Max Slope", "Net Weight", "Dimensions (L/W/H)", "Operation Mode", "Power Source"]
    data = {"Parameter": labels}
    
    def extract(row):
        return [row.get('Product_type','-'), f"{row.get('Aisle Width (cm)','-')} cm", f"{row.get('Max_Slope','-')}°", f"{row.get('Net Weight (kg)','-')} Kg", f"{row.get('Measures_L','-')}/{row.get('Measures_W','-')} mm", row.get('Operation_mode','-'), row.get('Power Source','-')]

    data[f"Current: {base_row['Brand']}"] = extract(base_row)
    for i, name in enumerate(selected_names):
        comp_row = other_products[other_products['Display_Name'] == name].iloc[0]
        data[f"Product {i+2}: {name}"] = extract(comp_row)
    
    st.table(pd.DataFrame(data).set_index("Parameter"))

@st.dialog("Product Details", width="large")
def show_detail(row, full_df):
    col_t, col_c = st.columns([3, 1])
    with col_t: st.header(f"{row['Brand']} - {row['Model Variations']}")
    with col_c: 
        if st.button("🔄 Compare"): show_comparison(row, full_df)
    
    st.image(get_image_path(row.get('General Specifications')), width=250)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Specs")
        st.write(f"**Type:** {row.get('Product_type','-')}")
        st.write(f"**Aisle:** {row.get('Aisle Width (cm)','-')} cm")
        st.write(f"**Slope:** {row.get('Max_Slope','-')}°")
    with col2:
        st.subheader("Dimensions")
        st.write(f"**Weight:** {row.get('Net Weight (kg)','-')} Kg")
        st.write(f"**Size:** {row.get('Measures_L','-')}x{row.get('Measures_W','-')} mm")

    spec_name = str(row.get('General Specifications', '')).strip()
    found_path = os.path.join("static", "brochures", f"{spec_name}.pdf")
    if os.path.exists(found_path):
        with open(found_path, "rb") as f: st.download_button("📄 Download Brochure", f, f"{spec_name}.pdf")

# --- MAIN APP ---
def main():
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    
    q = st.query_params
    if "token" in q: set_password_screen(q["token"]); return

    if not st.session_state.logged_in:
        login_screen()
    else:
        # --- SIDEBAR & LOGOUT ---
        st.sidebar.title(f"Welcome, {st.session_state.username}")
        if st.sidebar.button("Logout"): st.session_state.logged_in = False; st.rerun()

        df = load_data()
        
        # --- RE-INTEGRATING ALL FILTERS ---
        st.sidebar.header("🎛️ Search Filters")
        
        def get_uniques(col_name):
            actual = get_actual_col(df, col_name)
            if actual:
                temp = df[actual].dropna().astype(str).str.replace(r"[\[\]']", '', regex=True)
                return sorted([i for i in temp.str.split(',').explode().str.strip().unique() if i and i.lower() != 'nan'])
            return []

        pilihan_produk = st.sidebar.radio("Brand / Category", ["All", "Manual (Fiorentini)", "Autonomous (Gausium)"])
        filter_type = st.sidebar.multiselect("Product Type", sorted(df['Product_type'].dropna().unique().tolist()))
        filter_env = st.sidebar.multiselect("Environment", get_uniques('Environment'))
        filter_floor = st.sidebar.multiselect("Floor Type", get_uniques('Floor_Type_List'))
        filter_area = st.sidebar.number_input("Target Cleaning Area (m²/5h)", min_value=0, step=100)
        filter_slope = st.sidebar.number_input("Max Slope (°)", min_value=0, step=1)
        
        # Filter Logic
        res = df.copy()
        if pilihan_produk == "Manual (Fiorentini)": res = res[res['Brand'].str.contains("Fiorentini", case=False, na=False)]
        elif pilihan_produk == "Autonomous (Gausium)": res = res[res['Brand'].str.contains("Gausium", case=False, na=False)]
        
        if filter_type: res = res[res['Product_type'].isin(filter_type)]
        if filter_slope > 0:
            res['ts'] = pd.to_numeric(res['Max_Slope'], errors='coerce').fillna(0)
            res = res[res['ts'] >= filter_slope]
            
        def apply_list_filter(dataframe, target_col, selected_vals):
            if not selected_vals: return dataframe
            actual = get_actual_col(dataframe, target_col)
            if not actual: return dataframe
            pattern = "|".join([re.escape(str(v)) for v in selected_vals])
            return dataframe[dataframe[actual].astype(str).str.contains(pattern, flags=re.IGNORECASE, na=False)]

        res = apply_list_filter(res, 'Environment', filter_env)
        res = apply_list_filter(res, 'Floor_Type_List', filter_floor)

        # Main Display
        st.title("Product Recommendation Library")
        st.subheader(f"Results: {len(res)} Products Found")
        
        if not res.empty:
            cols = st.columns(3)
            for idx, (index, row) in enumerate(res.iterrows()):
                with cols[idx % 3]:
                    with st.container(border=True):
                        st.image(get_image_path(row['General Specifications']))
                        st.markdown(f"**{row['Brand']}**")
                        st.caption(row.get('Model Variations', '-'))
                        if st.button("View Details", key=f"btn_{index}"):
                            show_detail(row, df)
        else:
            st.warning("No products match these filters.")

if __name__ == "__main__":
    main()
