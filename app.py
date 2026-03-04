import streamlit as st
import pandas as pd
import os
import re
import urllib.parse
import io
import plotly.express as px
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

# --- DATABASE FUNCTIONS ---
def load_gsheet_data(worksheet_name):
    """Membaca data dari tab tertentu di Google Sheets."""
    try:
        return conn.read(worksheet=worksheet_name, ttl=0)
    except Exception:
        return pd.DataFrame()

def log_activity_to_gsheet(username, brand, model, record_type):
    try:
        # Nama worksheet tetap "DownloadHistory" agar tidak perlu ganti konfigurasi, 
        # tapi isinya kita perluas.
        history_df = load_gsheet_data("DownloadHistory")
        wib_now = datetime.now() + timedelta(hours=7)
        
        new_entry = pd.DataFrame([[
            wib_now.strftime("%Y-%m-%d %H:%M:%S"), 
            username, 
            brand, 
            model, 
            record_type
        ]], columns=["Timestamp", "Username", "Brand", "Model", "RecordType"])
        
        updated_df = pd.concat([history_df, new_entry], ignore_index=True)
        conn.update(worksheet="DownloadHistory", data=updated_df)
    except Exception as e:
        st.error(f"Gagal mencatat log {record_type}: {e}")

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

# --- PAGES ---

