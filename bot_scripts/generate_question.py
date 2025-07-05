import os
import shutil # Untuk menyalin file
from github import Github
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import subprocess

def generate_question_paper_pdf(subject, grade, exam_title, teacher_name, topic_1, topic_2, topic_3, logo_filename="logo_sekolah.png"):
    # 1. Setup Jinja2 Environment for LaTeX template
    # Pastikan path ke templates sudah benar dari root repo
    template_loader = FileSystemLoader(searchpath="./templates")
    env = Environment(loader=template_loader,
                       block_start_string='\BLOCK{',
                       block_end_string='}',
                       variable_start_string='\VAR{',
                       variable_end_string='}',
                       comment_start_string='\#{',
                       comment_end_string='}#') # Sesuaikan delimiter Jinja2 agar tidak bentrok dengan LaTeX
    template = env.get_template("question_template.tex")

    # 2. Get current date for the template
    current_date = datetime.now().strftime("%d %B %Y")

    # 3. Render the LaTeX template with provided data
    output_latex_content = template.render(
        subject=subject,
        grade=grade,
        date=current_date,
        teacher_name=teacher_name,
        exam_title=exam_title,
        topic_1=topic_1,
        topic_2=topic_2,
        topic_3=topic_3
    )

    # 4. Generate temporary .tex filename and path for compilation
    temp_tex_filename_base = f"temp_soal_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    temp_tex_path = os.path.join("/tmp", f"{temp_tex_filename_base}.tex")

    with open(temp_tex_path, "w", encoding="utf-8") as f:
        f.write(output_latex_content)

    # 5. Copy the logo image to the temporary directory for LaTeX compilation
    # Ini penting karena pdflatex mungkin tidak bisa mengakses path relatif dari /tmp
    logo_source_path = os.path.join(os.getcwd(), "assets", "images", logo_filename)
    logo_dest_path = os.path.join("/tmp", logo_filename)
    if os.path.exists(logo_source_path):
        shutil.copy(logo_source_path, logo_dest_path)
        print(f"Logo '{logo_filename}' berhasil disalin ke '/tmp/'.")
        # Ubah path di template LaTeX untuk gambar menjadi hanya nama filenya
        # (ini sudah kita antisipasi dengan path relatif di LaTeX template)
    else:
        print(f"Peringatan: File logo '{logo_source_path}' tidak ditemukan. Header gambar mungkin tidak muncul.")
        # Jika gambar tidak ditemukan, mungkin Anda ingin menghapus baris gambar dari LaTeX template secara dinamis
        # Atau minta guru untuk memastikan gambar ada.

    # 6. Compile LaTeX to PDF
    output_pdf_filename = f"Soal_{subject}_{grade}_{exam_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    output_pdf_path = os.path.join("/tmp", output_pdf_filename)

    try:
        # Jalankan pdflatex di direktori /tmp agar gambar bisa diakses langsung
        # Menggunakan -output-directory=/tmp untuk memastikan semua output di /tmp
        process = subprocess.run(
            ["pdflatex", "-output-directory=/tmp", temp_tex_path],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"LaTeX compilation stdout:\n{process.stdout}")
        print(f"LaTeX compilation stderr:\n{process.stderr}") # Output error jika ada
        print(f"PDF '{output_pdf_filename}' berhasil dikompilasi di '/tmp/'.")

        # 7. Baca file PDF yang sudah jadi
        with open(output_pdf_path, "rb") as f_pdf: # Mode 'rb' untuk binary
            pdf_content = f_pdf.read()

        # 8. Upload PDF ke GitHub
        github_token = os.environ.get('GITHUB_TOKEN')
        if not github_token:
            raise ValueError("GITHUB_TOKEN environment variable not set.")

        repo_name = os.environ.get('GITHUB_REPOSITORY') # Format: owner/repo_name
        if not repo_name:
            raise ValueError("GITHUB_REPOSITORY environment variable not set.")

        # Inisialisasi PyGithub
        g = Github(github_token)
        # Perhatikan: get_repo butuh nama repo (bukan owner/repo_name)
        repo = g.get_user().get_repo(repo_name.split('/')[1])

        # Path di GitHub repo tempat file PDF akan disimpan
        github_file_path = f"generated_questions/{output_pdf_filename}"

        try:
            repo.create_file(github_file_path,
                             f"Membuat soal PDF: {output_pdf_filename}",
                             pdf_content, # Konten binary
                             branch="main") # Pastikan branch target
            print(f"Soal PDF '{output_pdf_filename}' berhasil diunggah ke GitHub di '{github_file_path}'.")
        except Exception as e:
            print(f"Gagal mengunggah soal PDF ke GitHub: {e}")
            raise # Re-raise exception for GitHub Actions to catch

    except subprocess.CalledProcessError as e:
        print(f"Gagal mengompilasi LaTeX: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        log_file_path = os.path.join("/tmp", f"{temp_tex_filename_base}.log")
        if os.path.exists(log_file_path):
            with open(log_file_path, "r") as log_f:
                print(f"LaTeX log:\n{log_f.read()}")
        raise # Re-raise exception for GitHub Actions to catch
    finally:
        # 9. Bersihkan file sementara dari /tmp
        files_to_clean = [
            temp_tex_path,
            output_pdf_path,
            os.path.join("/tmp", f"{temp_tex_filename_base}.aux"),
            os.path.join("/tmp", f"{temp_tex_filename_base}.log"),
            os.path.join("/tmp", f"{temp_tex_filename_base}.out"),
            os.path.join("/tmp", f"{temp_tex_filename_base}.toc"),
            logo_dest_path # Hapus juga salinan logo di /tmp
        ]
        for f_path in files_to_clean:
            if os.path.exists(f_path):
                os.remove(f_path)
                print(f"Membersihkan: {f_path}")

if __name__ == "__main__":
    # Nilai-nilai ini akan diambil dari input GitHub Actions
    # Menggunakan os.environ.get untuk mengambil dari environment variables
    # Ganti "logo_sekolah.png" dengan nama file gambar Anda!
    generate_question_paper_pdf(
        subject=os.environ.get("INPUT_SUBJECT", "Matematika"),
        grade=os.environ.get("INPUT_GRADE", "8B"),
        exam_title=os.environ.get("INPUT_EXAM_TITLE", "Ulangan Harian 1"),
        teacher_name=os.environ.get("INPUT_TEACHER_NAME", "Bapak Budi"),
        topic_1=os.environ.get("INPUT_TOPIC_1", "Aljabar"),
        topic_2=os.environ.get("INPUT_TOPIC_2", "Geometri"),
        topic_3=os.environ.get("INPUT_TOPIC_3", "Statistika"),
        logo_filename="logo_sekolah.png" # PASTIKAN INI SAMA DENGAN NAMA FILE LOGO ANDA
    )