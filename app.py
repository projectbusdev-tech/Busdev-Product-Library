import streamlit as st
import pandas as pd
import os
import re
import urllib.parse

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

# --- HELPER FUNCTIONS ---
def get_actual_col(df, target_name):
    """Mencari nama kolom asli di DataFrame meskipun ada perbedaan spasi/underscore."""
    norm_target = re.sub(r'[\s_]+', '', target_name.lower())
    for col in df.columns:
        if re.sub(r'[\s_]+', '', col.lower()) == norm_target:
            return col
    return None

def clean_list_string(val):
    """Membersihkan format list string ['A', 'B'] menjadi A, B."""
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
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("Dataset_Normalized_Complete.csv", sep=";", encoding='latin1')
    except UnicodeDecodeError:
        df = pd.read_csv("Dataset_Normalized_Complete.csv", sep=";")
    df.columns = df.columns.str.strip() 
    return df

# --- IMAGE CHECKER FUNCTION ---
def get_image_path(filename):
    if pd.isna(filename):
        return "https://via.placeholder.com/300x200?text=No+Image"
    base_path = os.path.join("static", "images")
    clean_name = str(filename).strip()
    if os.path.exists(os.path.join(base_path, f"{clean_name}.jpg")):
        return os.path.join(base_path, f"{clean_name}.jpg")
    if os.path.exists(os.path.join(base_path, f"{clean_name}.png")):
        return os.path.join(base_path, f"{clean_name}.png")
    return "https://via.placeholder.com/300x200?text=No+Image"

# --- PRODUCT COMPARISON POPUP ---
@st.dialog("Compare Product", width="large")
def show_comparison(base_row, full_df):
    st.write(f"Comparing: **{base_row['Brand']} - {base_row['Model Variations']}**")
    
    # Pilih produk lain untuk dibandingkan (max 2)
    other_products = full_df[full_df['General Specifications'] != base_row['General Specifications']].copy()
    other_products['Display_Name'] = other_products['Brand'] + " - " + other_products['Model Variations'].fillna("")
    
    selected_names = st.multiselect(
        "Select up to 2 products to compare:", 
        options=other_products['Display_Name'].unique(),
        max_selections=2
    )
    
    # Kolom yang akan dibanding
    comparison_cols = ['Floor_Type_List', 'Obstacle_List', 'Waste_Type_List']
    labels = ["Floor Type", "Obstacle", "Waste Type"]
    
    # Menyiapkan Data Tabel
    data = {"Parameter": labels}
    
    # Data Produk Utama
    data[f"Current: {base_row['Brand']}"] = [
        clean_list_string(base_row.get(get_actual_col(full_df, col))) for col in comparison_cols
    ]
    
    # Data Produk Pilihan
    for i, name in enumerate(selected_names):
        comp_row = other_products[other_products['Display_Name'] == name].iloc[0]
        data[f"Product {i+2}: {name}"] = [
            clean_list_string(comp_row.get(get_actual_col(full_df, col))) for col in comparison_cols
        ]
    
    st.table(pd.DataFrame(data).set_index("Parameter"))
    
    if st.button("Close Comparison"):
        st.session_state.show_compare = False
        st.rerun()

