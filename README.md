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
| [`ci/jobs/cross_platform_selfcheck.json`](ci/jobs/cross_platform_selfcheck.json) | Uji Ubuntu Linux 24.04 — ARM64, Microsoft Windows Server 2022 — x64, dan Apple macOS 15 — Apple Silicon ARM64 |
| [`ci/fixtures/`](ci/fixtures/) | Source proyek contoh publik untuk pengujian fungsional |
| [`tests/test_job_platform.py`](tests/test_job_platform.py) | Unit test executor dan hasil terstruktur |

Workflow `ci.yml` mendukung `validate`, `python_tests`, `node_tests`, `package`, dan `script`. Untuk menambah pekerjaan, Grace membuat manifest `ci/jobs/<id>.json` atau skrip `.py`/`.sh` publik yang telah direview. Tugas `node_tests` berbasis npm masih memerlukan proyek Node, sedangkan manifest Node sederhana dapat berjalan tanpa `package.json`.

**Hatchable bukan tempat pemrosesan utama:** ia hanya mengirim perintah yang diizinkan ke GitHub Actions. Endpoint dispatcher berada di proyek ZEIBAEL SYSTEM dan hanya mengizinkan akses administrator. Saat ini terdapat tiga workflow: `ci.yml` dan `artifact.yml` untuk eksekusi atas permintaan, serta `quality.yml` untuk pengujian pada perubahan kode. Workflow quality tidak ditambahkan ke jalur dispatch job biasa.

## Generic Job Executor — aktif

Grace dapat membuat **manifest pekerjaan yang direview** di `ci/jobs/<nama>.json`, lalu memicunya melalui `workflow=ci`, `task=script`, `script_id=<nama>`. Kode dispatcher Hatchable **tidak diubah** selama peningkatan GitHub Compute; versi proyek Hatchable saat ini adalah v10 (heartbeat harian). Skrip `.py` dan `.sh` yang sudah ada tetap didukung.

Contoh manifest pada [`ci/jobs/zeibael_selfcheck.json`](ci/jobs/zeibael_selfcheck.json) menjalankan dua job sekaligus, satu untuk unit test Python dan satu untuk pemeriksaan Node.js. Manifest berisi `schema=1`, daftar `jobs`, dan untuk setiap job: `id`, `runtime`, `runner`, `timeout_profile`, serta `commands` (daftar argv, **bukan shell command bebas dari input dispatch**).

**Runtime yang dikonfigurasi (18):** `python`, `node`, `go`, `rust`, `java`, `docker`, `php`, `ruby`, `dotnet`, `kotlin`, `swift`, `powershell`, `perl`, `julia`, `haskell`, `fortran`, `r`, `scala` (Docker hanya Ubuntu). Runner yang diizinkan dalam manifest tercantum pada tabel **Standar penamaan runner ZEIBAEL** di bawah, dengan nama lengkap dan label asli GitHub. **Seluruh enam profil runtime telah lolos uji smoke di Ubuntu**: Python, Node, Go, Rust, Java, dan Docker. **Build nyata** C/C++, Go, Rust, Java, pengujian npm, Docker image, Docker container, dan Docker Compose juga telah lulus. Ubuntu Linux 24.04 — ARM64, Microsoft Windows Server 2022 — x64, dan Apple macOS 15 — Apple Silicon ARM64 lolos pemeriksaan OS/arsitektur menggunakan Python; kombinasi toolchain lain pada sistem operasi tersebut belum otomatis teruji.

## Dukungan bahasa tambahan: PHP, Ruby, .NET/C#, Kotlin, Swift

Bahasa berikut dijalankan pada **standard GitHub-hosted runner yang sama**, bukan layanan berbayar atau mesin terpisah. Alat CLI memakai toolchain yang sudah tersedia dalam image runner. Untuk mengurangi kegagalan tak terduga, ZEIBAEL membatasi kombinasi baru sampai diverifikasi:

