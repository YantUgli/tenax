# Upgrade Reader → qwen3.7-plus (16 Jul 2026)

## Latar belakang
Gerbang [Langkah 5](benchmark-gate-langkah-5.md) menyimpulkan kriteria akurasi/knowledge-
update/temporal-reasoning semua mentok di **"lantai reader"**: *"reader kuat mustahil di
free tier (qwen-plus mati)"*. Dapat voucher hackathon $40 → ini kesempatan mengetes apakah
reader yang lebih kuat benar-benar mengangkat lantai itu.

Kriteria keputusan: satu model dipakai konsisten sepanjang evaluasi (longeval yang
mencerminkan pemakaian produk nyata), model harus aktif dikembangkan (bukan legacy — catatan:
`qwen-turbo` ternyata sudah dibekukan, Alibaba sarankan `qwen-flash` sebagai penerus).

## Pemilihan model
Dibandingkan harga input/output riil dari console (bukan cuma web search) untuk
turbo/flash/plus/qwen3.7-plus/qwen3.7-max. **qwen3.7-plus** dipilih: generasi terbaru,
dan proyeksi awal (`--estimate`, asumsi completion pendek) full-pipeline 500 item muat di
~$32.7 dari budget $40 — angka ini kemudian terbukti meleset (lihat di bawah).

## Setup
`.env`: `QWEN_CHAT_MODEL=qwen3.7-plus`. Diverifikasi jalan via `pipenv run python -m
scripts.first_call` (chat + embed OK). `QWEN_CHEAP_MODEL` tetap `qwen-turbo` (fallback,
tak terpakai kecuali `--cheap`).

## Bug & perbaikan yang ditemukan selagi persiapan

