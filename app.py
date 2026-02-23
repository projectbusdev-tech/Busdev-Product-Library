import streamlit as st
import pandas as pd
import os
import re
import urllib.parse
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Product Recommendation Library", layout="wide")

# --- DATABASE CONNECTION (GOOGLE SHEETS) ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Konfigurasi Secrets Google Sheets belum lengkap.")
    st.stop()

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

# --- CREDENTIALS & USER DATABASE (GSHEETS) ---
ADMIN_USERNAME = st.secrets["admin_credentials"]["username"]
ADMIN_PASSWORD = st.secrets["admin_credentials"]["password"]

ADMIN_USERS = {
    ADMIN_USERNAME: {"password": ADMIN_PASSWORD, "role": "Admin"}
}

HISTORY_FILE = "login_history.csv"

def load_registered_users():
    """Membaca data user dari Google Sheets secara real-time."""
    try:
        return conn.read(ttl=0)
    except Exception:
        return pd.DataFrame(columns=["Username", "Password", "Role", "Verified"])

def save_new_user(email, password):
    """Menyimpan user baru ke Google Sheets agar permanen."""
    users_df = load_registered_users()
    if email in users_df['Username'].values:
        return False, "Email sudah terdaftar!"
    
    new_entry = pd.DataFrame([[email, password, "User", True]], 
                             columns=["Username", "Password", "Role", "Verified"])
    
    # Gabungkan data lama dengan data baru
    updated_df = pd.concat([users_df, new_entry], ignore_index=True)
    
    # Update ke Google Sheets
    conn.update(data=updated_df)
    return True, "Akun berhasil dibuat secara permanen! Silakan login."

def delete_user_gsheet(email_to_delete):
    """Menghapus user dari Google Sheets."""
    users_df = load_registered_users()
    updated_df = users_df[users_df['Username'] != email_to_delete]
    conn.update(data=updated_df)
    return True

# --- DIALOG SIGN UP ---
@st.dialog("Sign Up")
def signup_dialog():
    st.write("Daftar akun baru untuk mengakses Product Library.")
    email_input = st.text_input("Email (@traknus.co.id)")
    password_input = st.text_input("Buat Password", type="password")
    confirm_password = st.text_input("Konfirmasi Password", type="password")
    
    if st.button("Daftar Sekarang"):
        if not email_input or not password_input:
            st.error("Email dan Password tidak boleh kosong.")
        elif not email_input.endswith("@traknus.co.id"):
            st.error("Maaf, hanya email @traknus.co.id yang diperbolehkan.")
        elif password_input != confirm_password:
            st.error("Konfirmasi password tidak cocok.")
        elif len(password_input) < 6:
            st.warning("Password minimal 6 karakter.")
        else:
            success, msg = save_new_user(email_input, password_input)
            if success:
                st.success(msg)
                st.balloons()
            else:
                st.warning(msg)

# --- HISTORY LOGIC ---
def log_login(username, role):
    wib_now = datetime.now() + timedelta(hours=7) 
    now_str = wib_now.strftime("%Y-%m-%d %H:%M:%S")
    new_entry = pd.DataFrame([[username, role, now_str]], columns=["Username", "Role", "Timestamp"])
    if not os.path.isfile(HISTORY_FILE):
        new_entry.to_csv(HISTORY_FILE, index=False)
    else:
        new_entry.to_csv(HISTORY_FILE, mode='a', header=False, index=False)

def show_history_page():
    st.title("📜 Login History")
    if os.path.exists(HISTORY_FILE):
        history_df = pd.read_csv(HISTORY_FILE)
        st.dataframe(history_df.iloc[::-1], use_container_width=True)
        if st.button("Clear History"):
            os.remove(HISTORY_FILE)
            st.rerun()
    else:
        st.info("No login history available.")

