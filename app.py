import streamlit as st
import pandas as pd
import os
import re
import urllib.parse
import uuid  # Untuk token verifikasi unik
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

# --- DATABASE LOGIC (Sistem User) ---
ADMIN_USERS = {"admin": {"password": "admintn1", "role": "Admin"}}
USER_DB_FILE = "users_db.csv"
HISTORY_FILE = "login_history.csv"

def load_registered_users():
    cols = ["Username", "Password", "Role", "Verified", "Token"]
    if os.path.exists(USER_DB_FILE):
        try:
            df = pd.read_csv(USER_DB_FILE)
            # Validasi kolom agar tidak terjadi error jika format lama ditemukan
            for col in cols:
                if col not in df.columns:
                    df[col] = None if col != "Verified" else False
            return df
        except Exception:
            # Jika file rusak (ParserError), hapus dan buat baru
            if os.path.exists(USER_DB_FILE):
                os.remove(USER_DB_FILE)
            return pd.DataFrame(columns=cols)
    return pd.DataFrame(columns=cols)

def save_new_user(email):
    users_df = load_registered_users()
    if not users_df.empty and email in users_df['Username'].values:
        return False, "Email ini sudah terdaftar.", None
    
    token = str(uuid.uuid4())
    new_user = {
        "Username": email,
        "Password": "", # Kosong, akan diisi saat verifikasi
        "Role": "User",
        "Verified": False,
        "Token": token
    }
    
    # Simpan dengan menggabungkan ke dataframe utama
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