# --- PRODUCT DETAIL POPUP ---
@st.dialog("Product Details", width="large")
def show_detail(row, full_df):
    brand = row['Brand'] if not pd.isna(row['Brand']) else "-"
    model = row['Model Variations'] if not pd.isna(row['Model Variations']) else "-"
    aisle_w = row.get('Aisle Width (mm)', '-')
    slope_val = row.get('Max_Slope', '-')

    col_title, col_comp = st.columns([3, 1])
    with col_title:
        st.header(f"{brand} - {model}")
    with col_comp:
        # BUTTON COMPARE PRODUCT
        if st.button("🔄 Compare Product", type="primary"):
            st.session_state.compare_base = row
            st.session_state.show_compare = True
            st.rerun()

    img_path = get_image_path(row.get('General Specifications'))
    st.image(img_path, width=250) 
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("General Specifications")
        st.write(f"**Product Type:** {row.get('Product_type', '-')}")
        st.write(f"**Aisle Width:** :orange[**{aisle_w} mm**]")
        st.write(f"**Max. Slope Capacity:** :red[**{slope_val}°**]")
        st.write(f"**Power Source:** {row.get('Power Source', '-')}")
        
    with col2:
        st.subheader("Dimensions & Weight")
        st.write(f"**Size Category:** {row.get('Ukuran Produk', '-')}")
        st.write(f"**Net Weight:** {row.get('Net Weight (kg)', '-')} Kg")
        st.write(f"**Dimensions (L/W/H):** {row.get('Measures_L','-')}/{row.get('Measures_W','-')}/{row.get('Measures_H','-')} mm")

    st.markdown("---")
    
    spec_name = str(row.get('General Specifications', '')).strip()
    found_path = os.path.join("static", "brochures", f"{spec_name}.pdf")
    spec_name_encoded = urllib.parse.quote(spec_name)
    
    if os.path.exists(found_path):
        col_dl, col_wa, col_email = st.columns(3) 
        with col_dl:
            with open(found_path, "rb") as pdf_file:
                st.download_button(label="📄 Download Brochure", data=pdf_file, file_name=f"{spec_name}.pdf", mime="application/pdf")

        public_url = f"{GITHUB_RAW_BASE}static/brochures/{spec_name_encoded}.pdf" 
        subject_mail = f"Product Specs: {brand} - {model}"
        share_msg = f"Check out this product: {brand} - {model}\nBrochure: {public_url}"
        
        with col_wa:
            st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(share_msg)}" target="_blank" class="custom-button wa-button">📲 WhatsApp</a>', unsafe_allow_html=True)
        with col_email:
            st.markdown(f'<a href="mailto:?subject={urllib.parse.quote(subject_mail)}&body={urllib.parse.quote(share_msg)}" target="_blank" class="custom-button email-button">📧 Email</a>', unsafe_allow_html=True)
    else:
        st.info("Digital brochure is not yet available.")
    
    st.markdown("---")
    st.caption("Use the 'X' icon at the top right to close details.")

