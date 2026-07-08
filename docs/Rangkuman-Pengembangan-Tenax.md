# Rangkuman Pengembangan Tenax

Dokumen ini merangkum diskusi mengenai arah pengembangan **Tenax** — memory layer persisten untuk AI agent (hackathon Qwen Cloud, Track 1). Disusun sebagai acuan keputusan, dari analisis kondisi saat ini sampai keputusan strategis penambahan dimensi *grounded*.

---

## 1. Kondisi Tenax saat ini

Tenax adalah memory layer swakelola yang bisa dipasang ke agent MCP mana pun. Komponennya: MCP server + REST API (FastAPI), Qwen Cloud untuk ekstraksi (`qwen-plus`) dan embedding (`text-embedding-v4`), serta PostgreSQL + pgvector untuk penyimpanan.

Empat operasi inti:

- **`remember`** — ekstraksi fakta terdistilasi & self-contained dari input mentah (bukan menyimpan turn mentah).
- **`recall`** — hybrid retrieval (dense + full-text + recency + importance) dengan *budget-aware packing* ke dalam batas token.
- **`forget`** — decay ala Ebbinghaus yang mengarsipkan memori usang bernilai rendah.
- **`reflect`** — konsolidasi klaster near-duplicate menjadi fakta kanonik.

Arsitekturnya rapi dan pilihan desainnya sejalan dengan arah riset memory-agent 2026.

---

## 2. Potensi pengembangan inti memori

### 2.1 Penguatan teknis (quick wins)

- **Scoring pindah ke database.** Saat ini `retrieve.py` menarik kandidat lalu menghitung ulang cosine di Python (redundan karena pgvector sudah menghitungnya). Ganti dengan *Reciprocal Rank Fusion (RRF)* di SQL agar skalabel.
- **Klastering konsolidasi O(n²).** `_cluster` membangun matriks kemiripan penuh (dibatasi 300 baris) — akan pecah di skala nyata. Gunakan klaster berbasis DB atau algoritma inkremental.
- **Dedup saat tulis.** Tambahkan cek kemiripan tinggi (mis. cosine > 0.95) saat `remember` agar storage tidak membengkak sejak awal.
- **Tokenizer akurat.** Ganti proxy `cl100k_base` dengan tokenizer Qwen sebenarnya agar budgeting tepat.
- **Penjadwalan otomatis.** `forget` dan `reflect` masih manual; tambahkan background worker/cron agar benar-benar "self-managing".

### 2.2 Fitur yang benar-benar membedakan

- **Penanganan kontradiksi / knowledge update (paling penting).** Fakta yang saling bertentangan sering tidak cukup mirip untuk masuk klaster `reflect`, sehingga tersimpan berdampingan. Data lapangan menunjukkan akurasi produksi bisa jatuh ke ~49% setelah 30 hari akibat data usang + kontradiksi entitas. Tambahkan *belief revision* eksplisit (manfaatkan kolom `superseded_by` yang sudah ada).
- **Temporal reasoning / validity interval.** Bedakan *kapan fakta berlaku* dari *kapan direkam* (`valid_from`/`valid_until`). Ini kategori paling lemah di semua sistem, sekaligus sumber lonjakan performa terbesar.
- **Graph memory.** Ekstrak entitas + relasi ke knowledge graph untuk recall multi-hop yang tak terjangkau vektor datar (pendekatan graph dilaporkan unggul ~14,8 poin di LongMemEval untuk temporal reasoning).
- **Procedural memory.** Tipe `procedural` ada tapi masih "stretch" dan dikecualikan dari `reflect`; kembangkan jadi memori how-to / standing instruction yang benar-benar berguna.

### 2.3 Evaluasi & kredibilitas

Benchmark saat ini hanya satu dataset sintetis vs baseline recency. Bidang ini punya tolok ukur standar: **LoCoMo**, **LongMemEval**, dan **BEAM**. Menjalankan Tenax terhadap salah satunya (LongMemEval paling relevan karena menguji knowledge update & temporal) mengubah proyek dari prototipe jadi sesuatu yang angkanya bisa diklaim. Rasio dampak-terhadap-usaha paling tinggi.

### 2.4 Arah produk

