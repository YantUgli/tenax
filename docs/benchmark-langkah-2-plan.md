# Langkah 2 — Rencana Baseline LongMemEval (Free-Tier DashScope)

> Dokumen eksekusi mandiri. Status: Langkah 0 & 1 SELESAI. **Perubahan harness bagian 3
> SUDAH DIIMPLEMENTASIKAN & terverifikasi (compile + dry-run + estimate, tanpa API).**
> **Tahap 0 (estimasi) sudah dijalankan & LOLOS** (angka di bawah). Yang tersisa =
> Tahap 1 & Tahap 2 (memakai kuota API) — **kamu yang menjalankan**.

## 0. Hasil estimasi Tahap 0 (terukur, tanpa API — 2026-07-07)
| Run | Perintah inti | chat (LLM) | embed | Muat <1M? |
|---|---|---|---|---|
| Probe retrieval (Tahap 1) | `_s --sample 20 --max-sessions-per-item 15 --retrieval-only` | 841.699 | 655.834 | ✅ |
| Baseline oracle (Tahap 2) | `oracle --sample 80` | 698.614 | 456.408 | ✅ |
| Baseline recency (Tahap 2) | `oracle --sample 80 --baseline recency --skip-ingest` | +136.770 | +0 | ✅ |

Estimasi bersifat konservatif (over-estimate). Tahap 2 oracle + recency berurutan pada satu
model chat = ~836k < 1M. Verifikasi ulang dengan `--estimate` sebelum tiap run.

## 1. Konteks & batasan mengikat
- Baseline penuh 500 soal `longmemeval_s` = **~58 juta token & ~25.500 panggilan** →
  **mustahil** di free tier.
- Free tier DashScope: **121 model LLM + 5 model embed, masing-masing kuota ~1M token**.
- Anggaran efektif = **~1M token LLM + ~1M token embed**, karena:
  - **Embedding wajib SATU model** (ruang vektor antar-model tak kompatibel → retrieval rusak).
  - Ekstraksi/reader/judge SATU model demi validitas benchmark.
- **Full `_s` DILARANG:** ~103k token/soal → **10 soal saja = 1,03M > 1M** (pasti kena limit).
  Praktis ≤9 soal → tak layak. **Tidak dipakai.**

### Angka terukur (read-only, sampel `_s`)
| Strategi ingest | Token/soal | Muat / 1M token LLM |
|---|---|---|
| Full `_s` | ~103k | ~10 ❌ (dilarang) |
| Capped-15 `_s` (bukti + ≤15 sesi) | ~32k | ~31 (untuk probe retrieval) |
| Oracle-style (~1,9 sesi bukti) | ~5,5k | ~181 (untuk akurasi/reasoning) |

Reader+judge murah (~2k token/soal) → muat di satu model tetap.

