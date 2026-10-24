# ZEIBAEL COMPUTE

**Runner GitHub Actions publik untuk pekerjaan komputasi pengembangan ZEIBAEL · FREE-ONLY**

Repository ini berfungsi sebagai **mesin eksekusi sementara** ketika suatu pekerjaan benar-benar membutuhkan runtime di luar kemampuan operasi langsung GitHub Native Plugin. Fokusnya **bukan satu jenis output**, melainkan menjalankan pekerjaan pengembangan software yang sesuai: validasi, tes otomatis, menjalankan skrip terkontrol, memproses pekerjaan build, dan tugas CI lain yang dapat ditambahkan sesuai kebutuhan.

Repository utama dan data internal tetap berada di **ZEIBAEL-SYSTEM (private)**. Runner publik hanya menggunakan material yang memang aman diproses secara publik.

## Pemilihan jalur otomatis oleh Grace

Bos **tidak perlu** meminta “pakai GitHub Actions”, “jalankan di runner”, atau “panggil Hatchable”. Grace memilih sendiri:

1. **GitHub Native Plugin** untuk pekerjaan repository yang dapat dilakukan langsung.
2. **ZEIBAEL-COMPUTE** jika pekerjaan pengembangan memerlukan eksekusi pada runner GitHub-hosted.
3. **Hatchable ZEIBAEL SYSTEM** hanya sebagai dispatcher jika plugin native belum menyediakan pemicu `workflow_dispatch`.
4. **GitHub Native Plugin** kembali dipakai untuk membaca status/log dan menyimpan hasil yang sesuai ke repository privat selama pekerjaan berlangsung.

```text
Bos -> Grace -> Periksa kemampuan native
                    |
          +---------+----------+
          |                    |
    Bisa langsung         Perlu runner
          |                    |
    GitHub Plugin      GitHub Actions public
          |                    ^
          |          Hatchable hanya jika
          |          dispatch native tidak ada
          +----------+---------+
                     |
              Grace cek hasil
                     |
              Simpan ke private
              lewat GitHub Plugin
```

## Infrastruktur yang aktif

| Komponen | Peran |
|---|---|
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | Workflow modular untuk pemeriksaan dan pekerjaan pengembangan |
| [`.github/workflows/artifact.yml`](.github/workflows/artifact.yml) | Workflow tambahan untuk menyiapkan keluaran proyek/skill publik |
| [`scripts/ci_driver.py`](scripts/ci_driver.py) | Pelaksana pekerjaan terdefinisi pada runner |
| [`tests/test_ci_driver.py`](tests/test_ci_driver.py) | Unit test dan pemeriksaan keselamatan skrip CI |

Workflow `ci.yml` saat ini mendukung `validate`, `python_tests`, `node_tests`, `package`, dan `script`. Untuk menambah kebutuhan pengembangan yang spesifik, Grace dapat membuat/memperbarui skrip yang direview dalam `ci/jobs/<id>.py` atau `.sh` melalui GitHub Native Plugin, kemudian memicu tugas `script`. Kemampuan yang membutuhkan berkas tambahan tidak otomatis tersedia sebelum berkas tersebut dibuat; misalnya tugas Node.js memerlukan proyek Node dengan skrip tes.

**Hatchable bukan tempat pemrosesan utama:** ia hanya mengirim perintah yang diizinkan ke GitHub Actions. Endpoint dispatcher berada di proyek ZEIBAEL SYSTEM dan hanya mengizinkan akses administrator. Saat ini terdapat dua workflow aktif; runner lainnya atau konfigurasi lama bukan bagian dari jalur operasional utama.

## Batas keamanan dan penggunaan

- **Public berarti terlihat publik.** Jangan menaruh token, kredensial, kode privat, data pelanggan, maupun hasil sensitif dalam repository, input workflow, log, atau artifact.
- Runner tidak mewarisi akses Grace ke repository privat. Alur aktif **tidak memerlukan secret privat tambahan**; sumber privat tidak dicheckout otomatis ke runner.
- Gunakan runner untuk pengembangan, pengujian, dan pekerjaan CI sesuai ketentuan GitHub, **bukan** komputasi umum tanpa batas.
- Ikuti batas durasi job, konkurensi, penyimpanan, dan kebijakan penggunaan GitHub-hosted runners.
- **FREE-ONLY:** tidak mengaktifkan billing, PAYG, trial berbayar, atau fitur yang dapat menimbulkan tagihan.
- Semua pekerjaan baru dan hasilnya harus diverifikasi; jangan menganggap workflow berhasil hanya karena permintaan dispatch diterima.

## Bukti pengujian

- [CI modular dan unit test — berhasil](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40048674561)
- [Halaman Actions](../../actions) untuk melihat status eksekusi terbaru

_Dokumentasi diperbarui 24 Oktober 2026. Grace bertanggung jawab memilih jalur eksekusi sesuai pekerjaan, bukan meminta Bos mengingat detail workflow._
