import os

# ==========================================
# KONFIGURASI GMAIL DOT TRICK
# ==========================================
BASE_EMAIL = "rafliabdulbayhaqqy"
DOMAIN_EMAIL = "@googlemail.com"
MAX_EMAILS = 1000

def generate_dot_variants(base_username):
    variants = []
    n = len(base_username) - 1
    # Loop untuk mendapatkan semua kemungkinan (2^n)
    for i in range(2**n):
        binary = bin(i)[2:].zfill(n)
        variant = base_username[0]
        for j, bit in enumerate(binary):
            if bit == '1':
                variant += '.'
            variant += base_username[j+1]
        variants.append(variant)
    return variants

def main():
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "email.txt")
    
    # Ambil semua kemungkinan variasi titik
    all_variants = generate_dot_variants(BASE_EMAIL)
    
    # Batasi sesuai MAX_EMAILS (150)
    variants_to_save = all_variants[:MAX_EMAILS]
    
    with open(file_path, 'w') as f:
        for username in variants_to_save:
            email = f"{username}{DOMAIN_EMAIL}"
            f.write(email + "\n")
            
    print(f"Berhasil membuat {len(variants_to_save)} email (Gmail Dot Trick) untuk {BASE_EMAIL}{DOMAIN_EMAIL} di email.txt!")

if __name__ == '__main__':
    main()