| Runtime manifest | CLI | Runner yang disetujui ZEIBAEL |
|---|---|---|
| `php` | `php` | `ubuntu-24.04`, `ubuntu-24.04-arm`, `windows-2022`, `windows-11-arm`, `macos-15-intel` |
| `ruby` | `ruby` | `ubuntu-24.04`, `ubuntu-24.04-arm`, `windows-2022`, `windows-11-arm`, `macos-15-intel`, `macos-15` |
| `dotnet` | `dotnet` (C#/.NET) | `ubuntu-24.04`, `ubuntu-24.04-arm`, `windows-2022`, `windows-11-arm`, `macos-15-intel`, `macos-15` |
| `kotlin` | `kotlinc`, `java` (JVM) | `ubuntu-24.04`, `ubuntu-24.04-arm`, `windows-2022`, `windows-11-arm`, `macos-15-intel`, `macos-15` |
| `swift` | `swift` | `ubuntu-24.04`, `ubuntu-24.04-arm`, `macos-15-intel`, `macos-15` |

`ci/jobs/additional_languages_smoke.json` membuktikan enam kombinasi awal. `ci/jobs/languages_platform_a.json` dan `ci/jobs/languages_platform_b.json` menguji 21 kombinasi tambahan dengan program nyata di GitHub-hosted standard runner; hasil terbaru harus dikonfirmasi dari GitHub Actions run yang tepat. PHP pada macOS Apple Silicon, Swift pada Windows, dan seluruh lima bahasa pada Ubuntu Slim masih **dibatasi internal ZEIBAEL** karena belum didukung/dibuktikan untuk konfigurasi ini. Manifest memakai batas timeout yang sama; `output_files` tetap tidak aktif secara default. Toolchain bawaan image dapat berubah ketika provider memperbarui image; periksa log untuk membedakan kegagalan lingkungan/provider dari allowlist internal ZEIBAEL.

**Hasil verifikasi lintas platform (25 Oktober 2026):** seluruh **21 dari 21 kombinasi tambahan berhasil diuji** di GitHub Actions. Totalnya **27 kombinasi runtime/runner teruji** untuk lima bahasa tambahan, termasuk enam kombinasi awal. Rinciannya: PHP (5), Ruby (6), .NET/C# (6), Kotlin JVM (6), dan Swift (4).

- [Run A — 11 kombinasi sukses](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40120314137); [Run B — 6 sukses, 4 Windows awalnya gagal](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40120319003).
- [Run Windows setelah perbaikan pertama](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40120709266): Kotlin Windows x64/ARM64 sukses, .NET Windows masih gagal karena lingkungan NuGet.
- [Run Windows .NET final #40179467267](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40179467267): kedua job **.NET Windows Server 2022 x64** dan **Windows 11 ARM64** sukses; `ZEIBAEL_DOTNET_OK`, exit code `0`; agregasi `success`. [Quality/CodeQL pada commit perbaikan](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40179455830) juga `success`.
- **Diagnosis kegagalan sebelumnya: INTERNAL ZEIBAEL**, bukan kuota GitHub. Allowlist variabel environment awalnya tidak meneruskan konfigurasi standar Windows/NuGet; sekalipun nama variabel sudah didaftarkan, Python Windows menormalisasi kunci menjadi uppercase sehingga pencocokan yang case-sensitive membuangnya. Perbaikan final menggunakan pencocokan allowlist case-insensitive, tanpa mengizinkan variabel rahasia seperti `GITHUB_TOKEN`. [PR #9](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/pull/9) digabung; **52/52 tes regresi lulus**.
- **Cakupan klaim:** uji ini membuktikan menjalankan program smoke nyata pada kombinasi runner yang disebutkan. Ini bukan bukti semua framework/beban kerja produksi atau semua kombinasi yang belum diizinkan, misalnya Swift pada Windows dan runtime baru pada `ubuntu-slim`.

**Batas yang berasal dari ZEIBAEL sendiri:** daftar kombinasi runner/bahasa dan CLI yang diizinkan, maksimal 12 perintah/job, jumlah job 20, serta durasi 10/30/120/330 menit. Jangan keliru menganggap pembatasan internal tersebut sebagai limit GitHub.

## Auto router ringan dan 7 bahasa bawaan (ZEIBAEL)

Tambahan bahasa yang bisa digunakan pada standard GitHub-hosted runners: **PowerShell, Perl, Julia, Haskell, Fortran, R, Scala**. Daftar awal bersifat terbatas dan harus dibuktikan dengan uji nyata, bukan dianggap tersedia pada semua OS.

| Bahasa | Kompiler/interpreter | Runner pilihan ZEIBAEL |
|---|---|---|
| PowerShell | `pwsh` | `ubuntu-24.04` |
| Perl | `perl` | `ubuntu-24.04` |
| Julia | `julia` | `ubuntu-24.04` |
| Haskell | `runghc` (GHC) | `ubuntu-24.04` |
| Fortran | `gfortran` | `ubuntu-24.04` |
| R | Rscript (dari instalasi image) | `windows-2022` |
| Scala | sbt + Java 21 (compiler Scala dapat diunduh sbt via repositori publik) | `windows-2022` |

**Verifikasi end-to-end (25 Oktober 2026): [Run #40188271356 — SUCCESS](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40188271356).** Ketujuh job menjalankan program asli dan menghasilkan penanda `ZEIBAEL_POWERSHELL_OK`, `ZEIBAEL_PERL_OK`, `ZEIBAEL_JULIA_OK`, `ZEIBAEL_HASKELL_OK`, `ZEIBAEL_FORTRAN_OK`, `ZEIBAEL_R_OK`, dan `ZEIBAEL_SCALA_OK` dengan exit code 0; plan dan agregasi JSON juga sukses. [Quality & Security pada commit pengembangan](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40188225330) sukses, 64/64 tes regresi. Scala diuji menggunakan sbt di Windows dengan Java 21; dependensi Scala diunduh secara sementara dari repositori publik dan tidak membutuhkan account berbayar. Rscript menggunakan lokasi instalasi R yang disediakan Windows runner; tidak memerlukan instalasi tambahan.

**Pemilihan otomatis tanpa server baru:** manifest publik yang ditinjau boleh menggunakan `"language": "Julia"`, `"runtime": "auto"` dan `"runner": "auto"` (atau menghilangkan kedua field yang `auto`). `scripts/runtime_router.py` menormalkan alias bahasa menjadi runtime dan memilih runner yang memang masuk allowlist lokal ZEIBAEL. Pemilihan ini deterministik, dilakukan pada tahap `plan`, dan tidak menerima perintah tak tepercaya dari dispatcher. Jika bahasa tidak tersedia, planner **gagal jelas**; tidak memasang paket sendiri, tidak mengalihkan ke provider berbayar, dan tidak menjalankan shell command bebas. `ci/jobs/builtin_languages_smoke.json` adalah manifest uji 7 bahasa.

Grace tetap menentukan kebutuhan bahasa dari permintaan Bos dan menyiapkan manifest yang direview di repo publik. Router hanya memilih runtime+runner untuk bahasa yang sudah didukung; **ini bukan sistem yang membaca prompt alami langsung dari GitHub**. Untuk kombinasi OS lain gunakan runner eksplisit yang telah lolos pemeriksaan, bukan menebak. Batasan pemilihan merupakan **aturan ZEIBAEL**, bukan kuota GitHub.

## Standar penamaan runner ZEIBAEL

Untuk menghindari kebingungan, laporan Grace dan README menyebut **nama lengkap sistem operasi — arsitektur**, diikuti **label GitHub sebenarnya**. Semua tujuh runner sudah masuk allowlist; tabel ini tidak mengubah konfigurasi atau kapasitas runner.

| No. | Nama lengkap (untuk ditampilkan) | Label asli GitHub (untuk `runs-on`/manifest) |
|---|---|---|
| 1 | **Ubuntu Linux 24.04 — x64** | `ubuntu-24.04` |
| 2 | **Ubuntu Linux 24.04 — ARM64** | `ubuntu-24.04-arm` |
| 3 | **Microsoft Windows Server 2022 — x64** | `windows-2022` |
| 4 | **Microsoft Windows 11 — ARM64** | `windows-11-arm` |
| 5 | **Apple macOS 15 — Intel x64** | `macos-15-intel` |
| 6 | **Apple macOS 15 — Apple Silicon ARM64** | `macos-15` |
| 7 | **Ubuntu Linux Slim — x64 (container)** | `ubuntu-slim` |

**Pembedaan penting:** `runner` adalah label resmi di kolom kanan, sedangkan `id` seperti `linux_x64_1` pada manifest `capacity_20_probe.json` hanyalah **ID job pengujian lama** buatan ZEIBAEL, bukan nama atau label GitHub Runner. Riwayat run lama tetap memakai ID tersebut. Jangan mengubah nilai `runner` menjadi `linux_x64_1`; untuk job baru, pakai ID yang jelas mencerminkan Ubuntu/Windows/macOS dan selalu tampilkan label runner sebenarnya.

**Paralelisme saat ini:** maksimal 20 job dalam satu manifest, maksimal 20 dicoba paralel dalam satu run; batas GitHub Free 20 concurrent job untuk akun, dengan maksimal 5 macOS. Banyak run dapat berbagi slot; bukan 20 slot khusus per workflow. Tidak ada workflow-wide concurrency lock. **Timeout per job:** `short` (10 menit), `standard` (30 menit), `long` (120 menit), atau `extended` (330 menit), dengan batas internal perintah sedikit lebih singkat agar laporan sempat ditulis.

**Laporan:** setiap job menghasilkan `result.json` serta baris log `ZEIBAEL_RESULT_JSON=...`. Job `results` menggabungkan laporan menjadi `aggregate.json`, baris `ZEIBAEL_AGGREGATE_JSON=...`, dan GitHub Actions artifacts dengan retensi satu hari. Grace dapat membaca status/log/artifact metadata melalui GitHub Native Plugin dan menyimpan ringkasan yang sesuai di repository privat. Jangan mengirim data rahasia ke runner publik.

**Bukti integrasi:** [Run #40095281869](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40095281869) — 11 unit test Python lulus, Node berhasil, dua job matrix dan JSON gabungan. [Run #40095607051](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40095607051) — Go, Rust, Java, Docker berhasil (empat job, maksimal tiga sekaligus), serta JSON gabungan sukses. Kedua uji memakai dispatcher Hatchable yang sudah ada, tanpa mengubah konfigurasinya.

## Verifikasi end-to-end terbaru

| Kemampuan | Bukti |
|---|---|
| Build C/C++, Go, Rust, Java + 15 unit test | [Run #40096787388](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40096787388) |
| npm, Docker image, container, Docker Compose | [Run #40096861811](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40096861811) |
| Ubuntu Linux 24.04 — ARM64, Microsoft Windows Server 2022 — x64, Apple macOS 15 — Apple Silicon ARM64 | [Run #40097047606](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40097047606) |
| Negative test: job gagal harus membuat workflow dan laporan gagal | [Run #40097157009](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40097157009) — sengaja FAILURE (exit 19), perilaku benar |

**Regresi terakhir:** [16 unit test berhasil pada commit terbaru](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40097391339). Manifest negative test sementara telah dihapus setelah digunakan, sementara riwayat run dan bukti tetap tersimpan.

**Pelaporan fail-closed:** agregator mengecek jumlah laporan sesuai jumlah job yang direncanakan, mendeteksi ID job duplikat, dan mengembalikan status failure apabila ada job gagal atau laporan hilang. Laporan per-job dan aggregate JSON tetap dibuat pada kegagalan biasa; perubahan sebelum driver sempat membuat laporan masih dapat menyebabkan job failure tanpa report lengkap. Artifact hanya disimpan 1 hari.

### Output file opsional — hanya untuk job yang meminta

- Manifest pekerjaan publik yang direview boleh menambahkan `"output_files": true` pada sebuah job. Default-nya `false`, jadi **job biasa tidak menjalankan langkah upload file output**.
- Saat `true`, perintah job menulis file hasil ke folder `$ZEIBAEL_OUTPUT_DIR/files/` (di Python: `Path(os.environ["ZEIBAEL_OUTPUT_DIR"]) / "files"`). Folder tersebut adalah lokasi sementara terisolasi, bukan path arbitrary dari pengguna.
- Setelah perintah berhasil, driver memeriksa keberadaan file, **maksimal 100 file dan total 50 MB**, menolak hidden paths serta symlink. Jika output kosong atau tidak memenuhi batas, job gagal.
- File yang lolos diunggah sebagai `zeibael-output-<job_id>` di artifact GitHub Actions dengan retensi **1 hari**. `result.json` / `aggregate.json` tetap diproduksi seperti biasa.
- Data yang dikeluarkan harus **aman dipublikasikan**. Jangan mengunggah rahasia, data pelanggan, private source, atau kredensial. Pemeriksaan struktur/ukuran tidak bisa menjamin isi file bebas informasi sensitif.
- Tidak ada penambahan server, workflow, database, atau mekanisme pengarsipan permanen. Grace dapat membaca artifact yang masih berlaku dari run GitHub yang tepat.

Uji cepat: `ci/jobs/optional_output_demo.json`, job Python kecil yang menulis contoh teks publik. Untuk pekerjaan nyata, tulis hasil build ke folder `files/` yang sama dan aktifkan flag hanya jika file memang dibutuhkan.

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

_Dokumentasi diverifikasi 25 Oktober 2026. Grace bertanggung jawab memilih jalur eksekusi sesuai pekerjaan, bukan meminta Bos mengingat detail workflow._

## Reliability, capacity and security (October 2026)

- `ci.yml` no longer has a workflow-wide concurrency group. Independent CI runs can use available account-level standard-runner slots together; GitHub still applies Free-plan limits. The independent ZIP packaging workflow retains its own `queue: max`.
- Manifest cap is now 20 trusted jobs with `max-parallel: 20` (not unlimited). The execution time budget is **shared by all commands** in a manifest job.
- `job_ids` are propagated from the validated job plan to the result aggregator, preventing a mismatched but equal-size report collection from being treated as success. Each run is identified by GitHub run ID.
- GitHub-managed actions are pinned to full immutable SHA commits; `.github/workflows/quality.yml` checks Python regressions and CodeQL on main.
- Optional `platform_extensions` is a fixture-based smoke test for HTTP APIs, temporary SQLite, TypeScript and PWA source contract; not a claim of Playwright or real offline E2E.
- Public artifacts expire after 1 day. Grace can archive a public-safe summary to the private registry through the connected GitHub app **when actively asked**, not by granting the public runner private tokens or doing background work.
- These changes target the free standard runners on public repositories; no billing, private code checkout or external secret stores are used.

### Optional real-browser PWA E2E

`ci/jobs/playwright_browser_smoke.json` runs **opt-in** Chromium testing with a fixed Playwright 1.56.1 package version on a public standard runner. It checks click behavior and reload while browser networking is set offline after service-worker precaching. Browser installation occurs only during this explicitly dispatched job; it is not part of every CI run. The fixture is not a production app. No cloud secrets or private code are used. This job installs npm dependencies ephemerally without committing a lockfile; for an actual application, commit its package lock and replace this fixture with reproducible project tests.

### Profil kapasitas GitHub Free (20 slot)

- `ci/jobs/capacity_20_probe.json`: uji 20 job dengan tujuh label runner standard publik; dipicu hanya ketika Bos meminta audit, bukan pada setiap CI.
- Standard GitHub-hosted runners pada repository publik gratis, tetapi tunduk pada batas concurrency GitHub Free (20 total, maksimal 5 macOS), batas penggunaan yang wajar dan aturan GitHub Actions. Membuka tujuh runner **tidak** melipatgandakan slot concurrency menjadi 140.
- `ubuntu-slim` disetujui hanya untuk runtime Python `short` (10 menit) di ZEIBAEL; batas GitHub 15 menit serta keterbatasan container membuatnya tidak cocok untuk Docker dan build berat. Runner lain mengikuti timeouts standar.
- Setiap pekerjaan tetap memilih satu OS yang dibutuhkan; tidak otomatis menggandakan job di semua OS.
- Tidak ada workflow baru, billing/PAYG, deployment Hatchable atau akses privat ke runner publik.