def show_product_analytics_page():
    st.title("📊 Product Analytics")
    
    history_df = load_gsheet_data("DownloadHistory")
    if history_df.empty:
        st.info("Belum ada data aktivitas.")
        return

    history_df['Timestamp'] = pd.to_datetime(history_df['Timestamp'])
    
    # Filter Role
    if st.session_state.role != "Admin":
        history_df = history_df[history_df['Username'] == st.session_state.username]

    st.subheader("🔍 Filters")
    c_f1, c_f2 = st.columns([2, 1])
    
    with c_f1:
        # 1. Filter Tanggal
        min_d, max_d = history_df['Timestamp'].min().date(), history_df['Timestamp'].max().date()
        date_range = st.date_input("Rentang Tanggal:", value=(min_d, max_d))
        
    with c_f2:
        # 2. Filter Jenis Aktivitas
        activity_options = ["All Activities", "Download", "WhatsApp", "Email"]
        selected_activity = st.selectbox("Jenis Aktivitas (untuk Grafik):", activity_options)

    # Logika Filter Tanggal
    if isinstance(date_range, tuple) and len(date_range) == 2:
        mask = (history_df['Timestamp'].dt.date >= date_range[0]) & (history_df['Timestamp'].dt.date <= date_range[1])
        df_filtered = history_df.loc[mask]
    else:
        df_filtered = history_df

    if not df_filtered.empty:
        # --- METRICS CARD (Kombinasi Count untuk Top Brand/Model) ---
        st.divider()
        m1, m2, m3, m4, m5 = st.columns(5)
        
        # Hitung untuk Card khusus
        total_dl = len(df_filtered[df_filtered['RecordType'] == 'Download'])
        total_wa = len(df_filtered[df_filtered['RecordType'] == 'WhatsApp'])
        total_em = len(df_filtered[df_filtered['RecordType'] == 'Email'])
        
        # Hitung Top (berdasarkan kombinasi semua aktivitas di range tgl tersebut)
        top_brand_df = df_filtered['Brand'].str.upper().value_counts().reset_index()
        top_model_df = df_filtered['Model'].value_counts().reset_index()
        
        max_b = top_brand_df['count'].max() if not top_brand_df.empty else 0
        b_name = " , ".join(top_brand_df[top_brand_df['count'] == max_b]['Brand'].tolist())
        
        max_m = top_model_df['count'].max() if not top_model_df.empty else 0
        m_name = " , ".join(top_model_df[top_model_df['count'] == max_m]['Model'].tolist())

        with m1: custom_metric("Total Downloads", f"{total_dl}x", "")
        with m2: custom_metric("WhatsApp Share", f"{total_wa}x", "")
        with m3: custom_metric("Email Share", f"{total_em}x", "")
        with m4: custom_metric("Top Brand (All)", b_name, f"{max_b} acts")
        with m5: custom_metric("Top Model (All)", m_name, f"{max_m} acts")

        # --- VISUALISASI (Berdasarkan Filter Aktivitas) ---
        st.write(f"### 📈 Charts: {selected_activity}")
        
        # Filter data khusus untuk grafik
        if selected_activity != "All Activities":
            df_chart = df_filtered[df_filtered['RecordType'] == selected_activity]
        else:
            df_chart = df_filtered

        if not df_chart.empty:
            chart_brand = df_chart['Brand'].str.upper().value_counts().reset_index()
            chart_model = df_chart['Model'].value_counts().reset_index()
            
            c1, c2 = st.columns(2)
            color_map = {'GAUSIUM': '#000000', 'FIORENTINI': '#0078D4'}

            with c1:
                fig_b = px.bar(chart_brand, x='Brand', y='count', color='Brand', color_discrete_map=color_map, text='Brand')
                fig_b.update_layout(height=450, showlegend=False, yaxis_title="Total Actions")
                fig_b.update_traces(textposition='inside', texttemplate='%{text}<br>%{y}', textfont=dict(size=16, color='white', family='Arial Black'))
                st.plotly_chart(fig_b, use_container_width=True)

            with c2:
                fig_m = px.bar(chart_model.head(10), x='count', y='Model', orientation='h', text='Model', color_discrete_sequence=['#2ECC71'])
                fig_m.update_layout(height=450, yaxis=dict(showticklabels=False))
                fig_m.update_traces(textposition='inside', texttemplate=' %{text} (%{x})', textfont=dict(size=14, color='white', family='Arial Black'))
                st.plotly_chart(fig_m, use_container_width=True)
        else:
            st.warning(f"Tidak ada data untuk kategori {selected_activity}")

    # Tabel Detail
    st.divider()
    st.subheader("📄 Activity Logs")
    st.dataframe(df_filtered[["Timestamp", "Username", "Brand", "Model", "RecordType"]].iloc[::-1], use_container_width=True)

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
def custom_metric(label, value, sub_value):
    st.markdown(f"""
        <div style="
            background-color: #f0f2f6;
            padding: 15px;
            border-radius: 10px;
            border-left: 5px solid #2ECC71;
            min-height: 120px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        ">
            <p style="font-size: 14px; color: #5f6368; margin: 0;">{label}</p>
            <p style="font-size: 18px; font-weight: bold; color: #262730; margin: 5px 0; line-height: 1.2; word-wrap: break-word;">
                {value}
            </p>
            <p style="font-size: 14px; color: #2ecc71; margin: 0; font-weight: 500;">
                ↑ {sub_value}
            </p>
        </div>
    """, unsafe_allow_html=True)

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

# --- IMAGE CHECKER FUNCTION ---
def get_image_path(filename):
    if pd.isna(filename):
        return "https://via.placeholder.com/300x200?text=No+Image"
    base_path = os.path.join("static", "images")
    clean_name = str(filename).strip()
    for ext in [".jpg", ".png"]:
        if os.path.exists(os.path.join(base_path, clean_name + ext)):
            return os.path.join(base_path, clean_name + ext)
    return "https://via.placeholder.com/300x200?text=No+Image"

