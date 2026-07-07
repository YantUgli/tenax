# Fase Perkuat & Buktikan Inti — Protokol Benchmark & Gerbang Keputusan Grounded

Dokumen ini menjabarkan langkah demi langkah untuk (a) memperkuat inti memori Mnemo dan (b) mem-benchmark-nya secara terukur, sehingga hasil benchmark menjadi dasar objektif untuk keputusan: **"garap dimensi grounded atau tahan dulu".**

## Prinsip pemandu: ukur → perbaiki → ukur lagi

Jangan memperbaiki lebih dulu. Ambil **baseline** dari kondisi Mnemo sekarang, baru perbaiki bagian terlemah, lalu ukur ulang untuk melihat *delta*. Tanpa baseline, kamu tidak bisa membuktikan sebuah perbaikan benar-benar menaikkan angka — dan tidak bisa memakai angka itu sebagai gerbang keputusan.

Alurnya: `Baseline → Diagnosis → Perbaikan bertarget → Re-benchmark → Gerbang keputusan`.

---

## Langkah 0 — Prasyarat kode (agar benchmark valid)

Beberapa hal harus ada sebelum benchmark bisa dipercaya. Ini bukan "perbaikan fitur", melainkan syarat agar pengukuran sahih.

1. **`remember` harus menerima timestamp event.** Saat ini `Memory.created_at` default ke `now()`. Benchmark long-term memory menyuapkan riwayat multi-sesi dengan tanggal berbeda; jika semua memori bertanggal "sekarang", temporal reasoning tidak bisa diukur. Tambahkan parameter opsional `event_time` pada `remember`/`extract` yang mengisi `created_at` dan `last_accessed`.
2. **Isolasi per soal (namespace/reset).** Setiap pertanyaan benchmark punya "haystack" riwayatnya sendiri. Gunakan `user_id` unik per soal (mis. `bench:{item_id}`) dan pastikan bisa di-reset bersih, agar memori antar-soal tidak bocor.
3. **Instrumentasi metrik retrieval.** `recall` sudah mengembalikan `memories` dan `context`. Tambahkan kemampuan mencatat, untuk tiap soal, apakah fakta emas (gold) muncul di `context` — ini memisahkan kegagalan *memori* dari kegagalan *reader* (lihat Langkah 2).

---

## Langkah 1 — Bangun harness benchmark

Target utama: **LongMemEval** (500 soal, riwayat multi-sesi; varian -S berukuran ~115k token per soal). Ia paling relevan karena secara eksplisit menguji *knowledge update* dan *temporal reasoning* — dua titik lemah inti yang jadi fokus perbaikan. LoCoMo bisa jadi pelengkap.

Struktur harness (satu skrip, mis. `benchmark/longmemeval.py`):

1. **Muat dataset.** Ambil LongMemEval (GitHub/HuggingFace). Tiap item berisi: pertanyaan, tipe pertanyaan (kategori), jawaban emas, tanggal pertanyaan, dan haystack multi-sesi dengan timestamp per sesi.
2. **Fase tulis (ingest).** Untuk tiap item: pakai `user_id` unik, lalu iterasi sesi secara kronologis dan panggil `engine.remember(user_id, turn_text, source=session_id, event_time=session_time)` per turn/sesi. Timestamp wajib diteruskan (lihat Langkah 0).
3. **Fase baca (recall).** Panggil `engine.recall(user_id, question, token_budget=B)` → dapatkan `context`.
4. **Reader.** Beri `context` + pertanyaan ke satu LLM (Qwen) dengan instruksi menjawab **hanya** dari konteks. Ini memisahkan peran memori dari peran penalaran.
5. **Judge.** Bandingkan jawaban model vs jawaban emas dengan LLM-as-judge (pakai prompt evaluasi bawaan LongMemEval bila ada) → benar/salah per soal.
6. **Catat metrik** (lihat Langkah 2).

**Smoke test cepat:** benchmark sintetismu yang sudah ada (`benchmark/run.py`) tetap berguna sebagai uji-asap harian yang murah, sebelum menjalankan LongMemEval penuh yang lebih mahal.

---

## Langkah 2 — Ukur baseline (kondisi Mnemo sekarang)

Jalankan harness pada Mnemo apa adanya. Catat **empat kelompok metrik** — ini yang nanti jadi bahan gerbang keputusan:

1. **Akurasi keseluruhan** (end-to-end QA). Konteks: sistem terdepan 2026 berada di kisaran ~92–94% LongMemEval. Angka Mnemo kemungkinan jauh di bawah itu di awal — itu wajar; yang penting posisi relatifnya dan tren perbaikannya.
2. **Akurasi per kategori.** LongMemEval memisahkan: single-session-user, single-session-assistant, single-session-preference, multi-session, **temporal-reasoning**, **knowledge-update**, dan **abstention**. Dua yang ditebalkan adalah diagnostik utama "inti rusak atau tidak".
3. **Retrieval hit-rate.** Dari berapa persen soal, `context` benar-benar memuat fakta emas. Ini memisahkan kegagalan memori (fakta tak terambil) dari kegagalan reader (fakta ada tapi salah dijawab). Krusial: kalau failure ada di retrieval, itu masalah inti memori dan **harus** dibereskan sebelum grounded.
4. **Efisiensi token.** Rata-rata token per query. Selalu pasangkan akurasi dengan biayanya — angka akurasi tanpa biaya menyesatkan.

Sebagai pembanding, jalankan juga baseline naif: recency-only (sudah ada di `benchmark/run.py`) dan/atau full-context. Mnemo harus mengungguli keduanya dengan selisih jelas — kalau tidak, nilai tambah retrieval-nya belum terbukti.

