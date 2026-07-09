import streamlit as st
import pandas as pd
import os
import glob
import requests
import json
import google.generativeai as genai

# 1. KONFIGURASI LAYOUT HALAMAN (Wajib di baris paling atas)
st.set_page_config(
    page_title="BESTIE - Anti Stunting App", 
    page_icon="👶", 
    layout="centered"
)

# TAMPILAN JUDUL UTAMA (Tema Cerah Pastel Ramah Ibu & Anak)
st.markdown(
    """
    <div style="background-color:#ff6b81; padding:20px; border-radius:15px; margin-bottom:25px;">
        <h1 style="color:white; text-align:center; margin:0; font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
            💡 Rekomendasi Menu Pintar BESTIE
        </h1>
        <p style="color:white; text-align:center; margin:5px 0 0 0; font-size:16px;">
            Aplikasi Optimasi Gizi & Pendamping MPASI Lokal Edukatif Anti-Stunting
        </p>
    </div>
    """, 
    unsafe_allow_html=True
)
st.write("Selamat datang! Sistem pintar ini akan membantu Ibu menyusun menu sehat tinggi protein dengan harga terjangkau.")

st.markdown("---")

# 2. FITUR INPUT DARI IBU
st.header("🔍 Form Skrining & Anggaran")

col1, col2 = st.columns(2)
with col1:
    usia_anak = st.selectbox("Pilih Usia Anak Anda:", ["6-11 bulan", "1-3 tahun", "4-5 tahun"])
    berat_badan = st.number_input("Berat Badan Anak (kg):", min_value=1.0, max_value=30.0, value=10.0, step=0.1)

with col2:
    tinggi_badan = st.number_input("Tinggi/Panjang Badan Anak (cm):", min_value=40.0, max_value=120.0, value=75.0, step=0.1)
    anggaran_harian = st.number_input("Batas Anggaran Makan Harian (Rp):", min_value=5000, max_value=200000, value=25000, step=1000)

st.markdown("---")

# 3. MEMBACA FILE DATA (CSV) YANG SUDAH ANDA DOWNLOAD
st.header("📊 Data Harga Bahan Pangan")

# Perbaikan: Langsung mencari file harga di folder utama repositori GitHub
files_harga = glob.glob("*harga*")

if files_harga:
    try:
        file_target = files_harga[0]
        df_harga = pd.read_csv(file_target, sep=None, engine='python')
        
        st.success(f"Hebat! Berhasil memuat data dari: '{file_target}'")
        st.write("Berikut adalah cuplikan data harga yang Anda unduh:")
        st.dataframe(df_harga.head(10))
        
    except Exception as e:
        st.error(f"File ketemu, tapi gagal membaca isinya. Eror: {e}")
else:
    st.error("Waduh! File yang mengandung kata 'harga' tidak ditemukan di repositori GitHub Anda.")
    
