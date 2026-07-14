import random

# Kumpulan nama depan
nama_depan_pria = [
    "Budi", "Agus", "Ahmad", "Reza", "Rizky", "Hendra", "Bagus", "Ilham", 
    "Dwi", "Eko", "Fajar", "Rendi", "Aditya", "Dimas", "Wahyu", "Gilang", 
    "Bayu", "Arif", "Iqbal", "Joko", "Tegar", "Rangga", "Arya", "Kevin"
]

nama_depan_wanita = [
    "Siti", "Ayu", "Putri", "Sri", "Nur", "Dewi", "Dian", "Sari", 
    "Rini", "Lestari", "Intan", "Nisa", "Mega", "Rina", "Ratna", 
    "Wulan", "Fitri", "Indah", "Dina", "Nadia", "Siska", "Aulia", "Zahra"
]

# Kumpulan nama belakang khusus Pria / Umum
nama_belakang_pria = [
    "Saputra", "Pratama", "Wijaya", "Kusuma", "Setiawan", "Santoso", 
    "Hidayat", "Nugroho", "Wahyudi", "Ramadhan", "Siregar", "Nasution", 
    "Sanjaya", "Suryono", "Lubis", "Wibowo", "Gunawan", "Yulianto", 
    "Pangestu", "Mahendra", "Baskoro", "Firmansyah", "Mulyono", "Syahputra"
]

# Kumpulan nama belakang khusus Wanita
nama_belakang_wanita = [
    "Saputri", "Lestari", "Salsabila", "Ningsih", "Sari", "Pertiwi",
    "Handayani", "Wahyuni", "Susanti", "Puspita", "Anggraini", "Maharani",
    "Agustin", "Permata", "Lubis", "Siregar", "Wijaya", "Nasution"
]

def generate_nama_indonesia(gender="acak"):
    """
    Menghasilkan nama orang Indonesia secara acak.
    gender: 'pria', 'wanita', atau 'acak' (default)
    """
    gender = gender.lower()
    if gender == "acak":
        gender = random.choice(["pria", "wanita"])
        
    if gender == "pria":
        depan = random.choice(nama_depan_pria)
        belakang = random.choice(nama_belakang_pria)
    else: # wanita
        depan = random.choice(nama_depan_wanita)
        belakang = random.choice(nama_belakang_wanita)
    
    return f"{depan} {belakang}"

def generate_banyak_nama(jumlah, gender="acak"):
    return [generate_nama_indonesia(gender) for _ in range(jumlah)]

def generate_email_username(nama=None):
    """
    Membuat username email dari nama orang dan menambahkan angka acak ganjil.
    """
    if not nama:
        nama = generate_nama_indonesia()
        
    # Hapus spasi dan jadikan huruf kecil semua
    nama_bersih = nama.replace(" ", "").lower()
    
    # Menghasilkan angka acak dari 10 hingga 999
    angka = random.randint(10, 999)
    # Jika angkanya genap, tambah 1 agar menjadi ganjil
    if angka % 2 == 0:
        angka += 1
        
    return f"{nama_bersih}{angka}"

if __name__ == "__main__":
    for _ in range(100):
        nama = generate_nama_indonesia()
        email_username = generate_email_username(nama)
        print(email_username)
