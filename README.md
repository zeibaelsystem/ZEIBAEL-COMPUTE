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
| [`scripts/job_plan.py`](scripts/job_plan.py) | Menyusun matrix dari job manifest yang telah direview |
| [`scripts/aggregate_results.py`](scripts/aggregate_results.py) | Membuat laporan JSON gabungan |
| [`ci/jobs/zeibael_selfcheck.json`](ci/jobs/zeibael_selfcheck.json) | Contoh pekerjaan paralel Python dan Node |
| [`tests/test_job_platform.py`](tests/test_job_platform.py) | Unit test executor dan hasil terstruktur |

Workflow `ci.yml` mendukung `validate`, `python_tests`, `node_tests`, `package`, dan `script`. Untuk menambah pekerjaan, Grace membuat manifest `ci/jobs/<id>.json` atau skrip `.py`/`.sh` publik yang telah direview. Tugas `node_tests` berbasis npm masih memerlukan proyek Node, sedangkan manifest Node sederhana dapat berjalan tanpa `package.json`.

**Hatchable bukan tempat pemrosesan utama:** ia hanya mengirim perintah yang diizinkan ke GitHub Actions. Endpoint dispatcher berada di proyek ZEIBAEL SYSTEM dan hanya mengizinkan akses administrator. Saat ini terdapat dua workflow aktif; runner lainnya atau konfigurasi lama bukan bagian dari jalur operasional utama.

## Generic Job Executor — aktif

Grace dapat membuat **manifest pekerjaan yang direview** di `ci/jobs/<nama>.json`, lalu memicunya melalui `workflow=ci`, `task=script`, `script_id=<nama>`. Hatchable v8 **tidak diubah**. Skrip `.py` dan `.sh` yang sudah ada tetap didukung.

Contoh manifest pada [`ci/jobs/zeibael_selfcheck.json`](ci/jobs/zeibael_selfcheck.json) menjalankan dua job sekaligus, satu untuk unit test Python dan satu untuk pemeriksaan Node.js. Manifest berisi `schema=1`, daftar `jobs`, dan untuk setiap job: `id`, `runtime`, `runner`, `timeout_profile`, serta `commands` (daftar argv, **bukan shell command bebas dari input dispatch**).

**Runtime yang dikonfigurasi:** `python`, `node`, `go`, `rust`, `java`, `docker` (Docker hanya Ubuntu). Runner yang diizinkan dalam manifest: `ubuntu-24.04`, `windows-2022`, dan `macos-15`. **Yang sudah diuji secara end-to-end hanya Python dan Node di Ubuntu**; profil atau OS lainnya belum dinyatakan terverifikasi.

**Paralelisme:** maksimal 4 job dalam satu manifest, maksimal 3 dieksekusi paralel. **Timeout per job:** `short` (10 menit), `standard` (30 menit), `long` (120 menit), atau `extended` (330 menit), dengan batas internal perintah sedikit lebih singkat agar laporan sempat ditulis.

**Laporan:** setiap job menghasilkan `result.json` serta baris log `ZEIBAEL_RESULT_JSON=...`. Job `results` menggabungkan laporan menjadi `aggregate.json`, baris `ZEIBAEL_AGGREGATE_JSON=...`, dan GitHub Actions artifacts dengan retensi satu hari. Grace dapat membaca status/log/artifact metadata melalui GitHub Native Plugin dan menyimpan ringkasan yang sesuai di repository privat. Jangan mengirim data rahasia ke runner publik.

**Bukti integrasi:** [Run #40095281869](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40095281869) — 11 unit test Python lulus, Node berhasil, dua job berjalan dalam matrix, dan agregasi hasil JSON sukses.

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
