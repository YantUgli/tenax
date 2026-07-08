# Langkah 2 — Hasil Baseline LongMemEval (7 Jul 2026)

Baris pertama tabel riwayat untuk Langkah 3. Semua run free-tier DashScope. Data mentah:
`benchmark/results/{probe_retrieval,baseline_oracle,baseline_recency}.{jsonl,summary.json}`.

## Ringkasan

| Run | Dataset | Model (extract/reader/judge) | N | Metrik utama |
|---|---|---|---|---|
| Tahap 1 — probe retrieval | `_s` capped-15 | qwen-plus | 16 skor | **retrieval hit-rate 87.5%** |
| Tahap 2a — Tenax hybrid | `oracle` | qwen-turbo | 50 | **akurasi 42.0%**, hit-rate 100% |
| Tahap 2b — naif recency | `oracle` | qwen-turbo | 50 | akurasi 48.0% |

> Model beda antar-run (qwen-plus habis kuota di tengah Tahap 1 → Tahap 2 pindah qwen-turbo).
> Tiap run konsisten-internal; embedding `text-embedding-v4` sama di semua run. Angka
> **direksional** (N kecil, oracle + probe), bukan LongMemEval kanonik.

## Per-kategori (akurasi, oracle, qwen-turbo)

| Kategori | n | Tenax hybrid (2a) | Naif recency (2b) | Retrieval hit (Tahap 1, `_s`) |
|---|---|---|---|---|
| abstention | 3 | 100.0% | 100.0% | R+ |
| single-session-user | 6 | 83.3% | 83.3% | R+ |
| single-session-assistant | 6 | 66.7% | 66.7% | **R- (2/2 miss)** |
| knowledge-update | 7 | 42.9% | 57.1% | R+ |
| multi-session | 12 | 33.3% | 33.3% | R+ |
| temporal-reasoning | 13 | 15.4% | 23.1% | R+ |
| single-session-preference | 3 | 0.0% | 33.3% | R+ |

## Temuan

1. **Inti memori (retrieval) sehat.** Di haystack nyata berdistraktor (`_s`): **87.5%** gold
   evidence tertarik. Di oracle: 100%. Kegagalan akurasi = **reasoning/reader**, bukan memori.
2. **Titik lemah retrieval:** `single-session-assistant` (2/2 miss di Tahap 1) — fakta yang
   **diucapkan asisten** kurang tertarik. Kandidat perbaikan #1 Langkah 3.
3. **Oracle TIDAK bisa membuktikan kriteria #1 (hybrid > naif):** tanpa distraktor, recency
   menarik set memori yang sama → hybrid tak memberi lift, malah sedikit tertinggal
   (ordering relevansi menyakiti reader lemah pada knowledge-update yang butuh fakta terbaru).
   **Nilai hybrid = menolak distraktor**, hanya terukur di `_s` (atau uji sintetis
   `benchmark/run.py`), bukan oracle.
4. **temporal-reasoning terlemah (15%)** — kombinasi reasoning tanggal + reader qwen-turbo
   (lebih lemah dari plus). Baseline ini adalah **lantai**; qwen-plus akan lebih tinggi.
5. **abstention 100%** — Tenax benar berkata "tidak tahu" saat jawaban tak ada.

## Kuota terpakai (free tier, ~1M/model)

| Model | Peran | Chat token | Embed token | Status |
|---|---|---|---|---|
| qwen-plus | Tahap 1 extract/recall | 687,837 | — | **HABIS** (403 FreeTierOnly di item 18) |
| qwen-turbo | Tahap 2a+2b all-roles | 387,152 | — | ~613k sisa |
| text-embedding-v4 | embed semua run | — | 43,628 | ~956k sisa (nyaris penuh) |

Catatan: estimasi embed (656k) jauh di atas realita (44k) — fakta hasil ekstraksi jauh lebih
pendek dari sesi mentah. Estimator sengaja konservatif.

## Implikasi untuk gerbang Langkah 5
- **#4 retrieval** → inti memori terbukti bekerja (87.5% berdistraktor) → **layak diperkuat/diperluas**.
- **#1 hybrid vs naif** → belum terbukti di free-tier oracle; perlu run reader di `_s`
  berdistraktor atau andalkan uji sintetis `benchmark/run.py`.
- Prioritas Langkah 3: (a) retrieval `single-session-assistant`; (b) evaluasi ulang akurasi
  pada model lebih kuat bila kuota memungkinkan; (c) demonstrasi #1 di haystack berdistraktor.
