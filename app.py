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

def log_filter_to_gsheet(username, filters):
    try:
        # Mengambil data lama dari sheet FilterLogs
        history_df = load_gsheet_data("FilterLogs")
        wib_now = datetime.now() + timedelta(hours=7)
        timestamp = wib_now.strftime("%Y-%m-%d %H:%M:%S")

        base_data = {
            "Timestamp": timestamp,
            "Username": username,
            "Brand_Filter": filters.get('brand', 'All'),
            "Area_Filter": filters.get('area', 0),
            "Slope_Filter": filters.get('slope', 0)
        }

        multi_map = {
            'Product Type': filters.get('product_type', []),
            'Environment': filters.get('environment', []),
            'Floor Type': filters.get('floor_type', []),
            'Aisle Category': filters.get('aisle_cat', []),
            'Obstacle': filters.get('obstacle', []),
            'Waste Type': filters.get('waste_type', [])
        }

        new_rows = []
        for category, values in multi_map.items():
            if isinstance(values, list) and len(values) > 0:
                for val in values:
                    row = base_data.copy()
                    row["Category"] = category
                    row["Value"] = val
                    new_rows.append(row)
            else:
                row = base_data.copy()
                row["Category"] = category
                row["Value"] = "All"
                new_rows.append(row)

        new_entries_df = pd.DataFrame(new_rows)
        updated_df = pd.concat([history_df, new_entries_df], ignore_index=True)
        conn.update(worksheet="FilterLogs", data=updated_df)
    except Exception as e:
        st.error(f"Gagal mencatat log filter: {e}")

def clear_gsheet_content(sheet_name):
    """Menghapus data di worksheet dengan menyisakan header saja."""
    try:
        # Buat DataFrame kosong dengan kolom yang sesuai
        if sheet_name == "LoginHistory":
            empty_df = pd.DataFrame(columns=["Username", "Role", "Timestamp", "Status"])
        else:
            # Sesuaikan untuk sheet lain jika perlu
            return False

        # Update sheet tersebut dengan DF kosong (hanya header)
        conn.update(worksheet=sheet_name, data=empty_df)
        return True
    except Exception as e:
        st.error(f"Gagal menghapus data: {e}")
        return False

def load_registered_users():
    try:
        # Membaca sheet Registered_Users
        df = conn.read(worksheet="UserAccount", ttl=0)

        # Memastikan Username dan Password selalu terbaca sebagai teks/string
        df['Username'] = df['Username'].astype(str).str.strip()
        df['Password'] = df['Password'].astype(str).str.strip()
        
        # Jika kolom Status belum ada, buat dan isi dengan Active (untuk legacy user)
        if 'ApprovalStatus' not in df.columns:
            df['ApprovalStatus'] = 'Active'
        else:
            df['ApprovalStatus'] = df['ApprovalStatus'].fillna('Active')
            
        if 'Role' not in df.columns:
            df['Role'] = 'User'
        else:
            df['Role'] = df['Role'].fillna('User')
        return df
    except Exception as e:
        st.error(f"Gagal memuat data user: {e}")
        return pd.DataFrame(columns=["Username", "Password", "Role", "Verified", "ApprovalStatus"])
        
def update_user_gsheet(updated_df):
    """Fungsi pembantu untuk menyimpan perubahan ke Google Sheets"""
    try:
        conn.update(worksheet="UserAccount", data=updated_df)
        return True
    except Exception as e:
        st.error(f"Gagal memperbarui database: {e}")
        return False


def save_new_user(email, password):
    users_df = load_registered_users()
    if email in users_df['Username'].values:
        return False, "Email sudah terdaftar."
    
    # User baru otomatis berstatus Pending
    new_user = pd.DataFrame([[email, password, "User", True, "Pending"]], columns=["Username", "Password", "Role", "Verified", "ApprovalStatus"])
    updated_df = pd.concat([users_df, new_user], ignore_index=True)
    
    try:
        conn.update(worksheet="UserAccount", data=updated_df)
        return True, "Registrasi berhasil! Mohon Menunggu Approval Admin untuk dapat login. silahkan follow-up ke tim Product Management 1"
    except Exception as e:
        return False, f"Gagal menyimpan data: {e}"

def delete_user_gsheet(email_to_delete):
    """Menghapus user dari Google Sheets."""
    users_df = load_registered_users()
    updated_df = users_df[users_df['Username'] != email_to_delete]
    conn.update(data=updated_df)
    return True

# --- ADMIN APPROVAL PAGE ---
def show_admin_approval_page():
    st.title("🛡️ User Approval Management")
    st.info("Halaman ini digunakan untuk menyetujui akses user baru.")
    
    users_df = load_registered_users()
    # Filter hanya yang berstatus Pending
    pending_users = users_df[users_df['ApprovalStatus'].str.lower() == 'pending']
    
    if pending_users.empty:
        st.success("Semua permintaan akun telah diproses. Tidak ada antrean baru.")
    else:
        for index, row in pending_users.iterrows():
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Request dari:** {row['Username']}")
                    st.caption(f"Status Saat Ini: {row['ApprovalStatus']}")
                with col2:
                    if st.button("Approve ✅", key=f"approve_{index}"):
                        users_df.at[index, 'ApprovalStatus'] = 'Active'
                        conn.update(worksheet="UserAccount", data=users_df)
                        st.success(f"Akun {row['Username']} diaktifkan!")
                        st.rerun()