---

## Langkah 3 — Perbaikan bertarget (dipandu baseline)

Perbaiki sesuai kategori terlemah dari Langkah 2, bukan sesuai tebakan. Urutan berdasarkan dampak:

1. **Knowledge-update lemah → implementasi belief revision.** Deteksi fakta yang saling meniadakan, tandai yang lama via `superseded_by`. Ini penyebab utama akurasi jatuh oleh kontradiksi.
2. **Temporal-reasoning lemah → validity interval.** Tambahkan `valid_from`/`valid_until`; buat `recall` sadar-waktu terhadap `question_date`.
3. **Retrieval hit-rate rendah → quick wins retrieval.** RRF di SQL, penyetelan bobot skorer, dedup saat tulis.
4. **Abstention lemah → ambang kepercayaan recall.** Sistem harus bisa mengatakan "tidak tahu" saat fakta memang tak ada di memori.

**Setelah tiap perbaikan, jalankan ulang benchmark** dan catat delta per kategori. Simpan tabel riwayat (baseline → +belief revision → +temporal → …) agar setiap perubahan terbukti berkontribusi. Ini juga yang membuat proyekmu bisa mengklaim angka secara kredibel.

---

## Langkah 4 — Uji ketahanan staleness (khusus memori swakelola)

Benchmark standar tidak menguji apakah mesin `forget`/`reflect`-mu *merusak* memori seiring waktu. Buat uji ini sendiri dengan memperluas harness sintetismu:

1. Seed fakta penting + distraktor (sudah ada).
2. Simulasikan berjalannya waktu dan jalankan `forget()` serta `reflect()` secara periodik.
3. Ukur apakah fakta penting **selamat** (masih ter-recall) setelah beberapa siklus, dan apakah konsolidasi tidak menggabungkan fakta berbeda secara keliru.

Kegagalan di sini berarti swakelolamu justru liabilitas — dan itu harus dibereskan sebelum grounded, karena grounded akan berbagi infrastruktur yang sama.

---

## Langkah 5 — Gerbang keputusan: garap grounded atau tahan?

Setelah siklus perbaikan-dan-ukur stabil, terapkan gerbang berikut. **Garap grounded hanya jika SEMUA terpenuhi.** Angka floor di bawah adalah titik kalibrasi yang bisa kamu sesuaikan, bukan hukum mati — yang penting logikanya.

| # | Kriteria | Floor yang disarankan | Kenapa penting |
|---|---|---|---|
| 1 | Akurasi keseluruhan | Mengungguli baseline recency/full-context dengan selisih jelas, dan berada di jalur menuju band kredibel (SOTA ~92–94% sebagai acuan gap) | Inti harus terbukti berfungsi, bukan sekadar berjalan |
| 2 | **Knowledge-update** | Tidak lagi gagal katastrofik (mis. ≥ ~60% atau naik tajam dari baseline) | Ini tes langsung penanganan kontradiksi; kalau masih jeblok, inti belum siap |
| 3 | **Temporal-reasoning** | Naik signifikan dari baseline | Kategori paling lemah universal; sinyal validity interval bekerja |
| 4 | **Retrieval hit-rate** | ≥ ~85–90% | Memastikan kegagalan sisa ada di reader, bukan di memori. Ini syarat paling menentukan: grounded bergantung pada retrieval yang sudah baik |
| 5 | Abstention | Berfungsi (menolak menjawab saat fakta tak ada) | Grounded soal keterpercayaan; fondasinya adalah tahu kapan tidak tahu |
| 6 | Ketahanan staleness | Fakta penting selamat setelah siklus forget/reflect | Swakelola tidak boleh merusak diri sendiri |

**Interpretasi:**

- **Semua lolos →** inti sudah "siap-diperluas". Grounded menjadi *pendalaman* yang memperkuat, dan nilai neto naik. Lanjut ke fase penambahan `mem_class` + `ingest` + `scope`.
- **Kriteria 4 gagal (retrieval hit-rate rendah) →** ini pemblokir mutlak. Grounded akan mewarisi retrieval yang lemah. **Tahan grounded**, benahi retrieval dulu.
- **Kriteria 2 atau 3 gagal →** inti belum menjawab kontradiksi/temporal. Menambah grounded sekarang hanya melebarkan fondasi rapuh dan menurunkan nilai untuk sementara. **Tahan.**
- **Kriteria 5 atau 6 gagal →** benahi lebih dulu; keduanya murah relatif terhadap risiko yang ditimbulkannya pada lapisan grounded.

---

## Ringkasan alur

```
Langkah 0  Prasyarat kode (timestamp, isolasi, instrumentasi)
Langkah 1  Bangun harness LongMemEval (+ smoke test sintetis)
Langkah 2  Ukur BASELINE  → 4 metrik: akurasi total, per-kategori, retrieval-hit, token
Langkah 3  Perbaiki terlemah → belief revision → temporal → retrieval → abstention
           (re-benchmark & catat delta setiap kali)
Langkah 4  Uji ketahanan staleness (forget/reflect tidak merusak)
Langkah 5  GERBANG KEPUTUSAN (6 kriteria)
              ├─ semua lolos → GARAP grounded
              └─ ada yang gagal → TAHAN, benahi kriteria itu dulu
```

Inti pesannya: gerbang di Langkah 5 mengubah pertanyaan subjektif "grounded ini bagus atau tidak" menjadi keputusan berbasis bukti "apakah inti memoriku sudah melewati ambang yang membuat perluasan layak". Retrieval hit-rate (kriteria 4) adalah penentu paling tegas, karena grounded dibangun di atas retrieval yang sama.
