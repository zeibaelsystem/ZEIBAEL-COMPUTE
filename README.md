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
| [`ci/jobs/runtime_selfcheck.json`](ci/jobs/runtime_selfcheck.json) | Uji Go, Rust, Java, dan Docker |
| [`ci/jobs/compiler_build_selfcheck.json`](ci/jobs/compiler_build_selfcheck.json) | Build dan jalankan C/C++, Go, Rust, Java; unit test Python |
| [`ci/jobs/docker_npm_selfcheck.json`](ci/jobs/docker_npm_selfcheck.json) | Uji `npm ci/test`, build/run Docker, Docker Compose |
| [`ci/jobs/cross_platform_selfcheck.json`](ci/jobs/cross_platform_selfcheck.json) | Uji Linux ARM64, Windows x64, dan macOS ARM64 |
| [`ci/fixtures/`](ci/fixtures/) | Source proyek contoh publik untuk pengujian fungsional |
| [`tests/test_job_platform.py`](tests/test_job_platform.py) | Unit test executor dan hasil terstruktur |

Workflow `ci.yml` mendukung `validate`, `python_tests`, `node_tests`, `package`, dan `script`. Untuk menambah pekerjaan, Grace membuat manifest `ci/jobs/<id>.json` atau skrip `.py`/`.sh` publik yang telah direview. Tugas `node_tests` berbasis npm masih memerlukan proyek Node, sedangkan manifest Node sederhana dapat berjalan tanpa `package.json`.

**Hatchable bukan tempat pemrosesan utama:** ia hanya mengirim perintah yang diizinkan ke GitHub Actions. Endpoint dispatcher berada di proyek ZEIBAEL SYSTEM dan hanya mengizinkan akses administrator. Saat ini terdapat dua workflow aktif; runner lainnya atau konfigurasi lama bukan bagian dari jalur operasional utama.

## Generic Job Executor — aktif

Grace dapat membuat **manifest pekerjaan yang direview** di `ci/jobs/<nama>.json`, lalu memicunya melalui `workflow=ci`, `task=script`, `script_id=<nama>`. Hatchable v8 **tidak diubah**. Skrip `.py` dan `.sh` yang sudah ada tetap didukung.

Contoh manifest pada [`ci/jobs/zeibael_selfcheck.json`](ci/jobs/zeibael_selfcheck.json) menjalankan dua job sekaligus, satu untuk unit test Python dan satu untuk pemeriksaan Node.js. Manifest berisi `schema=1`, daftar `jobs`, dan untuk setiap job: `id`, `runtime`, `runner`, `timeout_profile`, serta `commands` (daftar argv, **bukan shell command bebas dari input dispatch**).

**Runtime yang dikonfigurasi:** `python`, `node`, `go`, `rust`, `java`, `docker` (Docker hanya Ubuntu). Runner yang diizinkan dalam manifest: `ubuntu-24.04` (x64), `ubuntu-24.04-arm` (ARM64), `windows-2022` (x64), dan `macos-15` (ARM64). **Seluruh enam profil runtime telah lolos uji smoke di Ubuntu**: Python, Node, Go, Rust, Java, dan Docker. **Build nyata** C/C++, Go, Rust, Java, pengujian npm, Docker image, Docker container, dan Docker Compose juga telah lulus. Linux ARM64, Windows x64, dan macOS ARM64 lolos pemeriksaan OS/arsitektur menggunakan Python; kombinasi toolchain lain pada sistem operasi tersebut belum otomatis teruji.

**Paralelisme:** maksimal 4 job dalam satu manifest, maksimal 3 dieksekusi paralel. **Timeout per job:** `short` (10 menit), `standard` (30 menit), `long` (120 menit), atau `extended` (330 menit), dengan batas internal perintah sedikit lebih singkat agar laporan sempat ditulis.

**Laporan:** setiap job menghasilkan `result.json` serta baris log `ZEIBAEL_RESULT_JSON=...`. Job `results` menggabungkan laporan menjadi `aggregate.json`, baris `ZEIBAEL_AGGREGATE_JSON=...`, dan GitHub Actions artifacts dengan retensi satu hari. Grace dapat membaca status/log/artifact metadata melalui GitHub Native Plugin dan menyimpan ringkasan yang sesuai di repository privat. Jangan mengirim data rahasia ke runner publik.

**Bukti integrasi:** [Run #40095281869](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40095281869) — 11 unit test Python lulus, Node berhasil, dua job matrix dan JSON gabungan. [Run #40095607051](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40095607051) — Go, Rust, Java, Docker berhasil (empat job, maksimal tiga sekaligus), serta JSON gabungan sukses. Kedua uji memakai dispatcher Hatchable yang sudah ada, tanpa mengubah konfigurasinya.

## Verifikasi end-to-end terbaru

| Kemampuan | Bukti |
|---|---|
| Build C/C++, Go, Rust, Java + 15 unit test | [Run #40096787388](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40096787388) |
| npm, Docker image, container, Docker Compose | [Run #40096861811](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40096861811) |
| Linux ARM64, Windows x64, macOS ARM64 | [Run #40097047606](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40097047606) |
| Negative test: job gagal harus membuat workflow dan laporan gagal | [Run #40097157009](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40097157009) — sengaja FAILURE (exit 19), perilaku benar |

**Regresi terakhir:** [16 unit test berhasil pada commit terbaru](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40097391339). Manifest negative test sementara telah dihapus setelah digunakan, sementara riwayat run dan bukti tetap tersimpan.

**Pelaporan fail-closed:** agregator mengecek jumlah laporan sesuai jumlah job yang direncanakan, mendeteksi ID job duplikat, dan mengembalikan status failure apabila ada job gagal atau laporan hilang. Laporan per-job dan aggregate JSON tetap dibuat pada kegagalan biasa; perubahan sebelum driver sempat membuat laporan masih dapat menyebabkan job failure tanpa report lengkap. Artifact hanya disimpan 1 hari.

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

## Reliability, capacity and security (October 2026)

- `ci.yml` and `artifact.yml` use `queue: max` with `cancel-in-progress: false`, so the GitHub Actions concurrency queue can hold multiple pending jobs. GitHub documents up to 100 pending runs per group, after which excess can be canceled; ordering is not guaranteed by dispatch order.
- Manifest cap is now 8 trusted jobs with `max-parallel: 4` (not unlimited). The execution time budget is **shared by all commands** in a manifest job.
- `job_ids` are propagated from the validated job plan to the result aggregator, preventing a mismatched but equal-size report collection from being treated as success. Each run is identified by GitHub run ID.
- GitHub-managed actions are pinned to full immutable SHA commits; `.github/workflows/quality.yml` checks Python regressions and CodeQL on main.
- Optional `platform_extensions` is a fixture-based smoke test for HTTP APIs, temporary SQLite, TypeScript and PWA source contract; not a claim of Playwright or real offline E2E.
- Public artifacts expire after 1 day. Grace can archive a public-safe summary to the private registry through the connected GitHub app **when actively asked**, not by granting the public runner private tokens or doing background work.
- These changes target the free standard runners on public repositories; no billing, private code checkout or external secret stores are used.