# ==============================================================================
# 4. LOGIKA AI & INTEGRASI API GEMINI AI
# ==============================================================================
try:
    if 'df_harga' in locals():
        df_harga.columns = df_harga.columns.str.strip()
        kolom_kab_kota = [col for col in df_harga.columns if 'kabupaten' in col.lower() or 'kota' in col.lower()][0]
        daftar_wilayah = sorted(df_harga[kolom_kab_kota].unique())

        # PILIHAN FILTER UTAMA
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            pilih_wilayah = st.selectbox("📍 Ketik & Pilih Kabupaten/Kota Anda:", options=daftar_wilayah, index=0)
        with col_filter2:
            cari_bahan = st.text_input("🔍 Cari Bahan Spesifik (Misal: Telur, Ikan, Tahu):", "")

        # INPUT TEKS ALERGI
        input_alergi = st.text_input(
            "⚠️ Tulis Riwayat Alergi Anak (Misal: telur, ikan, kacang):", 
            value="",
            help="Kosongkan jika anak tidak memiliki riwayat alergi."
        )

        if st.button("Hitung Rekomendasi Menu"):
            # Perbaikan: Membaca file data bahan pangan yang ada di GitHub (Ganti ke file data_bahan_pangan.csv jika diperlukan)
            df_gizi = pd.read_csv("data_bahan_pangan.csv", sep=None, engine='python')
            df_gizi.columns = df_gizi.columns.str.strip().str.lower()
            
            def deteksi_alergen(nama_bahan):
                nama_lower = str(nama_bahan).lower()
                if 'telur' in nama_lower: return 'Telur'
                elif any(kata in nama_lower for kata in ['ikan', 'teri', 'udang', 'mujair', 'seafood', 'kepiting', 'cumi']): return 'Ikan/Seafood'
                elif any(kata in nama_lower for kata in ['kacang', 'tempe', 'tahu', 'kedelai']): return 'Kacang/Kedelai'
                elif 'susu' in nama_lower: return 'Susu'
                else: return 'Aman (Non-Alergen)'

            df_gizi['allergen_type'] = df_gizi['name'].apply(deteksi_alergen)
            df_harga_lokal = df_harga[df_harga[kolom_kab_kota] == pilih_wilayah]
            
            kamus_harga_live = {}
            kolom_komoditas = [col for col in df_harga.columns if 'komoditas' in col.lower()][0]
            kolom_harga = [col for col in df_harga.columns if 'level 2' in col.lower() or 'het' in col.lower() or 'harga' in col.lower()][0]
            
            for index, row in df_harga_lokal.iterrows():
                komoditas_nama = str(row[kolom_komoditas]).lower()
                harga_nilai = row[kolom_harga]
                if isinstance(harga_nilai, str):
                    harga_nilai = float(harga_nilai.replace('.', '').replace('Rp', '').strip())
                
                if 'telur' in komoditas_nama: kamus_harga_live['Telur Ayam'] = harga_nilai / 10
                elif 'beras' in komoditas_nama: kamus_harga_live['Nasi Putih'] = (harga_nilai / 10) * 0.4

            if 'harga_per_100g' not in df_gizi.columns:
                df_gizi['harga_per_100g'] = 2000.0
                
            for bahan, harga_baru in list(kamus_harga_live.items()):
                df_gizi.loc[df_gizi['name'].str.lower() == bahan.lower(), 'harga_per_100g'] = harga_baru

            df_terjangkau = df_gizi[df_gizi['harga_per_100g'] <= (anggaran_harian / 3)]
            
            if input_alergi.strip():
                list_alergi = [kata.strip().lower() for kata in input_alergi.split(',')]
                for kata_alergi in list_alergi:
                    if kata_alergi:
                        df_terjangkau = df_terjangkau[
                            (~df_terjangkau['name'].str.contains(kata_alergi, case=False, na=False)) & 
                            (~df_terjangkau['allergen_type'].str.contains(kata_alergi, case=False, na=False))
                        ]

            if usia_anak == "6-11 bulan":
                kata_kunci_dilarang = ['kerupuk', 'dendeng', 'kering', 'asin', 'sale', 'mentah', 'kayu', 'tepung', 'goreng', 'keripik', 'kripik', 'snack']
                for kata in kata_kunci_dilarang:
                    df_terjangkau = df_terjangkau[~df_terjangkau['name'].str.contains(kata, case=False, na=False)]
            elif usia_anak == "1-3 tahun":
                kata_kunci_dilarang = ['kerupuk', 'dendeng', 'mentah', 'kayu']
                for kata in kata_kunci_dilarang:
                    df_terjangkau = df_terjangkau[~df_terjangkau['name'].str.contains(kata, case=False, na=False)]

            if cari_bahan:
                df_terjangkau = df_terjangkau[df_terjangkau['name'].str.contains(cari_bahan, case=False, na=False)]
            
            df_rekomendasi = df_terjangkau.sort_values(by='proteins', ascending=False).head(5)
            
            if df_rekomendasi.empty:
                st.warning("Mohon maaf, tidak ditemukan bahan makanan aman.")
            else:
                st.success(f"Berhasil menyusun rekomendasi menu lokal aman khusus {pilih_wilayah}!")
                st.write("### 🍳 Kombinasi Bahan Makanan Aman Top 5 Tinggi Protein:")
                st.dataframe(df_rekomendasi[['name', 'allergen_type', 'proteins', 'calories', 'harga_per_100g']])
                
                # --- PROSES INTEGRASI API GOOGLE GEMINI AI ---
                st.markdown("---")
                st.subheader("🤖 Analisis Konsultasi Otomatis (Gemini AI)")
                
                with st.spinner("Asisten BESTIE sedang menganalisis kandungan gizi lewat API Gemini..."):
                    try:
                        API_KEY_GEMINI = "AQ.Ab8RN6LAEeWVY5dcJdweYHq8Lh1aXyx0LtP7sPIdrQJwOEaIIQ" 
                        
                        list_nama_menu = df_rekomendasi['name'].tolist()
                        prompt_ai = f"""
                        Anda adalah seorang dokter spesialis anak dan pakar gizi stunting (Nama Aplikasi Anda: BESTIE).
                        Berikan analisis edukatif singkat dan ramah untuk seorang Ibu berdasarkan data berikut:
                        - Usia Anak: {usia_anak}
                        - Batas Anggaran: Rp {anggaran_harian}/hari
                        - Riwayat Alergi: {input_alergi if input_alergi else 'Tidak ada'}
                        - Bahan Pangan yang disarankan oleh sistem kami: {', '.join(list_nama_menu)}
                        
                        Tolong berikan saran penyajian tekstur yang tepat dan cara memasak bahan-bahan di atas agar kandungan proteinnya tetap terjaga demi mencegah stunting. Tulis maksimal 3 paragraf pendek dengan gaya bahasa yang menyemangati ibu balita.
                        """
                        
                        url_api = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY_GEMINI}"
                        headers = {'Content-Type': 'application/json'}
                        
                        payload = {
                            "contents": [{
                                "parts": [{"text": prompt_ai}]
                            }],
                            "safetySettings": [
                                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                            ]
                        }
                        
                        respons_google = requests.post(url_api, headers=headers, json=payload)
                        hasil_json = respons_google.json()
                        
                        if 'candidates' in hasil_json and len(hasil_json['candidates']) > 0:
                            candidate = hasil_json['candidates'][0]
                            if 'content' in candidate and 'parts' in candidate['content']:
                                teks_jawaban_ai = candidate['content']['parts'][0]['text']
                                st.info(teks_jawaban_ai)
                            else:
                                st.warning("👶 *Asisten BESTIE menyarankan:* Pastikan menu diolah dengan tekstur lembut/saring (bubur lumat) tanpa garam berlebih, serta pastikan bahan dimasak hingga benar-benar matang sempurna.")
                        else:
                            if 'error' in hasil_json:
                                st.write(f"Sistem sedang sinkronisasi kode: {hasil_json['error']['message']}")
                            st.warning("👶 *Asisten BESTIE menyarankan:* Pastikan menu diolah dengan tekstur lembut/saring (bubur lumat) tanpa garam berlebih, serta pastikan bahan dimasak hingga benar-benar matang sempurna.")
                        
                    except Exception as error_api:
                        st.error(f"Gagal memproses respons AI. Detail: {error_api}")
                        st.warning("🤖 *Catatan: Pastikan laptop terhubung internet.*")
except Exception as e:
    st.error(f"Gagal memproses menu rekomendasi pintar. Eror: {e}")
