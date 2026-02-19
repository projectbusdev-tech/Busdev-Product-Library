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
    .stButton button, .stDownloadButton button { width: 100% !important; height: 42px !important; }
    .block-container { padding-top: 2rem; }
    .stContainer { min-height: 400px; display: flex; flex-direction: column; justify-content: space-between; }
    .stContainer img { height: 200px; object-fit: contain; width: 100%; padding-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- DATABASE & AUTH LOGIC ---
ADMIN_USERS = {"admin": {"password": "admintn1", "role": "Admin"}}
USER_DB_FILE = "users_db.csv"
HISTORY_FILE = "login_history.csv"

def load_registered_users():
    cols = ["Username", "Password", "Role", "Verified", "Token"]
    if os.path.exists(USER_DB_FILE):
        try:
            df = pd.read_csv(USER_DB_FILE)
            for col in cols:
                if col not in df.columns: df[col] = None if col != "Verified" else False
            return df
        except Exception:
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

def delete_user(username):
    users_df = load_registered_users()
    if username in users_df['Username'].values:
        users_df = users_df[users_df['Username'] != username]
        users_df.to_csv(USER_DB_FILE, index=False)
        return True
    return False

def update_user_password(token, new_password):
    users_df = load_registered_users()
    if token in users_df['Token'].values:
        users_df.loc[users_df['Token'] == token, 'Password'] = new_password
        users_df.loc[users_df['Token'] == token, 'Verified'] = True
        users_df.to_csv(USER_DB_FILE, index=False)
        return True
    return False

# --- SCREEN: SET PASSWORD ---
def set_password_screen(token):
    st.markdown("<h2 style='text-align: center;'>🔐 Aktivasi Akun</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        users_df = load_registered_users()
        user_data = users_df[users_df['Token'] == token]
        if user_data.empty:
            st.error("Token tidak valid."); st.button("Ke Login", on_click=lambda: st.query_params.clear())
            return
        st.info(f"Email: **{user_data.iloc[0]['Username']}**")
        with st.form("set_pass"):
            p1 = st.text_input("Password Baru", type="password")
            p2 = st.text_input("Konfirmasi Password", type="password")
            if st.form_submit_button("Aktifkan"):
                if len(p1) < 6: st.error("Minimal 6 karakter.")
                elif p1 != p2: st.error("Password tidak cocok.")
                else:
                    if update_user_password(token, p1):
                        st.success("Akun aktif!"); st.query_params.clear(); st.rerun()

# --- DIALOG SIGN UP ---
@st.dialog("Sign Up")
def signup_dialog():
    email = st.text_input("Email (@traknus.co.id / @gmail.com)")
    if st.button("Daftar"):
        if email and (email.endswith("@traknus.co.id") or email.endswith("@gmail.com")):
            success, msg, token = save_new_user(email)
            if success:
                st.session_state.signup_token = token
                st.session_state.signup_ok = True
            else: st.warning(msg)
        else: st.error("Email tidak valid.")
    if st.session_state.get('signup_ok'):
        st.success("Berhasil! Klik link di bawah untuk buat password:")
        st.markdown(f"[✅ Link Aktivasi](/?token={st.session_state.signup_token})")
        if st.button("Tutup"): st.session_state.signup_ok = False; st.rerun()

# --- LOGIN SCREEN ---
def login_screen():
    st.markdown("<h2 style='text-align: center;'>Product Recommendation Library</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            u = st.text_input("Email/Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                if u in ADMIN_USERS and ADMIN_USERS[u]["password"] == p:
                    st.session_state.logged_in, st.session_state.username, st.session_state.role = True, u, "Admin"
                    log_login(u, "Admin"); st.rerun()
                else:
                    db = load_registered_users()
                    match = db[(db['Username'] == u) & (db['Password'] == p) & (db['Verified'] == True)]
                    if not match.empty:
                        st.session_state.logged_in, st.session_state.username, st.session_state.role = True, u, "User"
                        log_login(u, "User"); st.rerun()
                    else: st.error("Gagal login atau akun belum aktif.")
        if st.button("Sign Up"): signup_dialog()

def log_login(username, role):
    wib = datetime.now() + timedelta(hours=7)
    df = pd.DataFrame([[username, role, wib.strftime("%Y-%m-%d %H:%M:%S")]], columns=["Username", "Role", "Timestamp"])
    df.to_csv(HISTORY_FILE, mode='a', header=not os.path.exists(HISTORY_FILE), index=False)

# --- FUNGSI PENDUKUNG (TETAP SAMA) ---
def get_actual_col(df, target):
    norm = re.sub(r'[\s_]+', '', target.lower())
    for c in df.columns:
        if re.sub(r'[\s_]+', '', c.lower()) == norm: return c
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
    base = os.path.join("static", "images")
    for ext in [".jpg", ".png"]:
        path = os.path.join(base, str(filename).strip() + ext)
        if os.path.exists(path): return path
    return "https://via.placeholder.com/300x200?text=No+Image"

# --- DIALOGS ---
@st.dialog("Compare Product", width="large")
def show_comparison(base_row, df):
    st.write(f"Comparing: **{base_row['Brand']} - {base_row['Model Variations']}**")
    other = df[df['General Specifications'] != base_row['General Specifications']].copy()
    other['Display'] = other['Brand'] + " - " + other['Model Variations'].fillna("")
    sel = st.multiselect("Select products:", options=other['Display'].unique(), max_selections=2)
    labels = ["Type", "Aisle Width", "Max Slope", "Weight", "Size", "Mode", "Power"]
    data = {"Parameter": labels}
    def get_s(r): return [r.get('Product_type','-'), f"{r.get('Aisle Width (cm)','-')} cm", f"{r.get('Max_Slope','-')}°", f"{r.get('Net Weight (kg)','-')} Kg", f"{r.get('Measures_L','-')}/{r.get('Measures_W','-')}/{r.get('Measures_H','-')} mm", r.get('Operation_mode','-'), r.get('Power Source','-')]
    data["Current"] = get_s(base_row)
    for i, n in enumerate(sel):
        r = other[other['Display'] == n].iloc[0]
        data[n] = get_s(r)
    st.table(pd.DataFrame(data).set_index("Parameter"))
    if st.button("Close"): st.session_state.show_compare = False; st.rerun()

@st.dialog("Details", width="large")
def show_detail(row, df):
    c_t, c_b = st.columns([3, 1])
    with c_t: st.header(f"{row['Brand']} - {row['Model Variations']}")
    with c_b: 
        if st.button("🔄 Compare"): st.session_state.compare_base = row; st.session_state.show_compare = True; st.rerun()
    st.image(get_image_path(row.get('General Specifications')), width=250)
    st.write(f"**Environment:** {clean_list_string(row.get('Environment'))}")
    st.write(f"**Obstacles:** {clean_list_string(row.get('Obstacle_List'))}")
    st.write(f"**Waste Type:** {clean_list_string(row.get('Waste_Type_List'))}")
    f_path = os.path.join("static", "brochures", f"{str(row.get('General Specifications')).strip()}.pdf")
    if os.path.exists(f_path):
        with open(f_path, "rb") as f: st.download_button("📄 Download Brochure", f, f_path)

# --- MAIN APP ---
def main():
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if "token" in st.query_params: set_password_screen(st.query_params["token"]); return
    if not st.session_state.logged_in: login_screen(); return

    # --- NAVIGATION MENU ---
    pages = ["Product Library"]
    if st.session_state.role == "Admin":
        pages.extend(["User Management", "Login History"])
    
    st.sidebar.markdown(f"### Welcome, {st.session_state.username}!")
    choice = st.sidebar.selectbox("Navigation", pages)
    if st.sidebar.button("Logout"): st.session_state.logged_in = False; st.rerun()

    if choice == "Product Library":
        df = load_data()
        st.sidebar.header("Filters")
        if st.sidebar.button("Reset Filters"): 
            st.session_state.form_key = st.session_state.get('form_key', 0) + 1
            st.rerun()
        
        fk = st.session_state.get('form_key', 0)
        pilihan = st.sidebar.radio("Brand", ["All", "Manual (Fiorentini)", "Autonomous (Gausium)"], key=f"p_{fk}")
        f_type = st.sidebar.multiselect("Type", sorted(df['Product_type'].dropna().unique()), key=f"t_{fk}")
        
        def get_u(col):
            act = get_actual_col(df, col)
            if act:
                tmp = df[act].dropna().astype(str).str.replace(r"[\[\]']", '', regex=True)
                return sorted([i.strip() for i in tmp.str.split(',').explode().unique() if i.strip() and i.lower() != 'nan'])
            return []

        f_env = st.sidebar.multiselect("Environment", get_u('Environment'), key=f"e_{fk}")
        f_obs = st.sidebar.multiselect("Obstacles", get_u('Obstacle_List'), key=f"o_{fk}")
        f_waste = st.sidebar.multiselect("Waste Type", get_u('Waste_Type_List'), key=f"w_{fk}")
        f_slope = st.sidebar.number_input("Max Slope (°)", 0, key=f"s_{fk}")

        res = df.copy()
        if pilihan == "Manual (Fiorentini)": res = res[res['Brand'].str.contains("Fiorentini", False)]
        elif pilihan == "Autonomous (Gausium)": res = res[res['Brand'].str.contains("Gausium", False)]
        if f_type: res = res[res['Product_type'].isin(f_type)]
        if f_slope > 0: res = res[pd.to_numeric(res['Max_Slope'], 'coerce').fillna(0) >= f_slope]

        def apply_f(d, col, vals):
            if not vals: return d
            act = get_actual_col(d, col)
            if not act: return d
            pat = "|".join([re.escape(str(v)) for v in vals])
            return d[d[act].astype(str).str.contains(pat, flags=re.IGNORECASE, na=False)]

        res = apply_f(res, 'Environment', f_env)
        res = apply_f(res, 'Obstacle_List', f_obs)
        res = apply_f(res, 'Waste_Type_List', f_waste)

        st.subheader(f"Results: {len(res)} Products Found")
        if not res.empty:
            cols = st.columns(3)
            for idx, (index, row) in enumerate(res.iterrows()):
                with cols[idx % 3]:
                    with st.container(border=True):
                        st.image(get_image_path(row['General Specifications']))
                        st.markdown(f"**{row['Brand']}**")
                        st.caption(row.get('Model Variations', '-'))
                        if st.button("View Details", key=f"b_{index}"):
                            st.session_state.detail_row = row
                            st.session_state.show_dialog = True
            
            if st.session_state.get('show_dialog') and not st.session_state.get('show_compare'):
                show_detail(st.session_state.detail_row, df)
            if st.session_state.get('show_compare'):
                show_comparison(st.session_state.compare_base, df)
        else: st.warning("No results.")

    elif choice == "User Management":
        st.header("👥 User Management")
        users_df = load_registered_users()
        if not users_df.empty:
            # Tampilkan tabel daftar user
            st.dataframe(users_df[["Username", "Role", "Verified", "Token"]], use_container_width=True)
            
            st.subheader("Hapus User")
            user_to_delete = st.selectbox("Pilih User yang akan dihapus:", users_df["Username"].tolist())
            if st.button("❌ Hapus User", type="primary"):
                if delete_user(user_to_delete):
                    st.success(f"User {user_to_delete} berhasil dihapus!")
                    st.rerun()
                else:
                    st.error("Gagal menghapus user.")
        else:
            st.info("Belum ada user yang terdaftar.")

    elif choice == "Login History":
        st.header("📊 Login History")
        if os.path.exists(HISTORY_FILE):
            st.dataframe(pd.read_csv(HISTORY_FILE).sort_values("Timestamp", ascending=False), use_container_width=True)
        else: st.info("No records.")

if __name__ == "__main__":
    main()