# --- MAIN APP ---
def main():
    if 'form_key' not in st.session_state: st.session_state.form_key = 0
    if 'show_dialog' not in st.session_state: st.session_state.show_dialog = False
    if 'show_compare' not in st.session_state: st.session_state.show_compare = False
    if 'filter_params' not in st.session_state: st.session_state.filter_params = {}

    df = load_data()

    def get_uniques(col_name):
        actual = get_actual_col(df, col_name)
        if actual:
            temp = df[actual].dropna().astype(str).str.replace(r"[\[\]']", '', regex=True)
            all_items = temp.str.split(',').explode().str.strip()
            return sorted([i for i in all_items.unique() if i and i.lower() != 'nan'])
        return []

    # --- SIDEBAR FILTERS ---
    st.sidebar.header("🎛️ Search Filters")
    if st.sidebar.button("🔄 Reset Filters"):
        handle_reset()
        st.session_state.form_key += 1
        st.rerun()

    pilihan_produk = st.sidebar.radio(
        "Brand / Category", 
        ["All", "Manual (Fiorentini)", "Autonomous (Gausium)"],
        index=["All", "Manual (Fiorentini)", "Autonomous (Gausium)"].index(st.session_state.filter_params.get('pilihan_produk', "All")),
        key=f"radio_{st.session_state.form_key}"
    )

    filter_type = st.sidebar.multiselect(
        "Product Type", 
        sorted(df['Product_type'].dropna().unique().tolist()) if 'Product_type' in df.columns else [], 
        default=st.session_state.filter_params.get('filter_type', []),
        key=f"type_{st.session_state.form_key}"
    )
    
    filter_loc = st.sidebar.multiselect(
        "Application Location", 
        get_uniques('Processed_Locations'), 
        default=st.session_state.filter_params.get('filter_loc', []),
        key=f"loc_{st.session_state.form_key}"
    )

    filter_aisle_cat = st.sidebar.multiselect(
        "Aisle Category", 
        get_uniques('Aisle Category'),
        default=st.session_state.filter_params.get('filter_aisle_cat', []),
        key=f"aisle_cat_{st.session_state.form_key}"
    )

    filter_slope = st.sidebar.number_input(
        "Min. Max.Slope Capacity (°)", 
        min_value=0, step=1, 
        value=st.session_state.filter_params.get('filter_slope', 0),
        key=f"slope_{st.session_state.form_key}"
    )
    
    filter_area = st.sidebar.number_input(
        "Target Area (sqm/h)", 
        min_value=0, step=100, 
        value=st.session_state.filter_params.get('filter_area', 0),
        key=f"area_{st.session_state.form_key}"
    )
    
    filter_floor = st.sidebar.multiselect(
        "Floor Type", 
        get_uniques('Floor_Type_List'), 
        default=st.session_state.filter_params.get('filter_floor', []),
        key=f"floor_{st.session_state.form_key}"
    )

    # Obstacle & Waste Selection
    st.sidebar.markdown("---")
    st.sidebar.subheader("Obstacle Selection")
    obs_options = get_uniques('Obstacle_List')
    selected_obstacles = []
    if obs_options:
        with st.sidebar.expander(f"Select Obstacles ({len(obs_options)})"):
            for obs in obs_options:
                is_checked = obs in st.session_state.filter_params.get('filter_obstacle', [])
                if st.checkbox(obs, value=is_checked, key=f"chk_obs_{obs}_{st.session_state.form_key}"):
                    selected_obstacles.append(obs)
    else: st.sidebar.info("No Obstacle data found.")

    st.sidebar.subheader("Waste Type Selection")
    waste_options = get_uniques('Waste_Type_List')
    selected_wastes = []
    if waste_options:
        with st.sidebar.expander(f"Select Waste Types ({len(waste_options)})"):
            for wst in waste_options:
                is_checked_w = wst in st.session_state.filter_params.get('filter_waste', [])
                if st.checkbox(wst, value=is_checked_w, key=f"chk_wst_{wst}_{st.session_state.form_key}"):
                    selected_wastes.append(wst)
    else: st.sidebar.info("No Waste Type data found.")

    st.session_state.filter_params = {
        'pilihan_produk': pilihan_produk, 'filter_aisle_cat': filter_aisle_cat,
        'filter_slope': filter_slope, 'filter_type': filter_type,
        'filter_loc': filter_loc, 'filter_area': filter_area,
        'filter_floor': filter_floor, 'filter_obstacle': selected_obstacles,
        'filter_waste': selected_wastes
    }

    # --- FILTERING LOGIC ---
    res = df.copy()
    params = st.session_state.filter_params

    if params['pilihan_produk'] == "Manual (Fiorentini)":
        res = res[res['Brand'].str.contains("Fiorentini", case=False, na=False)]
    elif params['pilihan_produk'] == "Autonomous (Gausium)":
        res = res[res['Brand'].str.contains("Gausium", case=False, na=False)]
        
    if params['filter_aisle_cat']:
        res = res[res['Aisle Category'].isin(params['filter_aisle_cat'])]

    if params['filter_slope'] > 0:
        res['temp_slope'] = pd.to_numeric(res['Max.Slope (°)'], errors='coerce').fillna(0)
        res = res[res['temp_slope'] >= params['filter_slope']]

    if params['filter_type']:
        res = res[res['Product_type'].isin(params['filter_type'])]

    if params['filter_area'] > 0:
        res['Recommended Coverage Area_min'] = pd.to_numeric(res['Recommended Coverage Area_min'], errors='coerce')
        res['Recommended Coverage Area_max'] = pd.to_numeric(res['Recommended Coverage Area_max'], errors='coerce')
        res = res[(res['Recommended Coverage Area_min'] <= params['filter_area']) & (res['Recommended Coverage Area_max'].fillna(float('inf')) >= params['filter_area'])]

    def apply_list_filter(dataframe, target_col, selected_vals):
        if not selected_vals: return dataframe
        actual = get_actual_col(dataframe, target_col)
        if not actual: return dataframe
        pattern = "|".join([re.escape(str(v)) for v in selected_vals])
        return dataframe[dataframe[actual].astype(str).str.contains(pattern, flags=re.IGNORECASE, na=False)]

    res = apply_list_filter(res, 'Processed_Locations', params['filter_loc'])
    res = apply_list_filter(res, 'Floor_Type_List', params['filter_floor'])
    res = apply_list_filter(res, 'Obstacle_List', params['filter_obstacle'])
    res = apply_list_filter(res, 'Waste_Type_List', params['filter_waste'])

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
            
    # --- DIALOG CALLS ---
    if st.session_state.show_dialog and not st.session_state.show_compare:
        show_detail(st.session_state.detail_row, df)
    
    if st.session_state.show_compare:
        show_comparison(st.session_state.compare_base, df)

if __name__ == "__main__":
    main()
