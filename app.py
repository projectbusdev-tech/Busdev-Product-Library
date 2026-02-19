import streamlit as st
import pandas as pd
import os
import re
import urllib.parse
import uuid  # Menambahkan UUID untuk token verifikasi
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

# --- CREDENTIALS & USER DATABASE ---
ADMIN_USERS = {
    "admin": {"password": "admintn1", "role": "Admin"}
}

USER_DB_FILE = "users_db.csv"
HISTORY_FILE = "login_history.csv"

def load_registered_users():
    if os.path.exists(USER_DB_FILE):
        return pd.read_csv(USER_DB_FILE)
    # Menambahkan kolom 'Token' untuk alur pembuatan password
    return pd.DataFrame(columns=["Username", "Password", "Role", "Verified", "Token"])

def save_new_user(email):
    users_df = load_registered_users()
    if email in users_df['Username'].values:
        return False, "Email sudah terdaftar!", None
    
    # Generate token unik untuk link verifikasi
    token = str(uuid.uuid4())
    # User baru disimpan dengan password kosong dan Verified=False
    new_entry = pd.DataFrame([[email, "", "User", False, token]], 
                             columns=["Username", "Password", "Role", "Verified", "Token"])
    new_entry.to_csv(USER_DB_FILE, mode='a', header=not os.path.exists(USER_DB_FILE), index=False)
    return True, "Berhasil!", token

def update_user_password(token, new_password):
    users_df = load_registered_users()
    if token in users_df['Token'].values:
        users_df.loc[users_df['Token'] == token, 'Password'] = new_password
        users_df.loc[users_df['Token'] == token, 'Verified'] = True
        users_df.to_csv(USER_DB_FILE, index=False)
        return True
    return False