# --- SCREEN: SET PASSWORD (Mengecek URL ?token=...) ---
def set_password_screen(token):
    st.markdown("<h2 style='text-align: center;'>🔐 Buat Password Akun Baru</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        users_df = load_registered_users()
        user_data = users_df[users_df['Token'] == token]
        
        if user_data.empty:
            st.error("Token verifikasi tidak valid atau sudah kadaluarsa.")
            if st.button("Kembali ke Login"):
                st.query_params.clear()
                st.rerun()
            return

        email = user_data.iloc[0]['Username']
        st.info(f"Mengatur akun untuk: **{email}**")
        
        with st.form("form_password"):
            p1 = st.text_input("Password Baru", type="password")
            p2 = st.text_input("Konfirmasi Password", type="password")
            if st.form_submit_button("Aktifkan Akun & Login"):
                if len(p1) < 6:
                    st.error("Password minimal 6 karakter.")
                elif p1 != p2:
                    st.error("Password tidak cocok.")
                else:
                    if update_user_password(token, p1):
                        st.success("Akun aktif! Silakan login.")
                        st.query_params.clear()
                        st.rerun()

# --- DIALOG SIGN UP ---
@st.dialog("Pendaftaran Akun Baru")
def signup_dialog():
    st.write("Gunakan email @traknus.co.id atau @gmail.com (Tes).")
    email_input = st.text_input("Masukkan Email Anda")
    
    if st.button("Daftar Sekarang"):
        if not email_input:
            st.error("Email tidak boleh kosong.")
        elif not (email_input.endswith("@traknus.co.id") or email_input.endswith("@gmail.com")):
            st.error("Gunakan email @traknus.co.id atau @gmail.com")
        else:
            success, msg, token = save_new_user(email_input)
            if success:
                st.session_state.signup_done = True
                st.session_state.temp_token = token
                st.session_state.temp_email = email_input
            else:
                st.warning(msg)

    if st.session_state.get('signup_done'):
        st.success(f"Permintaan verifikasi untuk {st.session_state.temp_email} berhasil.")
        st.warning("Silakan klik link simulasi di bawah untuk membuat password:")
        st.markdown(f"[✅ KLIK DI SINI UNTUK BUAT PASSWORD](/?token={st.session_state.temp_token})")
        if st.button("Tutup"):
            st.session_state.signup_done = False
            st.rerun()

# --- LOGIN SCREEN ---
def login_screen():
    st.markdown("<h2 style='text-align: center;'>Product Library Login</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            user_in = st.text_input("Username / Email")
            pass_in = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                if user_in in ADMIN_USERS and ADMIN_USERS[user_in]["password"] == pass_in:
                    st.session_state.logged_in = True
                    st.session_state.username = user_in
                    st.session_state.role = ADMIN_USERS[user_in]["role"]
                    st.rerun()
                else:
                    users_df = load_registered_users()
                    match = users_df[(users_df['Username'] == user_in) & 
                                     (users_df['Password'] == pass_in) & 
                                     (users_df['Verified'] == True)]
                    if not match.empty:
                        st.session_state.logged_in = True
                        st.session_state.username = user_in
                        st.session_state.role = match.iloc[0]['Role']
                        st.rerun()
                    else:
                        st.error("Email/Password salah atau akun belum diaktifkan.")
        st.write("---")
        if st.button("Belum punya akun? Sign Up"):
            signup_dialog()

# --- FUNGSI PENDUKUNG PRODUK (Sama seperti sebelumnya) ---
def get_actual_col(df, target_name):
    norm_target = re.sub(r'[\s_]+', '', target_name.lower())
    for col in df.columns:
        if re.sub(r'[\s_]+', '', col.lower()) == norm_target:
            return col
    return None

def clean_list_string(val):
    if pd.isna(val) or str(val).lower() == 'nan': return "-"
    return str(val).replace("[", "").replace("]", "").replace("'", "").strip()

@st.cache_data
def load_data():
    try:
        df = pd.read_csv("Dataset_Normalized_Complete.csv", sep=";", encoding='latin1')
    except:
        df = pd.read_csv("Dataset_Normalized_Complete.csv", sep=";")
    df.columns = df.columns.str.strip() 
    return df

def get_image_path(filename):
    if pd.isna(filename): return "https://via.placeholder.com/300x200?text=No+Image"
    base_path = os.path.join("static", "images")
    clean_name = str(filename).strip()
    for ext in [".jpg", ".png"]:
        if os.path.exists(os.path.join(base_path, clean_name + ext)):
            return os.path.join(base_path, clean_name + ext)
    return "https://via.placeholder.com/300x200?text=No+Image"

# --- POPUPS ---
@st.dialog("Product Details", width="large")
def show_detail(row, full_df):
    brand = row['Brand'] if not pd.isna(row['Brand']) else "-"
    model = row['Model Variations'] if not pd.isna(row['Model Variations']) else "-"
    st.header(f"{brand} - {model}")
    st.image(get_image_path(row.get('General Specifications')), width=250)
    st.markdown("---")
    st.write(f"**Aisle Width:** {row.get('Aisle Width (cm)', '-')} cm")
    st.write(f"**Max. Slope:** {row.get('Max_Slope', '-')}°")
    # ... Detail lainnya sesuai app (3).py Anda ...

# --- MAIN APP ---
def main():
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    
    # CEK PARAMETER TOKEN DI URL
    q_params = st.query_params
    if "token" in q_params:
        set_password_screen(q_params["token"])
        return

    if not st.session_state.logged_in:
        login_screen()
    else:
        # TAMPILAN SETELAH LOGIN
        st.sidebar.title(f"Halo, {st.session_state.username}")
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()
            
        df = load_data()
        st.title("Product Recommendation Library")
        
        # --- LOGIKA FILTER (Sama seperti app (3).py Anda) ---
        st.sidebar.header("Filter")
        filter_env = st.sidebar.multiselect("Environment", sorted(df['Environment'].dropna().unique().tolist()))
        
        res = df.copy()
        if filter_env:
            res = res[res['Environment'].isin(filter_env)]
            
        st.write(f"Ditemukan {len(res)} Produk")
        
        if not res.empty:
            cols = st.columns(3)
            for idx, (index, row) in enumerate(res.iterrows()):
                with cols[idx % 3]:
                    with st.container(border=True):
                        st.image(get_image_path(row['General Specifications']))
                        st.markdown(f"**{row['Brand']}**")
                        if st.button("Details", key=f"det_{index}"):
                            show_detail(row, df)

if __name__ == "__main__":
    main()