# --- PRODUCT COMPARISON POPUP ---
@st.dialog("Compare Product", width="large")
def show_comparison(base_row, full_df):
    st.write(f"Comparing: **{base_row['Brand']} - {base_row['Model Variations']}**")
    
    other_products = full_df[full_df['General Specifications'] != base_row['General Specifications']].copy()
    other_products['Display_Name'] = other_products['Brand'] + " - " + other_products['Model Variations'].fillna("")
    
    selected_names = st.multiselect(
        "Select up to 2 products to compare:", 
        options=other_products['Display_Name'].unique(),
        max_selections=2
    )
    
    labels = [
        "Product Type", "Aisle Width", "Max Slope", "Net Weight", 
        "Dimensions (L/W/H)", "Total Dimensions (mm)", "Operation Mode",
        "Environment", "Power Source", "Application Location",
        "Floor Type", "Obstacle", "Waste Type"
    ]
    
    def extract_compare_data(row):
        dims = f"{row.get('Measures_L','-')}/{row.get('Measures_W','-')}/{row.get('Measures_H','-')} mm"
        return [
            row.get('Product_type', '-'),
            f"{row.get('Aisle Width (cm)', '-')} cm",
            f"{row.get('Max_Slope', '-')}°",
            f"{row.get('Net Weight (kg)', '-')} Kg",
            dims,
            row.get('Measures_Total', '-'),
            row.get('Operation_mode', '-'),
            row.get('Environment', '-'),
            row.get('Power Source', '-'),
            clean_list_string(row.get(get_actual_col(full_df, 'Processed_Locations'))),
            clean_list_string(row.get(get_actual_col(full_df, 'Floor_Type_List'))),
            clean_list_string(row.get(get_actual_col(full_df, 'Obstacle_List'))),
            clean_list_string(row.get(get_actual_col(full_df, 'Waste_Type_List')))
        ]

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
    
    with image_cols[1]:
        with st.container():
            st.image(get_image_path(base_row.get('General Specifications')), use_container_width=True)
    
    for i, comp_row in enumerate(selected_rows):
        with image_cols[i+2]:
            with st.container():
                st.image(get_image_path(comp_row.get('General Specifications')), use_container_width=True)

    st.table(pd.DataFrame(data).set_index("Parameter"))
    
    if st.button("Close Comparison"):
        st.session_state.show_compare = False
        st.rerun()