def login_screen():
    st.markdown("<h2 style='text-align: center;'>Product Library</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username / Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                # Cek Admin Hardcoded
                if username in ADMIN_USERS and ADMIN_USERS[username]["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = ADMIN_USERS[username]["role"]
                    log_login(username, st.session_state.role)
                    st.rerun()
                
                # Cek Database Google Sheets
                else:
                    users_df = load_registered_users()
                    match = users_df[(users_df['Username'] == username) & (users_df['Password'] == str(password))]
                    if not match.empty:
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.session_state.role = match.iloc[0]['Role']
                        log_login(username, st.session_state.role)
                        st.rerun()
                    else:
                        st.error("Invalid Username or Password")
        
        st.write("---")
        if st.button("Sign Up"):
            signup_dialog()

def show_user_management_page():
    st.title("👥 User Management")
    users_df = load_registered_users()
    
    if not users_df.empty:
        st.subheader("Registered Users (Google Sheets Database)")
        for index, row in users_df.iterrows():
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col1:
                st.write(f"**Email:** {row['Username']}")
            with col2:
                st.write(f"**Role:** {row['Role']}")
            with col3:
                status = "✅ Verified" if row['Verified'] else "❌ Unverified"
                st.write(status)
            with col4:
                if row['Username'] != st.session_state.username:
                    if st.button("Delete", key=f"del_{row['Username']}"):
                        delete_user_gsheet(row['Username'])
                        st.success(f"User {row['Username']} berhasil dihapus permanen!")
                        st.rerun()
                else:
                    st.write("(Current Admin)")
            st.divider()
    else:
        st.info("Belum ada user yang terdaftar di database.")

# --- HELPER FUNCTIONS ---
def get_actual_col(df, target_name):
    norm_target = re.sub(r'[\s_]+', '', target_name.lower())
    for col in df.columns:
        if re.sub(r'[\s_]+', '', col.lower()) == norm_target:
            return col
    return None

def clean_list_string(val):
    if pd.isna(val) or str(val).lower() == 'nan': return "-"
    return str(val).replace("[", "").replace("]", "").replace("'", "").strip()

# --- HANDLER LOGIC ---
def handle_reset():
    st.session_state.show_dialog = False
    st.session_state.show_compare = False
    st.session_state.detail_row = None
    st.session_state.filter_params = {} 

def click_detail(row):
    st.session_state.detail_row = row
    st.session_state.show_dialog = True
    st.session_state.show_compare = False

# --- LOAD DATA FUNCTION ---
@st.cache_data(ttl=3600)
def load_data():
    try:
        df = pd.read_csv("Dataset_Normalized_Complete.csv", sep=";", encoding='latin1')
    except:
        df = pd.read_csv("Dataset_Normalized_Complete.csv", sep=";")
    df.columns = df.columns.str.strip() 
    if 'Product_type' in df.columns:
        df['Product_type'] = df['Product_type'].astype(str).str.strip()
    return df

def get_image_path(filename):
    if pd.isna(filename):
        return "https://via.placeholder.com/300x200?text=No+Image"
    base_path = os.path.join("static", "images")
    clean_name = str(filename).strip()
    for ext in [".jpg", ".png"]:
        if os.path.exists(os.path.join(base_path, clean_name + ext)):
            return os.path.join(base_path, clean_name + ext)
    return "https://via.placeholder.com/300x200?text=No+Image"

# --- POPUP DIALOGS ---
@st.dialog("Compare Product", width="large")
def show_comparison(base_row, full_df):
    st.write(f"Comparing: **{base_row['Brand']} - {base_row['Model Variations']}**")
    other_products = full_df[full_df['General Specifications'] != base_row['General Specifications']].copy()
    other_products['Display_Name'] = other_products['Brand'] + " - " + other_products['Model Variations'].fillna("")
    
    selected_names = st.multiselect("Select up to 2 products:", options=other_products['Display_Name'].unique(), max_selections=2)
    
    labels = ["Product Type", "Aisle Width", "Max Slope", "Net Weight", "Dimensions", "Total Dim", "Operation", "Env", "Power", "Location", "Floor", "Obstacle", "Waste"]
    
    def extract_compare_data(row):
        return [row.get('Product_type', '-'), f"{row.get('Aisle Width (cm)', '-')} cm", f"{row.get('Max_Slope', '-')}°", f"{row.get('Net Weight (kg)', '-')} Kg", 
                f"{row.get('Measures_L','-')}/{row.get('Measures_W','-')}/{row.get('Measures_H','-')} mm", row.get('Measures_Total', '-'), row.get('Operation_mode', '-'), 
                row.get('Environment', '-'), row.get('Power Source', '-'), clean_list_string(row.get(get_actual_col(full_df, 'Processed_Locations'))),
                clean_list_string(row.get(get_actual_col(full_df, 'Floor_Type_List'))), clean_list_string(row.get(get_actual_col(full_df, 'Obstacle_List'))),
                clean_list_string(row.get(get_actual_col(full_df, 'Waste_Type_List')))]

    data = {"Parameter": labels}
    data[f"Current: {base_row['Brand']}"] = extract_compare_data(base_row)
    for i, name in enumerate(selected_names):
        comp_row = other_products[other_products['Display_Name'] == name].iloc[0]
        data[f"Product {i+2}: {name}"] = extract_compare_data(comp_row)
    
    st.table(pd.DataFrame(data).set_index("Parameter"))
    if st.button("Close Comparison"):
        st.session_state.show_compare = False
        st.rerun()

@st.dialog("Product Details", width="large")
def show_detail(row, full_df):
    col_title, col_comp = st.columns([3, 1])
    col_title.header(f"{row['Brand']} - {row['Model Variations']}")
    with col_comp:
        if st.button("🔄 Compare Product", type="primary"):
            st.session_state.compare_base = row
            st.session_state.show_compare = True
            st.session_state.show_dialog = False
            st.rerun()

    st.image(get_image_path(row.get('General Specifications')), width=250)
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Specifications")
        st.write(f"**Type:** {row.get('Product_type', '-')}")
        st.write(f"**Aisle Width:** {row.get('Aisle Width (cm)', '-')} cm")
        st.write(f"**Max Slope:** {row.get('Max_Slope', '-')}°")
    with c2:
        st.subheader("Dimensions & Weight")
        st.write(f"**Net Weight:** {row.get('Net Weight (kg)', '-')} Kg")
        st.write(f"**Total Dimensions:** {row.get('Measures_Total', '-')} mm")
    
    st.markdown("---")
    if st.button("Tutup Detail"):
        st.session_state.show_dialog = False
        st.rerun()

# --- MAIN APP ---
def main():
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if 'form_key' not in st.session_state: st.session_state.form_key = 0
    if 'show_dialog' not in st.session_state: st.session_state.show_dialog = False
    if 'show_compare' not in st.session_state: st.session_state.show_compare = False

    if not st.session_state.logged_in:
        login_screen()
        return

    st.sidebar.markdown(f"### Welcome, {st.session_state.username}!")
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.rerun()
    
    pages = ["Product Library"]
    if st.session_state.role == "Admin":
        pages.extend(["Login History", "User Management"])
    
    selected_page = st.sidebar.selectbox("Navigate to", pages)

    if selected_page == "Login History":
        show_history_page()
    elif selected_page == "User Management":
        show_user_management_page()
    else:
        df = load_data()
        
        # --- UI FILTER SIDEBAR ---
        st.sidebar.header("🎛️ Search Filters")
        if st.sidebar.button("🔄 Reset Filters"):
            handle_reset()
            st.session_state.form_key += 1
            st.rerun()

        pilihan_produk = st.sidebar.radio("Brand / Category", ["All", "Manual (Fiorentini)", "Autonomous (Gausium)"], key=f"radio_{st.session_state.form_key}")
        filter_type = st.sidebar.multiselect("Product Type", sorted(df['Product_type'].dropna().unique().tolist()), key=f"type_{st.session_state.form_key}")
        
        # --- APPLY FILTERS ---
        res = df.copy()
        if pilihan_produk == "Manual (Fiorentini)":
            res = res[res['Brand'].str.contains("Fiorentini", case=False, na=False)]
        elif pilihan_produk == "Autonomous (Gausium)":
            res = res[res['Brand'].str.contains("Gausium", case=False, na=False)]
        if filter_type: res = res[res['Product_type'].isin(filter_type)]

        st.divider()
        st.subheader(f"Results: {len(res)} Products Found")
        
        if not res.empty:
            cols = st.columns(3)
            for idx, (index, row) in enumerate(res.iterrows()):
                with cols[idx % 3]:
                    with st.container(border=True):
                        st.image(get_image_path(row['General Specifications']))
                        st.markdown(f"**{row['Brand']}**")
                        st.caption(row.get('Model Variations', '-'))
                        st.button("View Details", key=f"btn_{index}", on_click=click_detail, args=(row,))
        else:
            st.warning("No products match these filters.")
                
        # --- DIALOG HANDLER ---
        if st.session_state.show_dialog and st.session_state.detail_row is not None:
            show_detail(st.session_state.detail_row, df)
            st.session_state.show_dialog = False
        
        if st.session_state.show_compare:
            show_comparison(st.session_state.compare_base, df)

if __name__ == "__main__":
    main()