Autentikasi & multi-tenancy (belum ada auth; scoping baru sebatas `user_id`), privasi & kepatuhan (plaintext, belum ada redaksi PII, hard delete untuk hak "dilupakan" GDPR belum diekspos), serta adaptor framework (LangChain/LlamaIndex/CrewAI) agar jadi memory backend siap-pakai.

### Tiga prioritas berdampak tertinggi

1. Penanganan kontradiksi / knowledge update
2. Menjalankan LongMemEval untuk angka nyata
3. Temporal validity

---

## 3. Perluasan multimodal (file/gambar → knowledge)

### Prinsip: pisahkan *ingestion* dari *memory*

- **Ingestion / ekstraksi** (file/foto → teks/info) adalah pipeline preprocessing.
- **Memory** (apa yang diingat, retrieval, forgetting) adalah tugas Tenax.

Karena Tenax lapisan "tengah" (MCP), ekstraksi tidak harus hidup di dalamnya — bisa langkah upstream atau tool MCP terpisah (`ingest`/`remember_file`). Engine memori tetap satu tanggung jawab.

### Soal "membuang source": simpan keduanya

Menyimpan teks hasil ekstraksi di vector DB itu efektif dan standar. Source tidak terbuang selama file asli disimpan di **object storage** dengan pointer/URI di kolom **`source`** (yang sudah ada). Retrieval jalan di atas teks; file asli diambil saat perlu (verifikasi / re-ekstraksi dengan model lebih baik).

### Kapan perlu multimodal embedding

Untuk query yang inherently visual (mis. "diagram mana yang menunjukkan X"), teks kehilangan informasi. Ekosistem Qwen mendukung ini: `qwen3-vl-plus`/`qwen3-vl-flash` untuk ekstraksi, dan seri **Qwen3-VL-Embedding** yang memetakan teks + gambar + video ke satu ruang terpadu (catatan: model open-source, kemungkinan perlu self-host — verifikasi ketersediaannya di DashScope).

### Caveat kunci: knowledge base ≠ agent memory

Mesin `forget`/decay dan `reflect` dirancang untuk fakta personal yang berevolusi. Jika potongan dokumen dituang mentah ke `remember`, decay akan mengarsipkan halaman yang jarang diakses dan konsolidasi akan menggabungkan fakta berbeda — merusak KB. **Kebijakan retensi harus dipisah.**

---

## 4. NotebookLM sebagai referensi

### Apa itu NotebookLM

Sistem RAG **source-grounded**: hanya menjawab dari sumber yang diunggah, setiap klaim diberi sitasi span ke paragraf asal. Filosofinya: **tidak pernah membuang source, tidak pernah melupakan.** Ini kebalikan dari Tenax yang mendistilasi (lossy) dan melupakan.

### Implikasi: ini percabangan, bukan sekadar penambahan

Di sumbu retensi, keduanya berlawanan:

| Aspek | Tenax (evolving) | NotebookLM (grounded) |
|---|---|---|
| Perlakuan input | Distilasi lossy | Sumber utuh |
| Waktu | Melupakan (decay) | Tidak melupakan |
| Verifikasi | Memori terdistilasi | Sitasi span |
| Optimal untuk | Memori personal, budget ketat | Auditability korpus |

NotebookLM sekaligus menjawab kekhawatiran "membuang source": desainnya adalah "jangan pernah buang".

### Di mana ia cocok jadi acuan

- **Cocok:** pipeline ingestion multimodal, dan terutama **provenance/sitasi span** (rantai chunk → source URI → offset). Ini fitur trust tertinggi yang belum dimiliki Tenax.
- **Tidak cocok ditiru:** filosofi forgetting/distilasi Tenax — justru itu yang **tidak** dimiliki NotebookLM dan jangan dibuang.

### Peluang & kompetisi

NotebookLM adalah produk konsumen tertutup, bukan infrastruktur MCP. Celahnya bukan "kloning", melainkan **versi open, self-hostable, MCP-native yang bisa dipasang ke agent mana pun — plus lapisan memori yang tidak dimiliki NotebookLM.** Jangan bersaing di kepolesan UX konsumen melawan Google.

---

## 5. Konsep dua lapisan: tetap SATU kesatuan

Keputusan: **satu sistem, satu interface, satu `recall`** — bukan dua produk. Perbedaan grounded vs evolving adalah **properti pada data, bukan arsitektur terpisah.**

### Kenapa satu kesatuan