# --- PRODUCT DETAIL POPUP ---
@st.dialog("Product Details", width="large")
def show_detail(row, full_df):
    brand = row['Brand'] if not pd.isna(row['Brand']) else "-"
    model = row['Model Variations'] if not pd.isna(row['Model Variations']) else "-"
    aisle_w = row.get('Aisle Width (cm)', '-') 
    slope_val = row.get('Max_Slope', '-') 
    max_area = row.get('Targeted Cleaning_Area', '-')
    floor_type = clean_list_string(row.get('Floor_Type_List'))
    obstacles = clean_list_string(row.get('Obstacle_List'))
    waste_type = clean_list_string(row.get('Waste_Type_List'))

    col_title, col_comp = st.columns([3, 1])
    with col_title:
        st.header(f"{brand} - {model}")
    with col_comp:
        if st.button("🔄 Compare Product", type="primary"):
            st.session_state.compare_base = row
            st.session_state.show_compare = True
            st.session_state.show_dialog = False # Reset status dialog detail
            st.rerun()

    st.image(get_image_path(row.get('General Specifications')), width=250) 
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("General Specifications")
        st.write(f"**Product Type:** {row.get('Product_type', '-')}")
        st.write(f"**Aisle Width:** :orange[**{aisle_w} cm**]") 
        st.write(f"**Max. Slope:** :red[**{slope_val}°**]")
        st.write(f"**Max Target Cleaning Area:** :green[**{max_area} m²/5h**]")
        st.write(f"**Floor Type:** {floor_type}")
        st.write(f"**Obstacle:** {obstacles}")
        st.write(f"**Waste Type:** {waste_type}")
        st.write(f"**Operation Mode:** {row.get('Operation_mode', '-')}")
        st.write(f"**Environment:** {row.get('Environment', '-')}")
        st.write(f"**Power Source:** {row.get('Power Source', '-')}")
        
    with col2:
        st.subheader("Dimensions & Weight")
        st.write(f"**Net Weight:** {row.get('Net Weight (kg)', '-')} Kg")
        st.write(f"**Dimensions (L/W/H):** {row.get('Measures_L','-')}/{row.get('Measures_W','-')}/{row.get('Measures_H','-')} mm")
        st.write(f"**Total Dimensions:** {row.get('Measures_Total', '-')} mm")

    st.markdown("---")
    
    spec_name = str(row.get('General Specifications', '')).strip()
    found_path = os.path.join("static", "brochures", f"{spec_name}.pdf")
    spec_name_encoded = urllib.parse.quote(spec_name)
    
    if os.path.exists(found_path):
        col_dl, col_wa, col_email = st.columns(3) 
        with col_dl:
            with open(found_path, "rb") as pdf_file:
                # TRIGGER LOG: Jika tombol ditekan, jalankan fungsi log
                if st.download_button(
                    label="📄 Download Brochure", 
                    data=pdf_file, 
                    file_name=f"{spec_name}.pdf", 
                    mime="application/pdf",
                    key=f"dl_{spec_name}"
                ):
                    # PERBAIKAN: Tambahkan argumen ke-4 yaitu "Download"
                    log_activity_to_gsheet(st.session_state.username, brand, model, "Download")
                    st.success("Download tercatat!")

        public_url = f"{GITHUB_RAW_BASE}static/brochures/{spec_name_encoded}.pdf" 
        subject_mail = f"Product Specs: {brand} - {model}"
        share_msg = f"Check out this product: {brand} - {model}\nBrochure: {public_url}"
        
       with col_wa:
            wa_url = f"https://wa.me/?text={urllib.parse.quote(share_msg)}"
            # Gunakan st.link_button untuk menghindari blokir browser
            if st.link_button("📲 WhatsApp", wa_url, use_container_width=True):
                # Catatan: link_button di Streamlit akan membuka link dulu, 
                # lalu menjalankan kode di bawahnya (tergantung versi Streamlit)
                log_activity_to_gsheet(st.session_state.username, brand, model, "WhatsApp")
                
        with col_email:
            if st.button("📧 Email", key=f"em_{row.name}"):
                # 1. Catat aktivitas ke GSheet
                log_activity_to_gsheet(st.session_state.username, brand, model, "Email")
                
                # 2. Buka link Email secara otomatis
                email_url = f"mailto:?subject={urllib.parse.quote(subject_mail)}&body={urllib.parse.quote(share_msg)}"
                st.write(f'<meta http-equiv="refresh" content="0;url={email_url}">', unsafe_allow_html=True)
                st.toast("Email share recorded!")
    else:
        st.info("Digital brochure is not yet available.")


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
    st.sidebar.caption(f"Role: {st.session_state.role}")
    
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.rerun()
    
    pages = ["Product Library", "Product Analytics"]
    if st.session_state.role == "Admin":
        pages.extend(["Login History", "User Management"])
    
    selected_page = st.sidebar.selectbox("Navigate to", pages)

    if selected_page == "Product Analytics":
        show_product_analytics_page()
    elif selected_page == "Login History":
        show_history_page()
    elif selected_page == "User Management":
        show_user_management_page()
    else:
        df = load_data()

        def get_uniques(col_name):
            actual = get_actual_col(df, col_name)
            if actual:
                temp = df[actual].dropna().astype(str).str.replace(r"[\[\]']", '', regex=True)
                all_items = temp.str.split(',').explode().str.strip()
                return sorted([i for i in all_items.unique() if i and i.lower() != 'nan'])
            return []

        st.sidebar.header("🎛️ Search Filters")
        if st.sidebar.button("🔄 Reset Filters"):
            handle_reset()
            st.session_state.form_key += 1
            st.rerun()

        # --- REORDERED FILTERS ---
        # 1. Brand/Category
        pilihan_produk = st.sidebar.radio("Brand / Category", ["All", "Manual (Fiorentini)", "Autonomous (Gausium)"], key=f"radio_{st.session_state.form_key}")
        
        # 2. Product Type
        filter_type = st.sidebar.multiselect("Product Type", sorted(df['Product_type'].dropna().unique().tolist()) if 'Product_type' in df.columns else [], key=f"type_{st.session_state.form_key}")
        
        # 3. Environment
        filter_env = st.sidebar.multiselect("Environment", get_uniques('Environment'), key=f"env_{st.session_state.form_key}")
        
        # 4. Floor Type
        filter_floor = st.sidebar.multiselect("Floor Type", get_uniques('Floor_Type_List'), key=f"floor_{st.session_state.form_key}")
        
        # 5. Target Cleaning Area (m²/5h)
        filter_area = st.sidebar.number_input("Target Cleaning Area (m²/5h)", min_value=0, step=100, key=f"area_{st.session_state.form_key}")
        
        # 6. Max Slope
        filter_slope = st.sidebar.number_input("Max Slope (°)", min_value=0, step=1, key=f"slope_{st.session_state.form_key}")
        
        # 7. Aisle Category
        filter_aisle_cat = st.sidebar.multiselect("Aisle Category", get_uniques('Aisle Category'), key=f"aisle_{st.session_state.form_key}")

        # 8. Obstacle 
        st.sidebar.subheader("Obstacle Selection")
        obs_options = get_uniques('Obstacle_List')
        selected_obstacles = []
        if obs_options:
            with st.sidebar.expander(f"Select Obstacles ({len(obs_options)})"):
                for obs in obs_options:
                    if st.checkbox(obs, key=f"chk_obs_{obs}_{st.session_state.form_key}"):
                        selected_obstacles.append(obs)

        # 9. Waste Type
        st.sidebar.subheader("Waste Type Selection")
        waste_options = get_uniques('Waste_Type_List')
        selected_wastes = []
        if waste_options:
            with st.sidebar.expander(f"Select Waste Types ({len(waste_options)})"):
                for wst in waste_options:
                    if st.checkbox(wst, key=f"chk_wst_{wst}_{st.session_state.form_key}"):
                        selected_wastes.append(wst)

        # --- APPLY FILTERS ---
        res = df.copy()
        if pilihan_produk == "Manual (Fiorentini)":
            res = res[res['Brand'].str.contains("Fiorentini", case=False, na=False)]
        elif pilihan_produk == "Autonomous (Gausium)":
            res = res[res['Brand'].str.contains("Gausium", case=False, na=False)]
        if filter_type: res = res[res['Product_type'].isin(filter_type)]
        if filter_aisle_cat: res = res[res['Aisle Category'].isin(filter_aisle_cat)]
        if filter_slope > 0:
            res['temp_slope'] = pd.to_numeric(res['Max_Slope'], errors='coerce').fillna(0)
            res = res[res['temp_slope'] >= filter_slope]
        if filter_area > 0:
            res['Targeted Cleaning_Area'] = pd.to_numeric(res['Targeted Cleaning_Area'], errors='coerce').fillna(0)
            res = res[res['Targeted Cleaning_Area'] >= filter_area]

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
                
        # --- REVISI PEMANGGILAN DIALOG ---
        # 1. Menangani Popup Detail Produk
        if st.session_state.show_dialog and st.session_state.detail_row is not None:
            show_detail(st.session_state.detail_row, df)
            # KUNCI PERBAIKAN: Segera set ke False setelah fungsi dipanggil.
            # Ini akan membersihkan antrean sehingga saat filter sidebar diubah (rerun),
            # kondisi if ini tidak lagi terpenuhi secara otomatis.
            st.session_state.show_dialog = False
        
        # 2. Menangani Popup Perbandingan (Comparison)
        if st.session_state.show_compare:
            show_comparison(st.session_state.compare_base, df)
            st.session_state.show_compare = False # KUNCI PERBAIKAN

if __name__ == "__main__":
    main()

