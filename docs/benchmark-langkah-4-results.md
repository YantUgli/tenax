# Langkah 4 — Uji Ketahanan Staleness (7 Jul 2026)

Menutup **gerbang Langkah 5 kriteria #6**: "fakta penting selamat setelah siklus
forget/reflect" ([Protokol §Langkah 4](Protokol-Benchmark-dan-Gerbang-Grounded.md)).
Benchmark standar (LongMemEval) tak menguji apakah mesin swakelola Tenax justru **merusak**
memorinya sendiri seiring waktu; uji ini dibuat khusus untuk itu.

## Prasyarat kode (Bagian A)
`reflect()`/`consolidate()` merutekan distilasi ke `qwen_chat_model` yang default-nya
`qwen-plus` — **mati permanen** (kuota free habis sejak Langkah 2) → `reflect()` akan 403
begitu menemukan klaster. Perbaikan:
1. **Default chat → `qwen-turbo`** ([app/config.py](../app/config.py) + `QWEN_CHAT_MODEL`
   di `.env`). Menghidupkan semua jalur non-cheap (reflect, remember tanpa `--cheap`).
2. **Plumb `cheap`** lewat `engine.reflect(cheap=)` → `consolidate(cheap=)` →
   `chat_json(cheap=)` (meniru pola `remember(..., cheap=)`).
3. **Hook jam simulasi** `sweep(now=)` → `decay_score(now=)` untuk siklus deterministik
   (harness memilih meng-*age* baris DB, lebih konsisten dengan reinforcement `recall`
   yang menulis jam nyata).

## Harness — [benchmark/staleness.py](../benchmark/staleness.py)
Perluasan uji sintetis (protokol: "perluas harness sintetismu"). Seed dunia:
- **6 fakta penting** (importance 8) — harus selamat saat dipakai.
- **1 fakta near-dup** dalam 3 parafrasa (importance 7) — reflect **harus** menggabung tanpa
  menghilangkan jawaban.
- **Pasangan mirip-tapi-beda** (putri Mia↔kacang vs putra Leo↔kerang) — reflect **tak boleh**
  mengonflasikan.
- **10 distraktor** (importance 3) — diharapkan dilupakan (perilaku benar).

Tiap siklus: (1) *accessed* → `recall` fakta penting (reinforsir akses); (2) age dunia −Δ
hari; (3) `forget()`; (4) `reflect(cheap=True)`. Ukur non-reinforcing: survival, wrong-merge,
correct-merge, jejak storage. Dua varian: **accessed** (fakta dipakai → wajib selamat) dan
**dormant** (tak pernah dipakai → memetakan batas peluruhan). Budget recall sengaja kecil
(150 tok) agar recall **selektif** — pada korpus ~20 memori, budget 1200 akan menyorot &
mereinforsir semuanya, menutupi kerja `forget`.

Perintah: `pipenv run python -m benchmark.staleness --cycles 3 --delta-days 14 --variant both`

## Hasil (K=3, Δ=14 hari)

| Siklus | accessed survival | dormant survival | wrong-merge | aktif→arsip (accessed) |
|---|---|---|---|---|
| baseline | 6/6 (100%) | 6/6 (100%) | 0 | 19 → 0 |
| 1 (~15 hr) | **6/6 (100%)** | 6/6 (100%) | 0 | 10 → 10 |
| 2 (~29 hr) | **6/6 (100%)** | **0/6 (0%)** | 0 | 8 → 12 |
| 3 (~43 hr) | **6/6 (100%)** | 0/6 (0%) | 0 | 8 → 12 |

- **accessed:** fakta penting selamat **100% di semua siklus** sementara distraktor luruh
  (aktif 19→8). Near-dup tergabung benar (2 memori → 1 kanonik, jawaban "monday" tetap
  ter-recall). Pasangan Mia/Leo tetap terpisah. **wrong-merge = 0.**
- **dormant:** fakta penting bertahan 1 siklus, luruh di siklus 2 (~29 hari, di bawah
  `forget_threshold`=0.15). Ini **batas Ebbinghaus** — peluruhan fakta tak-terpakai memang
  desain, bukan bug.

**Verdict gerbang #6: LULUS** (`gate6_pass=true`) — fakta penting yang **masih dipakai** tak
mati, dan reflect **tak pernah** salah-gabung entitas berbeda.

## Temuan minor
- `consolidate_similarity`=0.86 → hanya 2 dari 3 parafrasa near-dup masuk klaster (parafrasa
  ke-3 <0.86 terhadap seed klaster; jawaban tetap selamat karena kedua-nya memuat "monday").
  Sinyal untuk penyetelan ambang bila diinginkan — bukan kegagalan.
- Batas retensi fakta penting yang **dorman** ~28–29 hari pada knob saat ini (tau=14,
  threshold=0.15, importance=8). Bila fakta penting yang jarang diakses perlu bertahan lebih
  lama, kandidat perbaikan: *importance-floor* di `decay_score`. **Ditunda** (prinsip protokol:
  ukur dulu; belum ada kegagalan pada jalur yang dipakai).

## Kuota
Praktis nol: **chat 306 tok / 2 panggilan** (turbo), **embed 1.484 tok / 97 panggilan**
(text-embedding-v4). Tak menyentuh sisa budget yang berarti. Data:
`benchmark/results/staleness.{jsonl,summary.json}`.

## Status gerbang Langkah 5 setelah Langkah 4
- #4 retrieval hit-rate: ✅ kuat (87.5% `_s`; single-session-assistant 0/2→5/5 di Langkah 3).
- #5 abstention: ✅ berfungsi.
- **#6 ketahanan staleness: ✅ LULUS (ini).**
- #1 akurasi vs naif (hybrid > naif di haystack berdistraktor): ❌ **masih terbuka** — satu-
  satunya klaim arsitektural yang belum dibuktikan (murah lewat `benchmark/run.py`).
- #2/#3 (knowledge-update/temporal): ⚠️ lantai reader turbo, bukan kegagalan memori;
  pengukuran ulang di model kuat terhalang matinya qwen-plus.