# --- SCREEN: SET PASSWORD (Halaman Pembuatan Password) ---
def set_password_screen(token):
    st.markdown("<h2 style='text-align: center;'>🔐 Buat Password Baru</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        users_df = load_registered_users()
        user_data = users_df[users_df['Token'] == token]
        
        if user_data.empty:
            st.error("Token verifikasi tidak valid.")
            if st.button("Kembali ke Login"):
                st.query_params.clear()
                st.rerun()
            return

        email = user_data.iloc[0]['Username']
        st.info(f"Mengatur password untuk: **{email}**")
        
        with st.form("set_password_form"):
            new_pass = st.text_input("Masukkan Password Baru", type="password")
            confirm_pass = st.text_input("Konfirmasi Password", type="password")
            btn_save = st.form_submit_button("Simpan & Aktifkan Akun")
            
            if btn_save:
                if len(new_pass) < 6:
                    st.error("Password minimal harus 6 karakter.")
                elif new_pass != confirm_pass:
                    st.error("Konfirmasi password tidak cocok.")
                else:
                    if update_user_password(token, new_pass):
                        st.success("Password berhasil disimpan! Silakan login.")
                        st.query_params.clear() # Bersihkan URL
                        st.rerun()

# --- DIALOG SIGN UP ---
@st.dialog("Sign Up")
def signup_dialog():
    st.write("Gunakan email @traknus.co.id atau @gmail.com (untuk tes).")
    email_input = st.text_input("Masukkan Email")
    
    if st.button("Daftar Sekarang"):
        if not email_input:
            st.error("Email tidak boleh kosong.")
        # Mendukung dua jenis domain sesuai permintaan
        elif not (email_input.endswith("@traknus.co.id") or email_input.endswith("@gmail.com")):
            st.error("Gunakan email @traknus.co.id atau @gmail.com")
        else:
            success, msg, token = save_new_user(email_input)
            if success:
                st.session_state.signup_success = True
                st.session_state.signup_token = token
                st.session_state.signup_email = email_input
            else:
                st.warning(msg)

    # Menampilkan pesan sukses persisten di dalam dialog
    if st.session_state.get('signup_success'):
        st.success(f"Link verifikasi telah dikirim ke {st.session_state.signup_email}")
        st.warning("Klik link di bawah ini (Simulasi Email):")
        # Link simulasi yang membawa token ke URL
        st.markdown(f"[✅ Verifikasi Akun & Buat Password](/?token={st.session_state.signup_token})")
        if st.button("Tutup"):
            st.session_state.signup_success = False
            st.rerun()

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
                if username in ADMIN_USERS and ADMIN_USERS[username]["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = ADMIN_USERS[username]["role"]
                    log_login(username, st.session_state.role)
                    st.rerun()
                else:
                    users_df = load_registered_users()
                    # Menambahkan pengecekan status Verified
                    match = users_df[(users_df['Username'] == username) & 
                                     (users_df['Password'] == password) & 
                                     (users_df['Verified'] == True)]
                    if not match.empty:
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.session_state.role = match.iloc[0]['Role']
                        log_login(username, st.session_state.role)
                        st.rerun()
                    else:
                        st.error("Email/Password salah atau akun belum diverifikasi.")
        
        st.write("---")
        if st.button("Sign Up"):
            signup_dialog()

# --- HELPER & DATA FUNCTIONS (Tetap sesuai kode asli Anda) ---
def get_actual_col(df, target_name):
    norm_target = re.sub(r'[\s_]+', '', target_name.lower())
    for col in df.columns:
        if re.sub(r'[\s_]+', '', col.lower()) == norm_target:
            return col
    return None

def clean_list_string(val):
    if pd.isna(val) or str(val).lower() == 'nan': return "-"
    return str(val).replace("[", "").replace("]", "").replace("'", "").strip()

def handle_reset():
    st.session_state.show_dialog = False
    st.session_state.show_compare = False
    st.session_state.detail_row = None
    st.session_state.filter_params = {} 

def click_detail(row):
    st.session_state.detail_row = row
    st.session_state.show_dialog = True
    st.session_state.show_compare = False

@st.cache_data
def load_data():
    try:
        df = pd.read_csv("Dataset_Normalized_Complete.csv", sep=";", encoding='latin1')
    except:
        df = pd.read_csv("Dataset_Normalized_Complete.csv", sep=";")
    df.columns = df.columns.str.strip() 
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

# --- POPUPS (Tetap sesuai kode asli Anda) ---
@st.dialog("Compare Product", width="large")
def show_comparison(base_row, full_df):
    st.write(f"Comparing: **{base_row['Brand']} - {base_row['Model Variations']}**")
    other_products = full_df[full_df['General Specifications'] != base_row['General Specifications']].copy()
    other_products['Display_Name'] = other_products['Brand'] + " - " + other_products['Model Variations'].fillna("")
    selected_names = st.multiselect("Select up to 2 products to compare:", options=other_products['Display_Name'].unique(), max_selections=2)
    labels = ["Product Type", "Aisle Width", "Max Slope", "Net Weight", "Dimensions (L/W/H)", "Total Dimensions (mm)", "Operation Mode", "Environment", "Power Source", "Application Location", "Floor Type", "Obstacle", "Waste Type"]
    
    def extract_compare_data(row):
        dims = f"{row.get('Measures_L','-')}/{row.get('Measures_W','-')}/{row.get('Measures_H','-')} mm"
        return [row.get('Product_type', '-'), f"{row.get('Aisle Width (cm)', '-')} cm", f"{row.get('Max_Slope', '-')}°", f"{row.get('Net Weight (kg)', '-')} Kg", dims, row.get('Measures_Total', '-'), row.get('Operation_mode', '-'), row.get('Environment', '-'), row.get('Power Source', '-'), clean_list_string(row.get(get_actual_col(full_df, 'Processed_Locations'))), clean_list_string(row.get(get_actual_col(full_df, 'Floor_Type_List'))), clean_list_string(row.get(get_actual_col(full_df, 'Obstacle_List'))), clean_list_string(row.get(get_actual_col(full_df, 'Waste_Type_List')))]

    data = {"Parameter": labels}
    base_model = base_row.get('Model Variations', '')
    base_model_str = f" - {base_model}" if pd.notna(base_model) and base_model != "" else ""
    data[f"Current: {base_row['Brand']}{base_model_str}"] = extract_compare_data(base_row)
    
    selected_rows = []
    for i, name in enumerate(selected_names):
        comp_row = other_products[other_products['Display_Name'] == name].iloc[0]
        selected_rows.append(comp_row)
        data[f"Product {i+2}: {name}"] = extract_compare_data(comp_row)
    
    num_cols = len(selected_names) + 1
    image_cols = st.columns([1.2] + [2] * num_cols)
    with image_cols[1]: st.image(get_image_path(base_row.get('General Specifications')), use_container_width=True)
    for i, comp_row in enumerate(selected_rows):
        with image_cols[i+2]: st.image(get_image_path(comp_row.get('General Specifications')), use_container_width=True)

    st.table(pd.DataFrame(data).set_index("Parameter"))
    if st.button("Close Comparison"):
        st.session_state.show_compare = False
        st.rerun()

@st.dialog("Product Details", width="large")
def show_detail(row, full_df):
    brand = row['Brand'] if not pd.isna(row['Brand']) else "-"
    model = row['Model Variations'] if not pd.isna(row['Model Variations']) else "-"
    aisle_w = row.get('Aisle Width (cm)', '-') 
    slope_val = row.get('Max_Slope', '-') 
    col_title, col_comp = st.columns([3, 1])
    with col_title: st.header(f"{brand} - {model}")
    with col_comp:
        if st.button("🔄 Compare Product", type="primary"):
            st.session_state.compare_base = row
            st.session_state.show_compare = True
            st.rerun()
    st.image(get_image_path(row.get('General Specifications')), width=250) 
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("General Specifications")
        st.write(f"**Product Type:** {row.get('Product_type', '-')}"); st.write(f"**Aisle Width:** :orange[**{aisle_w} cm**]"); st.write(f"**Max. Slope:** :red[**{slope_val}°**]"); st.write(f"**Operation Mode:** {row.get('Operation_mode', '-')}"); st.write(f"**Environment:** {row.get('Environment', '-')}"); st.write(f"**Power Source:** {row.get('Power Source', '-')}")
    with c2:
        st.subheader("Dimensions & Weight")
        st.write(f"**Net Weight:** {row.get('Net Weight (kg)', '-')} Kg"); st.write(f"**Dimensions (L/W/H):** {row.get('Measures_L','-')}/{row.get('Measures_W','-')}/{row.get('Measures_H','-')} mm"); st.write(f"**Total Dimensions:** {row.get('Measures_Total', '-')} mm")
    st.markdown("---")
    spec_name = str(row.get('General Specifications', '')).strip()
    found_path = os.path.join("static", "brochures", f"{spec_name}.pdf")
    if os.path.exists(found_path):
        col_dl, col_wa, col_email = st.columns(3) 
        with col_dl:
            with open(found_path, "rb") as pdf_file: st.download_button(label="📄 Download Brochure", data=pdf_file, file_name=f"{spec_name}.pdf", mime="application/pdf")
        public_url = f"{GITHUB_RAW_BASE}static/brochures/{urllib.parse.quote(spec_name)}.pdf" 
        share_msg = f"Check out this product: {brand} - {model}\nBrochure: {public_url}"
        with col_wa: st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(share_msg)}" target="_blank" class="custom-button wa-button">📲 WhatsApp</a>', unsafe_allow_html=True)
        with col_email: st.markdown(f'<a href="mailto:?subject={urllib.parse.quote(brand)}&body={urllib.parse.quote(share_msg)}" target="_blank" class="custom-button email-button">📧 Email</a>', unsafe_allow_html=True)
    else: st.info("Digital brochure is not yet available.")

# --- MAIN APP ---
def main():
    # Inisialisasi State dasar
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if 'form_key' not in st.session_state: st.session_state.form_key = 0
    if 'show_dialog' not in st.session_state: st.session_state.show_dialog = False
    if 'show_compare' not in st.session_state: st.session_state.show_compare = False

    # CEK QUERY PARAMETER (Untuk alur Verifikasi Email)
    query_params = st.query_params
    if "token" in query_params:
        set_password_screen(query_params["token"])
        return

    if not st.session_state.logged_in:
        login_screen()
        return

    # --- KONTEN SETELAH LOGIN ---
    st.sidebar.markdown(f"### Welcome, {st.session_state.username}!")
    pages = ["Product Library"]
    if st.session_state.role == "Admin": pages.append("Login History")
    selected_page = st.sidebar.selectbox("Navigate to", pages)

    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.rerun()

    if selected_page == "Login History":
        show_history_page()
    else:
        df = load_data()
        def get_uniques(col_name):
            actual = get_actual_col(df, col_name)
            if actual:
                temp = df[actual].dropna().astype(str).str.replace(r"[\[\]']", '', regex=True)
                return sorted([i for i in temp.str.split(',').explode().str.strip().unique() if i and i.lower() != 'nan'])
            return []

        st.sidebar.header("🎛️ Search Filters")
        if st.sidebar.button("🔄 Reset Filters"):
            handle_reset(); st.session_state.form_key += 1; st.rerun()

        # Filters logic (tetap sesuai kode asli Anda)
        pilihan_produk = st.sidebar.radio("Brand / Category", ["All", "Manual (Fiorentini)", "Autonomous (Gausium)"], key=f"r_{st.session_state.form_key}")
        filter_type = st.sidebar.multiselect("Product Type", sorted(df['Product_type'].dropna().unique().tolist()), key=f"t_{st.session_state.form_key}")
        filter_env = st.sidebar.multiselect("Environment", get_uniques('Environment'), key=f"e_{st.session_state.form_key}")
        filter_floor = st.sidebar.multiselect("Floor Type", get_uniques('Floor_Type_List'), key=f"f_{st.session_state.form_key}")
        filter_area = st.sidebar.number_input("Target Cleaning Area (m²/5h)", min_value=0, step=100, key=f"a_{st.session_state.form_key}")
        filter_slope = st.sidebar.number_input("Max Slope (°)", min_value=0, step=1, key=f"s_{st.session_state.form_key}")
        filter_aisle_cat = st.sidebar.multiselect("Aisle Category", get_uniques('Aisle Category'), key=f"ac_{st.session_state.form_key}")

        st.sidebar.markdown("---")
        obs_options = get_uniques('Obstacle_List'); selected_obstacles = []
        if obs_options:
            with st.sidebar.expander("Select Obstacles"):
                for obs in obs_options:
                    if st.checkbox(obs, key=f"o_{obs}_{st.session_state.form_key}"): selected_obstacles.append(obs)

        waste_options = get_uniques('Waste_Type_List'); selected_wastes = []
        if waste_options:
            with st.sidebar.expander("Select Waste Types"):
                for wst in waste_options:
                    if st.checkbox(wst, key=f"w_{wst}_{st.session_state.form_key}"): selected_wastes.append(wst)

        # Filtering Process
        res = df.copy()
        if pilihan_produk == "Manual (Fiorentini)": res = res[res['Brand'].str.contains("Fiorentini", case=False, na=False)]
        elif pilihan_produk == "Autonomous (Gausium)": res = res[res['Brand'].str.contains("Gausium", case=False, na=False)]
        if filter_type: res = res[res['Product_type'].isin(filter_type)]
        if filter_aisle_cat: res = res[res['Aisle Category'].isin(filter_aisle_cat)]
        if filter_slope > 0: res = res[pd.to_numeric(res['Max_Slope'], errors='coerce').fillna(0) >= filter_slope]
        if filter_area > 0: res = res[pd.to_numeric(res['Targeted Cleaning_Area'], errors='coerce').fillna(0) >= filter_area]

        def apply_list_filter(dataframe, target_col, selected_vals):
            if not selected_vals: return dataframe
            actual = get_actual_col(dataframe, target_col)
            if not actual: return dataframe
            pattern = "|".join([re.escape(str(v)) for v in selected_vals])
            return dataframe[dataframe[actual].astype(str).str.contains(pattern, flags=re.IGNORECASE, na=False)]

        res = apply_list_filter(res, 'Environment', filter_env)
        res = apply_list_filter(res, 'Floor_Type_List', filter_floor)
        res = apply_list_filter(res, 'Obstacle_List', selected_obstacles)
        res = apply_list_filter(res, 'Waste_Type_List', selected_wastes)

        st.divider()
        st.subheader(f"Results: {len(res)} Products Found")
        if len(res) > 0:
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
                
        if st.session_state.show_dialog and not st.session_state.show_compare:
            show_detail(st.session_state.detail_row, df)
        if st.session_state.show_compare:
            show_comparison(st.session_state.compare_base, df)

if __name__ == "__main__":
    main()
