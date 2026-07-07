# Langkah 3.1 — Belief Revision / Knowledge Update (7 Jul 2026)

Menutup sisi **fitur** dari gerbang Langkah 5 kriteria #2 ("knowledge-update tidak lagi
gagal katastrofik"). Fakta yang saling bertentangan biasanya *tidak* cukup mirip untuk
masuk klaster `reflect`, sehingga tanpa penanganan eksplisit keduanya duduk berdampingan
dan `recall` menyajikan keyakinan usang bersama yang baru — reader tinggal menebak.

## Implementasi — [app/memory/revise.py](../app/memory/revise.py)

Berjalan di jalur tulis (`engine.remember`), setelah fakta baru ter-flush:

1. **Deteksi kandidat via pgvector (~0 kuota):** tiap fakta baru dicari lawannya di fakta
   `active` user yang sama dengan cosine similarity ≥ `revise_similarity`. **Kalibrasi
   text-embedding-v4:** pasangan "atribut sama, nilai baru" yang asli terukur ~0.55–0.70,
   fakta tak berhubungan ~0.35 → band dimulai di **0.50**. Recall kandidat hidup di band;
   presisi hidup di konfirmasi LLM.
2. **Konfirmasi SATU panggilan `chat_json` murah per batch** — hanya bila ada kandidat;
   `remember` ke namespace tanpa fakta serupa tidak memanggil LLM sama sekali. Pada korpus
   padat, pasangan diurutkan global berdasar similarity sebelum dipotong ke 20 (pasangan
   kontradiksi biasanya yang terdekat). Prompt konservatif: entitas beda TIDAK pernah
   disupersede; atribut komplementer TIDAK; penambahan preferensi TIDAK; ragu → TIDAK.
3. **Aksi:** `old.superseded_by = new.id`, `old.status = archived`. `recall` hanya
   menyajikan baris `active` → keyakinan usang langsung keluar dari konteks.

Knob: `revise_enabled`, `revise_similarity` ([app/config.py](../app/config.py)).

## Ukur 1 — sintetis, bentuk retrieval ([benchmark/update.py](../benchmark/update.py))

6 kasus update (employer, kota, nomor telepon, jadwal, advisor, preferensi) + 3 jebakan
yang TIDAK boleh disupersede (entitas-beda ala Mia/Leo, atribut-komplementer,
preferensi-aditif) + 6 distraktor. Fakta v1 di-seed langsung (deterministik, backdate
30 hari); update v2 lewat jalur tulis nyata `remember(cheap=True)`.

PASS per kasus = baris v1 `archived`+`superseded_by` terisi **dan** konteks recall memuat
nilai v2 **dan** tidak lagi memuat pernyataan v1 (level-pernyataan; plus probe kata untuk
nilai yang tak mungkin bocor ke v2, mis. nomor telepon lama).

**Hasil: 6/6 update PASS, 3/3 jebakan selamat, wrong-supersede = 0**
(`gate2_retrieval_form_pass = true`). Biaya: chat 5.868 tok / 17 panggilan (turbo),
embed 368 tok. Data: `benchmark/results/update.{jsonl,summary.json}`.

## Ukur 2 — delta LongMemEval knowledge-update, apel-ke-apel

Re-run **7 item knowledge-update yang persis sama** dengan baseline Langkah 2
(dataset oracle, reader+judge qwen-turbo, budget 1200, candidate_k 50; via flag baru
`--ids` di [benchmark/longmemeval.py](../benchmark/longmemeval.py)), kini dengan belief
revision aktif saat ingest.

| | akurasi knowledge-update (turbo reader) |
|---|---|
| Baseline Langkah 2 (tanpa revision) | 3/7 (42,9%) |
| Dengan belief revision | **3/7 (42,9%) — netto 0, komposisi berubah** |

Biaya: chat 61.572 tok / 34 panggilan. Retrieval hit-rate evidence **100% di kedua run**.
Data: `benchmark/results/ku_after_revision.{jsonl,summary.json}`.

**Bedah per item (temuan paling berharga dari run ini):**

| Item | Base→After | Diagnosis |
|---|---|---|
| ed4ddc30 (stok telur) | ✗→**✓** | **Kemenangan buku-teks**: baseline menjawab nilai usang "30 lusin"; dengan revision konteks hanya memuat "20 lusin" → benar. Mekanisme bekerja di data liar. |
| 07741c44 (sneakers) | ✓→**✗** | **Korban historis**: soalnya menanyakan nilai LAMA ("di mana *awalnya*…", gold "under my bed"). Revision mengarsipkan fakta lama itu — secara mekanis benar, tapi sejarahnya hilang dari konteks. |
| 6aeb4375 (jumlah restoran) | ✗→✗ | Tak pernah winnable (`hit_answer=false` di KEDUA run — jawaban "four" tak pernah ter-retrieve). n_memories 12→7 mengindikasikan revision ikut memangkas anggota daftar aditif — temuan kalibrasi. |
| 0977f2af (Instant Pot) | ✗→✗ | Fakta ADA di konteks kedua run (`hit_answer=true`); reader turbo tetap "I don't know" — murni lantai reader. |
| d7c942c3 (metode belanja ibu) | ✗→✗ | Reader ragu-ragu di kedua run — lantai reader. |
| 18bc8abd, e493bb7c | ✓→✓ | Stabil. |

**Interpretasi.** Soal knowledge-update ternyata terbelah dua rasa: **"berapa nilainya
SEKARANG"** (revision membantu — telur) vs **"berapa nilainya DULU"** (revision naif justru
merugikan — sneakers). Solusi lengkapnya bukan membatalkan revision, melainkan
melengkapinya dengan **Langkah 3.2**: recall sadar-waktu yang tetap menyajikan fakta
tersupersede *dengan tag usang* ("PAST: … → NOW: …"), sehingga soal nilai-kini dan
nilai-lampau sama-sama terjawab. Temuan ini adalah bukti empiris urutan peta-jalan
protokol (#belief-revision → #temporal-validity), bukan kegagalan revision.

Catatan jujur: delta diukur pada **reader turbo** — reader kuat tetap mustahil di free
tier (qwen-plus mati permanen); 3 dari 4 kegagalan tersisa adalah lantai reader/ekstraksi,
bukan retrieval (evidence hit-rate 100%).

## Regresi

- `benchmark/staleness.py` ulang: **gate #6 tetap PASS** (accessed 6/6 semua siklus,
  wrong-merge 0) dengan kode revise terpasang.
- Jalur nol-biaya terverifikasi: `remember` tanpa kandidat serupa = ekstraksi saja,
  tanpa panggilan revisi.