## 2. Prinsip
Pisahkan dua metrik ke dua pool kuota, dan **jangan rotasi peran sensitif**:
- **Reasoning/akurasi** (#1,#2,#3,#5) → reader+judge → pool LLM, varian **oracle** (kecil → banyak soal muat).
- **Retrieval hit-rate** (#4, penentu) → butuh distraktor → subsampel **capped-`_s`**, mode **retrieval-only**.
- Ukuran run **selalu < 1M**, dikonfirmasi `--estimate` sebelum jalan.

## 3. Perubahan harness (prasyarat — implementasikan dulu)
### `benchmark/longmemeval.py`
1. **`--sample N`** berstrata (proporsional 7 kategori, seed) — WAJIB karena file terkelompok per kategori (`--limit` bias). Reuse `category_of()`.
2. **`--shuffle`** — acak urutan item (seed) → dekorelasi dari kategori (syarat bila rotasi).
3. **`--max-sessions-per-item K`** — simpan semua sesi bukti (`answer_session_ids`) + isi hingga K sesi, urut kronologis untuk `event_time`. Batasi token/soal. Sentuh `iter_sessions()`/`ingest_item()`.
4. **`--estimate`** — read-only: proyeksi token **chat & embed terpisah** vs 1M + jumlah panggilan, per konfigurasi. Reuse `count_tokens` (`app/memory/retrieve.py`); pola seperti `--dry-run`.
5. **`--skip-ingest`** — pakai ulang bench user (+`--keep-users` yang ada) → iterasi eval murah.
6. *(Opsional)* **`--raw-ingest`** — simpan sesi mentah + embedding, lewati ekstraksi → geser biaya ke pool embed. Bukan jalur tulis asli Tenax (sadar trade-off).

### `app/qwen_client.py`
7. **Pelacak kuota** — akumulasi `resp.usage` (prompt/completion) terpisah chat vs embed; method `usage()`. Harness cetak pemakaian + peringatan mendekati 1M.
8. **Berhenti-anggun (selalu aktif)** — deteksi error quota-exceeded/rate → checkpoint & stop bersih (JSONL sudah inkremental → kerja tak hilang), bukan crash.
9. *(Opt-in, default OFF)* **`--rotate-models`** — saat quota-exceeded, maju ke model berikut dari pool kecil kurasi setara. **Hanya EKSTRAKSI**, **wajib `--shuffle`**. Reader/judge/embedding **SELALU satu model tetap**. Hasil diberi label "validitas lebih rendah". Hanya untuk memperbesar probe retrieval-only.

Tidak ada perubahan `app/memory/*` (hook Langkah 0 sudah cukup). Oracle (~15MB) skema JSON sama.

## 4. Kebijakan rotasi model (jawaban atas risiko akurasi)
| Peran | Rotasi? | Alasan |
|---|---|---|
| Embedding | ❌ Jangan | Ruang vektor beda-model tak kompatibel → retrieval rusak total |
| Reader | ❌ Jangan | Kualitas reader = akurasi yang diukur; rotasi = akurasi jadi campuran model |
| Judge | ❌ Jangan | Judge harus konsisten; judge lemah salah-menilai |
| Ekstraksi | ⚠️ Hanya dengan `--shuffle` | File terkelompok per kategori → rotasi sekuensial = bias per-kategori; shuffle ubah jadi noise |

Default = **tanpa rotasi**, run dikecilkan <1M. Rotasi = escape hatch opt-in untuk probe retrieval-only saja.

## 5. Runbook bertahap (granularity `session`; reader/judge/embed = satu model tetap)
> Prasyarat: stack DB up, `QWEN_API_KEY` set, harness sudah dimodifikasi (bagian 3).

```bash
# Unduh oracle (sekali)
wget -O data/longmemeval_oracle.json \
  https://huggingface.co/datasets/xiaowu0162/longmemeval/resolve/main/longmemeval_oracle

# Tahap 0 — pra-estimasi biaya (GRATIS, tanpa API). Pastikan chat & embed < 1M.
pipenv run python -m benchmark.longmemeval --dataset data/longmemeval_s.json \
  --sample 20 --max-sessions-per-item 15 --retrieval-only --estimate
pipenv run python -m benchmark.longmemeval --dataset data/longmemeval_oracle.json \
  --sample 80 --estimate

# Tahap 1 — Probe retrieval (#4). ~640k token. Haystack nyata (terbatas → optimistik).
pipenv run python -m benchmark.longmemeval --dataset data/longmemeval_s.json \
  --sample 20 --max-sessions-per-item 15 --retrieval-only --keep-users \
  --out benchmark/results/probe_retrieval.jsonl

# Tahap 2 — Baseline reasoning (#1/#2/#3/#5) pada oracle. ~590k token.
pipenv run python -m benchmark.longmemeval --dataset data/longmemeval_oracle.json \
  --sample 80 --out benchmark/results/baseline_oracle.jsonl
# lalu baseline naif (pembanding #1) pada item yang sama:
pipenv run python -m benchmark.longmemeval --dataset data/longmemeval_oracle.json \
  --sample 80 --baseline recency --skip-ingest --keep-users \
  --out benchmark/results/baseline_recency.jsonl
```
Hasil (JSONL + `summary.json`) di `benchmark/results/` = baris pertama tabel riwayat Langkah 3.
Naikkan `--sample` bertahap hanya setelah `--estimate` mengonfirmasi masih < 1M.

## 6. Metrik → gerbang (cakupan free tier)
- **#1** akurasi vs naif → ✅ (oracle + recency).
- **#2/#3/#5** knowledge-update / temporal / abstention → ✅ (oracle per-kategori).
- **#4** retrieval hit-rate → ⚠️ **proxy** (capped-`_s`, optimistik, N kecil → sinyal, bukan angka final; catat sebagai keterbatasan).
- Efisiensi token → ✅ (`tokens_used`).

## 7. Verifikasi
1. `--estimate` → token chat & embed < 1M tiap konfigurasi (tanpa API).
2. `--sample 21 --dry-run` → ~3 soal/kategori (bukan satu kategori).
3. `--max-sessions-per-item 15` → sesi ter-ingest ≤15 & semua sesi bukti hadir.
4. Tahap 1 → `summary.json`: `retrieval_hit_rate` terisi, `overall_accuracy=null`.
5. Tahap 2 → akurasi & per-kategori terisi; `--skip-ingest` tak ekstraksi ulang.
6. `usage()` < 1M tiap run; simulasi error kuota → berhenti-anggun + checkpoint.

## 8. Catatan
- Baseline free tier bersifat **direksional** (N kecil, oracle + probe), bukan angka
  LongMemEval kanonik. Cukup untuk gerbang keputusan internal Langkah 5.
- Setelah keluar plan mode, simpan ke memori: batasan free tier ~1M/model, disiplin
  satu-model-embed, larangan full-`_s`, kebijakan tanpa-rotasi reader/judge/embed.