- Berbagi infra yang sama: pgvector, embedding, skorer hybrid, interface MCP.
- Agent ingin **satu `recall`** yang menarik fakta personal *dan* potongan dokumen sekaligus, tanpa perlu tahu "tanya ke store yang mana". Retrieval terpadu + packing ke budget adalah inti nilainya.

### Bentuk di kode: satu dimensi baru

Tambahkan `mem_class` dengan dua nilai: `evolving` dan `grounded`.

**Yang bercabang:**
- `forget.sweep` dan `consolidate` diberi filter `mem_class == evolving` → korpus grounded tidak pernah dilupakan / digabung.
- Jalur tulis: fakta personal lewat `extract.py` (distilasi); dokumen lewat jalur `ingest` (chunk + object storage + pointer, tanpa distilasi).

**Yang tetap sama:** penyimpanan (tabel yang sama), embedding, dan fungsi `retrieve`.

### Saklar `scope` pada `recall`

- Default → tarik dari **keduanya**, skor bersama, epak ke budget (mode agent, ingatan mulus).
- `scope=grounded` → hanya korpus dokumen, sitasi span dipaksakan (mode NotebookLM, auditable).
- `scope=<namespace>` → batasi ke satu notebook/proyek.

### Tension yang perlu disetel

Chunk dokumen lebih panjang dan importance-nya bermakna beda dari fakta personal. Beri importance default netral untuk chunk grounded dan andalkan skor semantik + keyword, agar tidak saling menenggelamkan. Ini penyetelan, bukan perombakan.

---

## 6. Analisis nilai: naik atau turun?

Dimensi grounded adalah **pengali**, bukan sekadar tambahan — ia melipatgandakan kondisi inti Tenax saat ini.

### Kenapa bisa naik

- Cakupan use-case melebar drastis (asisten nyata butuh keduanya sekaligus).
- Diferensiasi langka: kombinasi memori evolutif + grounded dalam satu recall tidak dimiliki Mem0/Zep maupun NotebookLM → potensi moat.
- Kepercayaan naik: sitasi span menambal kelemahan recall lossy & staleness.
- Biaya marginal rendah (memakai ulang infra yang ada).

### Kenapa bisa turun

- **Identitas kabur:** pitch satu kalimat jadi rumit → nilai persepsi turun.
- **Luas eksekusi membengkak:** usaha tersedot ke ingestion, bukan ke pendalaman inti (kontradiksi, temporal, benchmark). Dua bagian setengah jadi < satu inti yang unggul.
- **Provabilitas menurun:** sistem hibrida tidak memetakan bersih ke benchmark memori maupun RAG.
- **Risiko degradasi retrieval:** grounded yang integrasinya buruk bisa membuat recall memori *lebih jelek*.

### Dua variabel penentu

1. **Urutan (sequencing).** Inti memori adalah fondasi; grounded bergantung padanya, bukan sebaliknya. Tambah grounded **sebelum** inti solid & ter-benchmark → nilai **turun**. Tambah **setelah** inti terbukti → nilai **naik**.
2. **Framing.** Posisikan grounded sebagai **pelayan keterpercayaan memori** ("memori yang bisa dipercaya karena tertelusur ke sumber"), bukan "Tenax juga jadi NotebookLM". Framing ini menjaga fokus konsep Tenax tetap utuh.

### Kesimpulan nilai

**Neto lebih tinggi, dengan syarat:** (1) kuatkan & benchmark inti memori lebih dulu, dan (2) bingkai grounded sebagai penopang keterpercayaan, bukan produk kedua. Jika grounded ditambahkan sekarang sementara kontradiksi/temporal/benchmark masih terbuka, nilainya justru **turun sementara** — lebih baik ditahan dulu.

Pertanyaan sebenarnya bukan "grounded menaikkan nilai atau tidak", melainkan **"apakah inti memoriku sudah cukup kuat untuk layak diperluas".**

---

## 7. Peta jalan yang disarankan

1. **Fase 1 — Perkuat inti:** kontradiksi/knowledge-update, temporal validity, quick wins teknis (RRF, dedup, tokenizer, scheduler).
2. **Fase 2 — Buktikan:** jalankan LongMemEval, dapatkan angka nyata.
3. **Fase 3 — Perluas dengan aman:** tambahkan `mem_class` + jalur `ingest` + `scope`, dengan grounded dibingkai sebagai lapisan keterpercayaan di atas inti yang sudah proven.