# --- DIALOG SIGN UP ---
@st.dialog("Sign Up")
def signup_dialog():
    st.write("Daftar akun baru untuk mengakses Product Library.")
    email_input = st.text_input("Email (@traknus.co.id)").strip()
    password_input = st.text_input("Buat Password", type="password").strip()
    confirm_password = st.text_input("Konfirmasi Password", type="password").strip()
    
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

def convert_df_to_excel(df):
    output = io.BytesIO()
    # Menggunakan engine xlsxwriter agar lebih cepat dan ringan
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='UserAccount')
    return output.getvalue()

# --- PAGES ---

def show_product_analytics_page():
    st.title("📊 Product Analytics")
    
    history_df = load_gsheet_data("DownloadHistory")
    if history_df.empty:
        st.info("Belum ada data aktivitas.")
        return

    # LOGIKA PRIVASI DATA (USER-SPECIFIC)
    # Jika role bukan Admin, filter data agar hanya menampilkan milik username yang sedang login
    if st.session_state.role != "Admin":
        # Menggunakan str.lower() untuk memastikan perbandingan tidak sensitif huruf kapital
        history_df = history_df[history_df['Username'].str.lower() == st.session_state.username.lower()]

    # 2. Cek kembali apakah data ada setelah difilter
    if history_df.empty:
        st.info("Anda belum memiliki riwayat aktivitas produk untuk dianalisis.")
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
        st.write(f"### 📈 Charts: {selected_activity} Per Brand & Model")

        # Filter data khusus untuk grafik
        if selected_activity != "All Activities":
            df_chart = df_filtered[df_filtered['RecordType'] == selected_activity]
        else:
            df_chart = df_filtered

        if not df_chart.empty:
            chart_brand = df_chart['Brand'].str.upper().value_counts().reset_index()
            chart_model = df_chart['Model'].value_counts().reset_index()
    
            color_map = {'GAUSIUM': '#000000', 'FIORENTINI': '#0078D4'}

            plotly_config = {
                'displaylogo': False,
                'modeBarButtonsToRemove': [
                    'zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 
                    'zoomOut2d', 'autoScale2d', 'resetScale2d', 'hoverClosestCartesian', 
                    'hoverCompareCartesian', 'toggleSpikelines'
                ],
                'displayModeBar': True
            }

            # --- CHART 1: BRAND (POSISI ATAS) ---
            st.subheader("Total Activities by Brand")
            max_b = chart_brand['count'].max()

            fig_b = px.bar(chart_brand, x='Brand', y='count', color='Brand', color_discrete_map=color_map, text='count')

            fig_b.update_layout(
                height=500, # Tinggi disesuaikan agar tidak terlalu memakan ruang saat vertikal
                showlegend=False, 
                yaxis_title="Total Activities",
                yaxis=dict(range=[0, max_b * 1.2], tickfont=dict(size=14)), 
                xaxis=dict(tickfont=dict(size=18)), 
                margin=dict(t=50, b=50) 
            )

            fig_b.update_traces(
                textposition='outside', 
                textfont=dict(size=22, family='Arial Black'), 
                cliponaxis=False
            )

            st.plotly_chart(fig_b, use_container_width=True, config=plotly_config)

            # Pemisah visual antara chart atas dan bawah
            st.divider()

            # --- CHART 2: MODEL (POSISI BAWAH) ---
            st.subheader("Top 10 Models")
            # Untuk chart horizontal, kita gunakan max_x untuk padding kanan
            max_m = chart_model.head(10)['count'].max()

            fig_m = px.bar(chart_model.head(10), x='count', y='Model', orientation='h', text='count', color_discrete_sequence=['#2ECC71'])

            fig_m.update_layout(
                height=600, 
                yaxis=dict(showticklabels=True, tickfont=dict(size=16), categoryorder='total ascending'), 
                xaxis=dict(range=[0, max_m * 1.3], tickfont=dict(size=14)), 
                xaxis_title="Total Activities",
                margin=dict(t=50, b=50)
            )

            fig_m.update_traces(
                textposition='outside', 
                textfont=dict(size=20, family='Arial Black'),
                cliponaxis=False
            )

            st.plotly_chart(fig_m, use_container_width=True, config=plotly_config)

        else:
            st.warning(f"Tidak ada data untuk kategori {selected_activity}")

    # --- TABEL DETAIL & EXPORT ---
    st.divider()
    st.subheader("📄 Activity Logs")
    
    # Menyiapkan DataFrame untuk tampilan dan export
    df_display = df_filtered[["Timestamp", "Username", "Brand", "Model", "RecordType"]].iloc[::-1]
    
    st.dataframe(df_display, use_container_width=True)
    
    # --- TOMBOL EXPORT BERDAMPINGAN ---
    col_ex1, col_ex2, _ = st.columns([1, 1, 3])
    
    with col_ex1:
        # Tombol Export CSV
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export to CSV",
            data=csv,
            file_name='product_activity_logs.csv',
            mime='text/csv',
        )

    with col_ex2:
        # Tombol Export Excel
        excel_data = convert_df_to_excel(df_display)
        st.download_button(
            label="📊 Export to Excel",
            data=excel_data,
            file_name='product_activity_logs.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

# --- HISTORY LOGIC ---
def log_login(username, role, status="Success"):
    try:
        # 1. Ambil data lama dari sheet LoginHistory
        history_df = load_gsheet_data("LoginHistory")
        
        # 2. Ambil waktu sekarang (WIB)
        wib_now = datetime.now() + timedelta(hours=7) 
        now_str = wib_now.strftime("%Y-%m-%d %H:%M:%S")
        
        # 3. Buat baris baru dalam bentuk DataFrame
        # Sesuaikan urutan kolom: Username, Role, Timestamp, Status
        new_entry = pd.DataFrame([[
            username, 
            role, 
            now_str, 
            status
        ]], columns=["Username", "Role", "Timestamp", "Status"])
        
        # 4. Gabungkan data lama dan baru
        if not history_df.empty:
            updated_df = pd.concat([history_df, new_entry], ignore_index=True)
        else:
            updated_df = new_entry
            
        # 5. Update ke Google Sheets
        conn.update(worksheet="LoginHistory", data=updated_df)
        
    except Exception as e:
        st.error(f"Gagal mencatat log login ke GSheet: {e}")

def show_history_page():
    st.title("📜 Login History")
    
    # Ambil data dari GSheet
    history_df = load_gsheet_data("LoginHistory")
    
    if not history_df.empty:
        # Tampilkan Tabel (Data terbaru di atas)
        df_display = history_df.iloc[::-1]
        st.dataframe(df_display, use_container_width=True)
        
        # Baris Tombol Aksi
        col_ex1, col_ex2, col_clear = st.columns([1, 1, 2])
        
        with col_ex1:
            csv_data = df_display.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export CSV", csv_data, "login_logs.csv", "text/csv")
            
        with col_ex2:
            excel_data = convert_df_to_excel(df_display)
            st.download_button("📊 Export Excel", excel_data, "login_logs.xlsx")

        # LOGIKA TOMBOL CLEAR
        with col_clear:
            if st.session_state.role == "Admin":
                # Gunakan popover atau warning agar tidak tidak sengaja terhapus
                if st.button("🗑️ Clear All History", type="secondary", help="Hapus semua data di GSheet"):
                    status = clear_gsheet_content("LoginHistory")
                    if status:
                        st.success("History berhasil dibersihkan!")
                        st.rerun()
                    else:
                        st.info("History sudah kosong (hanya tersisa header).")
    else:
        st.info("No login history available in Google Sheets.")

def login_screen():
    st.markdown("<h2 style='text-align: center;'>Product Library</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            # Tambahkan .strip() untuk membersihkan spasi tak sengaja
            username = st.text_input("Username / Email").strip()
            password = st.text_input("Password", type="password").strip()
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
                    # Perbandingan dilakukan dengan memastikan kedua belah pihak adalah string
                    match = users_df[(users_df['Username'] == username) & (users_df['Password'] == password)]
                    
                    if not match.empty:
                        user_status = match.iloc[0]['ApprovalStatus']
                        
                        # --- PENGECEKAN STATUS APPROVAL ---
                        if user_status == "Pending":
                            st.warning("⚠️ Akun Anda sedang menunggu persetujuan Admin. Silakan hubungi Admin untuk aktivasi.")
                        elif user_status == "Active":
                            st.session_state.logged_in = True
                            st.session_state.username = username
                            # Pastikan kolom 'Role' ada di sheet Anda, jika tidak ada bisa default ke 'User'
                            st.session_state.role = match.iloc[0]['Role'] if 'Role' in match.columns else "User"
                            log_login(username, st.session_state.role)
                            st.rerun()
                        else:
                            st.error("Status akun tidak dikenal. Silakan hubungi IT.")
                    else:
                        st.error("Invalid Username or Password")
        
        st.write("---")
        if st.button("Sign Up"):
            signup_dialog()

def load_registered_users():
    try:
        # Membaca sheet UserAccount
        df = conn.read(worksheet="UserAccount", ttl=0)
        
        # --- PERBAIKAN UNTUK LOGIN (Muhammad Sina & Password Angka) ---
        # Memastikan Username dan Password selalu terbaca sebagai teks/string
        df['Username'] = df['Username'].astype(str).str.strip()
        df['Password'] = df['Password'].astype(str).str.strip()
        
        # Inisialisasi kolom jika belum ada
        if 'ApprovalStatus' not in df.columns:
            df['ApprovalStatus'] = 'Active'
        else:
            df['ApprovalStatus'] = df['ApprovalStatus'].fillna('Active')
            
        if 'Role' not in df.columns:
            df['Role'] = 'User'
        else:
            df['Role'] = df['Role'].fillna('User')
            
        return df
    except Exception as e:
        st.error(f"Gagal memuat data user: {e}")
        return pd.DataFrame(columns=["Username", "Password", "Role", "Verified", "ApprovalStatus"])

def update_user_gsheet(updated_df):
    """Fungsi pembantu untuk menyimpan perubahan ke Google Sheets"""
    try:
        conn.update(worksheet="UserAccount", data=updated_df)
        return True
    except Exception as e:
        st.error(f"Gagal memperbarui database: {e}")
        return False

def show_user_management_page():
    st.title("👥 User Management & Role Control")
    st.write("Kelola hak akses dan persetujuan akun karyawan di sini.")
    
    # Load data terbaru
    users_df = load_registered_users()
    
    if not users_df.empty:
        # Header Tabel
        h1, h2, h3, h4 = st.columns([2, 1.5, 1.5, 1])
        h1.write("**Email**")
        h2.write("**Role Access**")
        h3.write("**Account Status**")
        h4.write("**Action**")
        st.divider()

        # Loop setiap user
        for index, row in users_df.iterrows():
            # Jika user ini adalah admin yang sedang login, kita beri proteksi agar tidak mengubah diri sendiri
            is_self = (row['Username'] == st.session_state.username)
            
            col1, col2, col3, col4 = st.columns([2, 1.5, 1.5, 1])
            
            with col1:
                st.write(row['Username'])
                if row['Verified']:
                    st.caption("✅ Verified")
                else:
                    st.caption("❌ Unverified")

            with col2:
                # Fitur Change Role
                new_role = st.selectbox(
                    "Role",
                    options=["User", "Admin"],
                    index=0 if row['Role'] == "User" else 1,
                    key=f"role_{row['Username']}",
                    label_visibility="collapsed",
                    disabled=is_self
                )

            with col3:
                # Fitur Approval (Change Status)
                new_status = st.selectbox(
                    "Status",
                    options=["Pending", "Active", "Inactive"],
                    index=["Pending", "Active", "Inactive"].index(row['ApprovalStatus']),
                    key=f"stat_{row['Username']}",
                    label_visibility="collapsed",
                    disabled=is_self
                )

            with col4:
                # Tombol simpan untuk baris ini
                if not is_self:
                    if st.button("Save", key=f"save_{row['Username']}"):
                        # Update dataframe
                        users_df.at[index, 'Role'] = new_role
                        users_df.at[index, 'ApprovalStatus'] = new_status
                        
                        if update_user_gsheet(users_df):
                            st.success(f"Update {row['Username']} Berhasil!")
                            st.rerun()
                    
                    if st.button("Delete", key=f"del_{row['Username']}", type="secondary"):
                        # Logika delete yang sudah Anda miliki sebelumnya
                        # delete_user_gsheet(row['Username']) 
                        # st.rerun()
                        pass
                else:
                    st.write("*(Me)*")

            st.write("---")
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

def handle_share_logging(username, brand, model, record_type):
    """Callback khusus untuk memastikan logging selesai sebelum aksi browser."""
    try:
        log_activity_to_gsheet(username, brand, model, record_type)
        # Session state ini hanya untuk membantu UI jika diperlukan
        st.session_state[f"logged_{record_type}"] = True
    except Exception as e:
        print(f"Error logging {record_type}: {e}")


# --- PRODUCT DETAIL POPUP ---
@st.dialog("Product Details", width="large")
def show_detail(row, full_df):
    brand = row['Brand'] if not pd.isna(row['Brand']) else "-"
    model = row['Model Variations'] if not pd.isna(row['Model Variations']) else "-"
    aisle_w = row.get('Aisle Width (cm)', '-')
    aisle_cat = clean_list_string(row.get('Aisle Category'))
    env_val = clean_list_string(row.get('Environment'))
    slope_val = row.get('Max_Slope', '-') 
    max_area = row.get('Target Cleaning Area_(m²/5h)', '-')
    floor_type = clean_list_string(row.get('Floor_Type_List'))
    obstacles = clean_list_string(row.get('Obstacle_List'))
    waste_type = clean_list_string(row.get('Waste_Type_List'))
    charging_time = clean_list_string(row.get('Charging_Time'))
    clean_waste_water_tank = clean_list_string(row.get('Clean_Waste_Water_Tank'))
    sensing_list = clean_list_string(row.get('Sensing_System_List'))
    feature_list = clean_list_string(row.get('Feature_Detail_List')) 
    solution_tank = clean_list_string(row.get('Solution_Tank_Capacity'))
    recovery_tank = clean_list_string(row.get('Recovery_Tank_Capacity'))
    waste_tank = clean_list_string(row.get('Waste_Tank_Capacity'))

    # --- LOGIKA PEMBERSIHAN TOTAL ---
    raw_val = row.get('Video_Link')
    
    # 1. Pastikan bukan NaN dan ubah ke string
    video_url = str(raw_val).strip() if pd.notna(raw_val) else ""
    
    # 2. Cek apakah isinya benar-benar link yang valid
    if video_url in ["-", "nan", "NaN", "None", ""]:
        has_video = False
    else:
        # 3. Pastikan diawali dengan protokol http agar tidak error
        if not video_url.startswith(('http://', 'https://')):
            # Jika user lupa input https://, kita tambahkan secara otomatis
            video_url = f"https://{video_url}"
        
        # Anggap valid jika setidaknya ada titik (.) sebagai ciri domain/URL
        has_video = "." in video_url

    # --- DEBUGGING (PENTING) ---
    # Jika masih tidak muncul, aktifkan baris di bawah ini untuk melihat apa yang dibaca Python
    # st.write(f"DEBUG - Nilai Asli: '{raw_val}' | Hasil Bersih: '{video_url}' | Status: {has_video}")

    # Judul dan Tombol Compare
    col_title, col_comp = st.columns([3, 1])
    with col_title:
        st.header(f"{brand} - {model}")
    with col_comp:
        if st.button("🔄 Compare Product", type="primary"):
            st.session_state.compare_base = row
            st.session_state.show_compare = True
            st.session_state.show_dialog = False 
            st.rerun()

    st.image(get_image_path(row.get('General Specifications')), width=250) 
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Specifications")
        st.write(f"**Product Type:** {row.get('Product_type', '-')}")
        st.write(f"**Environment:** {env_val}")
        st.write(f"**Floor Type:** {floor_type}") 
        st.write(f"**Max Target Cleaning Area:** {max_area} m²/5h")
        st.write(f"**Max. Slope:** {slope_val}")
        st.write(f"**Charging Time :** {charging_time}")
        st.write(f"**Solution Tank Capacity :** {solution_tank}")
        st.write(f"**Recovery Tank Capacity :** {recovery_tank}")
        st.write(f"**Waste Tank Capacity :** {waste_tank}")
        st.write(f"**Clean/Waste Water Tank :** {clean_waste_water_tank}")
        
    with col2:
        st.subheader("Weight & Dimensions")
        st.write(f"**Net Weight:** {row.get('Net Weight (kg)', '-')} Kg")
        st.write(f"**Dimensions (L/W/H):** {row.get('Measures_L','-')}/{row.get('Measures_W','-')}/{row.get('Measures_H','-')} mm")
        st.write(f"**Aisle Width:** {aisle_w} cm")
        st.write(f"**Aisle Category:** {aisle_cat}")
        st.subheader("Obstacle & Waste Type")
        st.write(f"**Obstacle:** {obstacles}")
        st.write(f"**Waste Type:** {waste_type}")
        st.subheader("Sensing System & Feature")
        st.write(f"**Sensing System :** {sensing_list}")
        st.write(f"**Feature :** {feature_list}")
        
        # Area Video
        st.subheader("Video")
        if has_video:
            st.link_button("🎥 Watch Video Demo", video_url, use_container_width=True)
        else:
            st.info("No video available for this model")

    st.markdown("---")
    
    spec_name = str(row.get('General Specifications', '')).strip()
    found_path = os.path.join("static", "brochures", f"{spec_name}.pdf")
    spec_name_encoded = urllib.parse.quote(spec_name)
    
    if os.path.exists(found_path):
        col_dl, col_wa, col_email = st.columns(3) 
        
        # --- LOGIKA DOWNLOAD ---
        with col_dl:
            with open(found_path, "rb") as pdf_file:
                if st.download_button(
                    label="📄 Download Brochure", 
                    data=pdf_file, 
                    file_name=f"{spec_name}.pdf", 
                    mime="application/pdf",
                    key=f"dl_{spec_name}"
                ):
                    # Menggunakan fungsi universal yang baru
                    log_activity_to_gsheet(st.session_state.username, brand, model, "Download")
                    st.success("Download tercatat!")

        # Persiapan Link Share
        public_url = f"{GITHUB_RAW_BASE}static/brochures/{spec_name_encoded}.pdf" 
        subject_mail = f"Product Specs: {brand} - {model}"
        share_msg = f"Check out this product: {brand} - {model}\nBrochure: {public_url}"
        
        with col_wa:
            wa_url = f"https://wa.me/?text={urllib.parse.quote(share_msg)}"
            # Gunakan on_click untuk menjamin eksekusi log
            if st.button("📲 WhatsApp", key=f"wa_btn_{row.name}", use_container_width=True,
                         on_click=handle_share_logging, 
                         args=(st.session_state.username, brand, model, "WhatsApp")):
                
                # Membuka link hanya SETELAH callback logging dijalankan
                js_wa = f'window.open("{wa_url}", "_blank").focus();'
                st.components.v1.html(f'<script>{js_wa}</script>', height=0)
                st.toast("WhatsApp activity recorded!")

        with col_email:
            email_url = f"mailto:?subject={urllib.parse.quote(subject_mail)}&body={urllib.parse.quote(share_msg)}"
            if st.button("📧 Email", key=f"em_btn_{row.name}", use_container_width=True,
                         on_click=handle_share_logging, 
                         args=(st.session_state.username, brand, model, "Email")):
                
                js_em = f'window.location.href = "{email_url}";'
                st.components.v1.html(f'<script>{js_em}</script>', height=0)
                st.toast("Email activity recorded!")

    else:
        st.info("Digital brochure is not yet available.")

    st.markdown("---")
    if st.button("Tutup Detail"):
        st.session_state.show_dialog = False
        st.rerun()


def filter_analytics_page():
    st.title("📊 Filter Analytics")

    try:
        # Gunakan fungsi load_gsheet_data yang sudah ada
        data = load_gsheet_data("FilterLogs")

        # --- 1. LOGIKA PRIVASI DATA (USER-SPECIFIC) ---
        if st.session_state.role != "Admin":
            # User hanya melihat data miliknya sendiri (Case Insensitive)
            data = data[data['Username'].str.lower() == st.session_state.username.lower()]
        
        if data.empty:
            st.info("Belum ada data aktivitas filter untuk akun Anda.")
            return

        plotly_config = {
            'displaylogo': False,
            'modeBarButtonsToRemove': [
                'zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 
                'zoomOut2d', 'autoScale2d', 'resetScale2d', 'hoverClosestCartesian', 
                'hoverCompareCartesian', 'toggleSpikelines'
            ],
            'displayModeBar': True
        }

        # --- DATA PREPARATION UNTUK NUMERIC FILTERS (AREA & SLOPE) ---
        # Karena Area_Filter & Slope_Filter ada di tiap baris log, kita ambil 1 data per sesi pencarian
        unique_searches = data.drop_duplicates(subset=['Timestamp', 'Username']).copy()

        # --- Visualisasi 1: Target Cleaning Area Clustering (Dari Area_Filter) ---
        st.divider()
        st.subheader("Target Cleaning Area Demand (m²/5h)")
        
        # Konversi ke numerik dan ambil yang di atas 0 (asumsi 0 = tidak diisi/All)
        unique_searches['Area_Num'] = pd.to_numeric(unique_searches['Area_Filter'], errors='coerce').fillna(0)
        area_data = unique_searches[unique_searches['Area_Num'] > 0].copy()

        if not area_data.empty:
            bins_area = [-float('inf'), 22500, 50000, 100000, float('inf')]
            labels_area = ['0-22.500', '22.501-50.000', '50.001-100.000', '100.001-Seterusnya']
            
            area_data['Cluster'] = pd.cut(area_data['Area_Num'], bins=bins_area, labels=labels_area)
            area_counts = area_data['Cluster'].value_counts().reindex(labels_area, fill_value=0).reset_index()
            area_counts.columns = ['Range', 'Count']
            max_area = area_counts['Count'].max()

            fig_area = px.bar(area_counts, x='Range', y='Count', text='Count', color_discrete_sequence=['#C0392B'])
            fig_area.update_traces(textposition='outside', textfont=dict(size=22, family='Arial Black'), cliponaxis=False)
            fig_area.update_layout(
                xaxis_title="", yaxis_title="Jumlah Pencarian",
                yaxis=dict(range=[0, max_area * 1.3 if max_area > 0 else 10], tickfont=dict(size=14)),
                xaxis=dict(tickfont=dict(size=16)), height=500, margin=dict(l=20, r=20, t=80, b=40)
            )
            st.plotly_chart(fig_area, use_container_width=True, config=plotly_config)
        else:
            st.info("Belum ada data numerik untuk Target Cleaning Area.")

        # --- Visualisasi 2: Max Slope Clustering (Dari Slope_Filter) ---
        st.divider()
        st.subheader("Max Slope Preference (%)")
        
        unique_searches['Slope_Num'] = pd.to_numeric(unique_searches['Slope_Filter'], errors='coerce').fillna(0)
        slope_data = unique_searches[unique_searches['Slope_Num'] > 0].copy()

        if not slope_data.empty:
            bins_slope = [-float('inf'), 5, 10, float('inf')]
            labels_slope = ['0-5', '6-10', '11 - Seterusnya']
            
            slope_data['Cluster'] = pd.cut(slope_data['Slope_Num'], bins=bins_slope, labels=labels_slope)
            slope_counts = slope_data['Cluster'].value_counts().reindex(labels_slope, fill_value=0).reset_index()
            slope_counts.columns = ['Range', 'Count']
            max_slope = slope_counts['Count'].max()

            fig_slope = px.bar(slope_counts, x='Range', y='Count', text='Count', color_discrete_sequence=['#2980B9'])
            fig_slope.update_traces(textposition='outside', textfont=dict(size=22, family='Arial Black'), cliponaxis=False)
            fig_slope.update_layout(
                xaxis_title="", yaxis_title="Jumlah Pencarian",
                yaxis=dict(range=[0, max_slope * 1.3 if max_slope > 0 else 10], tickfont=dict(size=14)),
                xaxis=dict(tickfont=dict(size=18)), height=500, margin=dict(l=20, r=20, t=80, b=40)
            )
            st.plotly_chart(fig_slope, use_container_width=True, config=plotly_config)
        else:
            st.info("Belum ada data numerik untuk Max Slope.")

        # --- Visualisasi 3: Environment Preference ---
        st.divider()
        st.subheader("Environment Preference")
        env_df = data[data['Category'] == 'Environment']
        if not env_df.empty:
            env_counts = env_df['Value'].value_counts().reset_index()
            env_counts.columns = ['Environment', 'Count']
            max_val = env_counts['Count'].max()
            fig_env = px.bar(env_counts, x='Environment', y='Count', text='Count', color_discrete_sequence=['#E67E22'])
            fig_env.update_traces(textposition='outside', textfont=dict(size=22, family='Arial Black'), cliponaxis=False)
            fig_env.update_layout(
                xaxis_title="", yaxis_title="Jumlah Pencarian",
                yaxis=dict(range=[0, max_val * 1.3], tickfont=dict(size=14)),
                xaxis=dict(showticklabels=True, tickfont=dict(size=18)),
                height=500, margin=dict(l=20, r=20, t=80, b=40)
            )
            st.plotly_chart(fig_env, use_container_width=True, config=plotly_config)

        # --- Visualisasi 4: Most Searched Floor Types ---
        st.subheader("Most Searched Floor Types")
        floor_data = data[data['Category'] == 'Floor Type']
        if not floor_data.empty:
            floor_counts = floor_data['Value'].value_counts().reset_index()
            floor_counts.columns = ['Floor Type', 'Count']
            max_val = floor_counts['Count'].max()
            fig_floor = px.bar(floor_counts, x='Floor Type', y='Count', text='Count', color_discrete_sequence=['#004d1a'])
            fig_floor.update_traces(textposition='outside', textfont=dict(size=22, family='Arial Black'), cliponaxis=False)
            fig_floor.update_layout(
                xaxis_title="", yaxis_title="Jumlah Pencarian",
                yaxis=dict(range=[0, max_val * 1.3], tickfont=dict(size=14)),
                xaxis=dict(showticklabels=True, tickfont=dict(size=18)),
                height=550, margin=dict(l=20, r=20, t=80, b=40)
            )
            st.plotly_chart(fig_floor, use_container_width=True, config=plotly_config)

        # --- Visualisasi 5: Product Type Preference ---
        st.divider()
        st.subheader("Product Type Preference")
        pt_df = data[data['Category'] == 'Product Type']
        if not pt_df.empty:
            pt_counts = pt_df['Value'].value_counts().reset_index()
            pt_counts.columns = ['Product Type', 'Count']
            max_val = pt_counts['Count'].max()
            fig_pt = px.bar(pt_counts, x='Product Type', y='Count', text='Count', color_discrete_sequence=['#16A085'])
            fig_pt.update_traces(textposition='outside', textfont=dict(size=22, family='Arial Black'), cliponaxis=False)
            fig_pt.update_layout(
                xaxis_title="", yaxis_title="Jumlah Pencarian",
                yaxis=dict(range=[0, max_val * 1.3], tickfont=dict(size=14)),
                xaxis=dict(showticklabels=True, tickfont=dict(size=18)),
                height=500, margin=dict(l=20, r=20, t=80, b=40)
            )
            st.plotly_chart(fig_pt, use_container_width=True, config=plotly_config)

        # --- Visualisasi 6: Obstacle Preference ---
        st.divider() 
        st.subheader("Obstacle Preference")
        obs_df = data[data['Category'] == 'Obstacle']
        if not obs_df.empty:
            obs_counts = obs_df['Value'].value_counts().reset_index()
            obs_counts.columns = ['Obstacle', 'Count']
            max_val = obs_counts['Count'].max()
            fig_obs = px.bar(obs_counts, x='Obstacle', y='Count', text='Count', color_discrete_sequence=['#34495E'])
            fig_obs.update_traces(textposition='outside', textfont=dict(size=22, family='Arial Black'), cliponaxis=False)
            fig_obs.update_layout(
                xaxis_title="", yaxis_title="Jumlah Pencarian",
                yaxis=dict(range=[0, max_val * 1.3], tickfont=dict(size=14)),
                xaxis=dict(showticklabels=True, tickfont=dict(size=18)),
                height=500, margin=dict(l=20, r=20, t=80, b=40)
            )
            st.plotly_chart(fig_obs, use_container_width=True, config=plotly_config)

        # --- Visualisasi 7: Waste Type Preference ---
        st.divider()
        st.subheader("Waste Type Preference")
        waste_df = data[data['Category'] == 'Waste Type']
        if not waste_df.empty:
            waste_counts = waste_df['Value'].value_counts().reset_index()
            waste_counts.columns = ['Waste Type', 'Count']
            max_val = waste_counts['Count'].max()
            fig_waste = px.bar(waste_counts, x='Waste Type', y='Count', text='Count', color_discrete_sequence=['#8E44AD'])
            fig_waste.update_traces(textposition='outside', textfont=dict(size=22, family='Arial Black'), cliponaxis=False)
            fig_waste.update_layout(
                xaxis_title="", yaxis_title="Jumlah Pencarian",
                yaxis=dict(range=[0, max_val * 1.3], tickfont=dict(size=14)),
                xaxis=dict(showticklabels=True, tickfont=dict(size=18)),
                height=500, margin=dict(l=20, r=20, t=80, b=40)
            )
            st.plotly_chart(fig_waste, use_container_width=True, config=plotly_config)

        # --- Visualisasi 8: Aisle Category Demand ---
        st.divider()
        st.subheader("Aisle Category Demand")
        aisle_df = data[data['Category'] == 'Aisle Category']
        if not aisle_df.empty:
            aisle_counts = aisle_df['Value'].value_counts().reset_index()
            aisle_counts.columns = ['Aisle', 'Count']
            max_val = aisle_counts['Count'].max()
            fig_aisle = px.bar(aisle_counts, x='Aisle', y='Count', text='Count', color_discrete_sequence=['#0078D4'])
            fig_aisle.update_traces(textposition='outside', textfont=dict(size=22, family='Arial Black'), cliponaxis=False)
            fig_aisle.update_layout(
                xaxis_title="", yaxis_title="Jumlah Pencarian",
                yaxis=dict(range=[0, max_val * 1.3], tickfont=dict(size=14)),
                xaxis=dict(showticklabels=True, tickfont=dict(size=18)),
                height=450, margin=dict(l=20, r=20, t=80, b=40)
            )
            st.plotly_chart(fig_aisle, use_container_width=True, config=plotly_config)
        
        # --- Tabel Data Mentah dengan Tombol Export ---
        st.divider()
        st.subheader("📋 Detail Data Logs")
        df_display = data.iloc[::-1]
        with st.expander("View & Export Data Details"):
            st.dataframe(df_display, use_container_width=True)
            col_ex1, col_ex2, _ = st.columns([1, 1, 3])
            with col_ex1:
                csv_data = df_display.to_csv(index=False).encode('utf-8')
                st.download_button(label="📥 Export to CSV", data=csv_data, file_name='filter_logs.csv', mime='text/csv')
            with col_ex2:
                excel_data = convert_df_to_excel(df_display)
                st.download_button(label="📊 Export to Excel", data=excel_data, file_name='filter_logs.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                
    except Exception as e:
        st.error(f"Failed to load Dashboard: {e}")
       
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
    
    pages = ["Product Library", "Product Analytics" , "Filter Analytics"]
    if st.session_state.role == "Admin":
        pages.extend(["Login History", "Admin Approval", "User Management"])
    
    selected_page = st.sidebar.selectbox("Navigate to", pages)

    if selected_page == "Product Analytics":
        show_product_analytics_page()
    elif selected_page == "Filter Analytics":
        filter_analytics_page()
    elif selected_page == "Login History":
        show_history_page()
    elif selected_page == "Admin Approval":
        show_admin_approval_page()
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
            res['Target Cleaning Area_(m²/5h)'] = pd.to_numeric(res['Target Cleaning Area_(m²/5h)'], errors='coerce').fillna(0)
            res = res[res['Target Cleaning Area_(m²/5h)'] >= filter_area]

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

        def handle_view_details(row, filters):
            # 1. Jalankan logging filter (Pecah baris otomatis)
            log_filter_to_gsheet(st.session_state.username, filters)
    
            # 2. Jalankan fungsi buka detail yang sudah Anda miliki
            click_detail(row)
        
        
        if len(res) > 0:
            cols = st.columns(3)
            for idx, (index, row) in enumerate(res.iterrows()):
                with cols[idx % 3]:
                    with st.container(border=True):
                        st.image(get_image_path(row['General Specifications']))
                        st.markdown(f"**{row['Brand']}**")
                        st.caption(row.get('Model Variations', '-'))
                
                        # --- KUMPULKAN FILTER YANG SEDANG AKTIF ---
                        # Sesuaikan nama variabel di kanan (ptype_filter, dll) 
                        # dengan nama variabel widget multiselect/slider Anda
                        current_filters = {
                            'brand': pilihan_produk,      # Sesuai baris 716
                            'product_type': filter_type,  # Sesuai baris 719
                            'environment': filter_env,    # Sesuai baris 722
                            'floor_type': filter_floor,   # Sesuai baris 725
                            'area': filter_area,          # Sesuai baris 728
                            'slope': filter_slope,        # Sesuai baris 731
                            'aisle_cat': filter_aisle_cat, # Sesuai baris 734
                            'obstacle': selected_obstacles, # Sesuai baris 738
                            'waste_type': selected_wastes   # Sesuai baris 747
                        }
                
                        # --- GANTI ON_CLICK KE WRAPPER ---
                        st.button(
                            "View Details", 
                            key=f"btn_{index}", 
                            on_click=handle_view_details, 
                            args=(row, current_filters) # Kirim row DAN data filter
                        )
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