1. **`count_tokens` crash pada token khusus** — [app/memory/retrieve.py:35](../app/memory/retrieve.py#L35).
   Teks LongMemEval kadang memuat literal `<|endoftext|>`, bikin `tiktoken.encode()` raise.
   Fix: `disallowed_special=()`. Tanpa ini item yang kena akan tercatat error (harness sudah
   toleran per-item), tapi datanya hilang diam-diam.

2. **Thinking-mode nyala default di qwen3.7-plus — ini yang paling mahal.** Diagnostic satu
   panggilan ekstraksi (656 token input, teks pendek) makan **51.5 detik**, menghasilkan
   **2.657 completion token** — 2.470 di antaranya (93%!) `reasoning_content` tersembunyi,
   bukan jawaban asli. Ini yang bikin smoke-test awal terlihat "diam" berjam-jam dan dashboard
   usage tak berubah (satu call belum kelar).
   Fix: `extra_body={"enable_thinking": False}` di kedua method
   [app/qwen_client.py](../app/qwen_client.py) — `chat()` (baris ~102-105) dan `chat_json()`
   (baris ~126-133). Diverifikasi aman untuk `qwen-turbo` juga (tak error). Setelah fix:
   panggilan yang sama → **2.9 detik**, **97 completion token**, `reasoning_content` 0 char.

3. **Progress indicator per sesi saat ingest** — [benchmark/longmemeval.py](../benchmark/longmemeval.py)
   fungsi `ingest_item`: sebelumnya nol output sampai satu ITEM utuh selesai (bisa puluhan
   sesi tanpa jejak). Sekarang print flushed per sesi.

4. **`KeyboardInterrupt` ditangkap bersih** — pola sama seperti `QuotaExceeded` yang sudah
   ada: Ctrl-C sekarang checkpoint (`summary.json` + usage token tersimpan) alih-alih mati
   total tanpa jejak.

5. **Script baru [`benchmark/summarize_jsonl.py`](../benchmark/summarize_jsonl.py)** —
   rekonstruksi summary (akurasi, retrieval hit-rate, per-kategori) dari JSONL manapun,
   partial atau lengkap, pakai fungsi `summarize()`/`print_summary()` yang sama persis dengan
   harness. Jaga-jaga kalau proses mati keras (`kill -9`, crash) sebelum sempat menulis
   summary sendiri. Catatan: token/biaya riil (`client.usage()`) TIDAK bisa direkonstruksi
   dari JSONL (hidup cuma di memori proses) — cross-check ke dashboard DashScope.

## Smoke test (n=3, `--sample 3 --seed 13 --shuffle`)

| Kategori | n | Akurasi |
|---|---|---|
| knowledge-update | 1 | 100% |
| multi-session | 1 | 100% |
| temporal-reasoning | 1 | 0% |

Overall **66.7%** (vs baseline turbo lama 42%), retrieval hit-rate **100%**. Sinyal awal
mendukung hipotesis lantai-reader — tapi n=3 masih terlalu kecil untuk kesimpulan solid.

Token nyata: chat 533.355 (196 call: 412.071 prompt + 121.284 completion), embed 65.937
(264 call). **elapsed_sec: 2344.6** (≈39 menit untuk 3 item / 149 sesi).

## Temuan kritis: proyeksi awal meleset di dua sumbu

**Biaya** — chat riil ≈ $0.287 untuk 3 item (prompt $0.32/M + completion $1.28/M) =
**~$0.096/item**. Diekstrapolasi ke 500 item: **~$48** — di atas budget $40 (belum termasuk
embed). Penyebab: estimator (`--estimate`) tak memodelkan panggilan konfirmasi
belief-revision (`revise.py`)/consolidate yang ikut jalan (196 call nyata vs ~146
proyeksi untuk 3 item ini), dan completion ekstraksi riil lebih variatif dari asumsi
`min(0.3×input, 512)`.

**Waktu** — 39 menit / 3 item → diekstrapolasi ke 500 item (~23.882 sesi): **≈4.5 hari**
nonstop sekuensial. Ini pembatas yang lebih ketat daripada uang.

**Keputusan: TIDAK menjalankan full 500 item.** Pakai stratified sample yang muat waktu
& budget.

## Run sesungguhnya (sedang/akan dijalankan)

Dipilih **`--sample 50`** (≈$5, ≈11 jam — muat semalaman):

```bash
nohup pipenv run python -m benchmark.longmemeval --dataset data/longmemeval_s.json \
  --sample 50 --seed 13 --shuffle \
  --out benchmark/results/qwen37plus_sample50.jsonl \
  > benchmark/results/qwen37plus_sample50.log 2>&1 &
```

Pantau: `tail -f benchmark/results/qwen37plus_sample50.log`
Cek proses: `ps aux | grep longmemeval`
Stop aman (checkpoint tersimpan): `kill -INT <PID>` — **jangan** `kill` biasa/`kill -9`
(tetap aman berkat fix #4, tapi kehilangan usage-tracking realtime; item selesai tetap ada
di JSONL, bisa direkonstruksi via `summarize_jsonl.py`).

## Status & langkah lanjutan
- [ ] Run `--sample 50` selesai (cek `benchmark/results/qwen37plus_sample50.summary.json`)
- [ ] Bandingkan `overall_accuracy`/per-kategori vs baseline turbo (42% akurasi, 15%
      temporal, knowledge-update 3/7) — apakah lantai reader di gate Langkah 5 terangkat?
- [ ] Cross-check biaya riil (dashboard DashScope) vs proyeksi ~$5 untuk sample 50
- [ ] Kalau hasil bagus & waktu/budget masih ada: pertimbangkan sample lebih besar
      (100-300 item) untuk penguatan statistik
- [ ] Update `docs/benchmark-gate-langkah-5.md` kalau kriteria #1/#2/#3 berubah status

## Catatan terbuka / risiko yang belum terverifikasi
- `tiktoken` (`cl100k_base`) di `count_tokens` cuma proxy — tokenizer asli Qwen bisa beda,
  jadi angka token (bukan biaya riil di dashboard) punya margin error.
- Estimasi biaya pakai tier harga **terendah** dari rentang yang diberikan Qwen Cloud —
  belum dikonfirmasi apakah sebagian request kena tier lebih mahal di skala besar.
- Deadline hackathon: memory sesi sebelumnya mencatat 9 Jul 2026, tapi dokumen ini ditulis
  16 Jul 2026 — belum diklarifikasi apakah deadline diperpanjang atau ini eksplorasi
  pasca-submission.

## File yang berubah sesi ini
- [app/qwen_client.py](../app/qwen_client.py) — thinking mode dimatikan (`chat`, `chat_json`)
- [app/memory/retrieve.py](../app/memory/retrieve.py) — fix crash `count_tokens`
- [benchmark/longmemeval.py](../benchmark/longmemeval.py) — progress print per sesi,
  `KeyboardInterrupt` ditangkap
- [benchmark/summarize_jsonl.py](../benchmark/summarize_jsonl.py) — baru
- `.env` — `QWEN_CHAT_MODEL=qwen3.7-plus`
