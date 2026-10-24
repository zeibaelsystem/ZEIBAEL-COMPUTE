# ZEIBAEL COMPUTE

**Repository publik untuk CI/build sementara ZEIBAEL · GitHub Actions · FREE-ONLY**

Repository ini menyediakan runner GitHub-hosted untuk **validasi kode, pengujian, packaging ZIP, dan skrip pengembangan yang aman dijalankan secara publik**. Data dan konfigurasi utama ZEIBAEL tetap berada di repository privat `ZEIBAEL-SYSTEM`; kode privat **tidak otomatis dipindahkan** ke runner ini.

## Alur eksekusi

```text
Bos meminta pekerjaan
        |
        v
Grace memilih GitHub Native Plugin untuk pekerjaan file biasa
        |
        +-- Jika perlu runner --> GitHub Actions di ZEIBAEL-COMPUTE
                                   ^
                                   |
                          Hatchable sebagai dispatcher
                      (hanya jika plugin tak bisa dispatch)
                                   |
                                   v
                        Grace baca hasil lewat GitHub Plugin
                                   |
                                   v
                        Grace simpan hasil yang sesuai
                        ke ZEIBAEL-SYSTEM (private)
```

Hatchable **bukan** mesin build; fungsinya mengirim permintaan `workflow_dispatch` ke GitHub. Owner juga bisa memicu workflow secara manual dari tab **Actions**. Tidak diperlukan secret baru untuk jalur CI publik yang berlaku sekarang.

## Workflow yang tersedia

| Workflow | Lokasi | Input | Hasil |
|---|---|---|---|
| **Modular Public CI** | [`ci.yml`](.github/workflows/ci.yml) | `task`, opsional `script_id` | Status, log, dan ZIP satu hari untuk `package` |
| **Package ZIP** | [`artifact.yml`](.github/workflows/artifact.yml) | `target`, opsional `skill_name` | ZIP artifact satu hari |

Pilihan `task` dalam `ci.yml`:

| Task | Kegunaan | Syarat |
|---|---|---|
| `validate` | Periksa sintaks Python, JSON, dan Bash | File sumber publik tersedia |
| `python_tests` | Jalankan Python `unittest` | Folder `tests/` |
| `node_tests` | Jalankan `npm test` | `package.json` dengan skrip `test`; perlu dependensi yang sesuai |
| `package` | Buat ZIP sumber publik | File publik tersedia |
| `script` | Jalankan skrip CI yang sudah direview | `ci/jobs/<script_id>.py` atau `.sh` |

**Kondisi saat dokumentasi ini dibuat:** `tests/` tersedia dan pengujian Python berhasil. Belum ada `package.json`, folder `ci/jobs/`, atau folder `skills/`; akibatnya `node_tests`, `script`, dan opsi `artifact target=skill` **belum dapat dipakai sampai berkas yang diperlukan ditambahkan**. Packaging `target=project` sudah berhasil diuji.

## Menjalankan workflow

**Dari Grace:** bila perlu runner, Grace memilih workflow dan meminta Hatchable menjalankannya melalui endpoint **admin-only** `POST /api/github-dispatch` pada proyek ZEIBAEL SYSTEM. Setelah itu Grace menggunakan GitHub Native Plugin untuk membaca status dan log, lalu menyimpan hasil yang diperlukan di repository privat.

Contoh parameter dispatcher (bukan URL publik):

```json
{"workflow":"ci","task":"python_tests"}
```

```json
{"workflow":"ci","task":"script","script_id":"nama_job"}
```

```json
{"workflow":"artifact","target":"project"}
```

**Secara manual:** buka tab [Actions](../../actions), pilih **ZEIBAEL - Modular Public CI** atau **ZEIBAEL - Package ZIP**, kemudian **Run workflow**. Hanya pengguna dengan izin yang sesuai bisa menjalankannya.

## Struktur repository

```text
.github/workflows/
  ci.yml                 # Validasi, unit test, skrip CI, dan packaging
  artifact.yml           # ZIP project atau skill publik yang tersedia
scripts/
  ci_driver.py           # Mesin pelaksana tugas CI
tests/
  test_ci_driver.py      # Unit test untuk CI driver
README.md                # Dokumentasi ini
```

## Keamanan dan batasan

- **PUBLIC berarti publik:** source, workflow, log, dan artifact dapat terlihat orang lain. **Jangan** menaruh token, file privat, data pribadi, atau hasil sensitif di sini.
- Runner hanya checkout **repository publik**. Ia **tidak mempunyai akses otomatis** ke `ZEIBAEL-SYSTEM`; tidak ada PAT privat atau signing secret tambahan pada jalur utama.
- Pengujian dan build mengikuti batas waktu job, konkurensi, penyimpanan, serta kebijakan penggunaan GitHub Actions. **Tidak berarti cloud compute tanpa batas atau boleh dipakai untuk semua jenis beban kerja.**
- ZIP yang diunggah sebagai Actions artifact menggunakan **retensi satu hari**. Jangan gunakan sebagai penyimpanan permanen.
- Skrip baru ditambahkan melalui GitHub Native Plugin, direview dahulu, dan tidak boleh mengeluarkan rahasia ke log.
- **FREE-ONLY:** jangan aktifkan billing atau sumber daya berbayar.

## Verifikasi

- [Unit test CI publik — berhasil, 5/5](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40048674561)
- [Packaging ZIP — berhasil](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/40048678563)

**Status dokumentasi:** 24 Oktober 2026. Workflow yang aktif adalah `ci.yml` dan `artifact.yml`; workflow duplikat lama sudah dihentikan.
