# Gerbang Langkah 5 — Papan Skor (7 Jul 2026)

Status enam kriteria gerbang keputusan grounded
([Protokol §Langkah 5](Protokol-Benchmark-dan-Gerbang-Grounded.md)) setelah Langkah 0–4.

| # | Kriteria | Status | Bukti |
|---|---|---|---|
| 1 | Akurasi vs naif (hybrid > naif) | ✅ **bentuk retrieval** / ⚠️ bentuk akurasi terbatas | Hybrid **6/6** vs recency-only **0/6** @400 tok ([hybrid_vs_naive](../benchmark/results/hybrid_vs_naive.summary.json)). Bentuk akurasi end-to-end terhalang matinya qwen-plus. |
| 2 | Knowledge-update | ✅ **fitur + bentuk retrieval** / ⚠️ akurasi = lantai reader | Belief-revision diimplementasi 7 Jul ([Langkah 3.1](benchmark-langkah-3.1-belief-revision.md)): sintetis **6/6 update PASS, wrong-supersede 0**; delta LongMemEval (7 item sama, turbo) 3/7→3/7 netto — 1 menang buku-teks (nilai usang terganti), 1 kalah soal-historis (butuh 3.2), sisanya lantai reader (evidence hit 100%). |
| 3 | Temporal-reasoning | ⚠️ lantai reader + fitur | 15% (turbo). Validity-interval belum diimplementasi; bedah 3.1 memberi bukti empiris desainnya (recall sadar-waktu yang menyajikan fakta tersupersede ber-tag usang). |
| 4 | Retrieval hit-rate | ✅ | 87.5% `_s`; single-session-assistant 0/2→5/5 (Langkah 3). |
| 5 | Abstention | ✅ | Berfungsi (menolak saat fakta tak ada). |
| 6 | Ketahanan staleness | ✅ | Fakta penting selamat 6/6 semua siklus; wrong-merge 0 ([Langkah 4](benchmark-langkah-4-results.md)). |

## Ringkasan Kriteria #1 (7 Jul)
`benchmark/run.py` menaruh 6 fakta penting di masa lalu lalu membanjiri jendela terbaru
dengan 30 distraktor. Dalam budget 400 token yang sama:

```
Mnemo (hybrid + budget) : 6/6  (100%)  avg 395 tok
Baseline (recency-only) : 0/6  (0%)    avg 400 tok
```

Recency-only melewatkan **setiap** fakta (terkubur di bawah distraktor terbaru); hybrid +
budget-aware recall menyorot **semuanya**. Ini menutup **bentuk retrieval** kriteria #1 —
inti klaim arsitektural "hybrid > sekadar simpan-N-terbaru". Biaya ~nol (hanya embedding).

## Interpretasi gerbang
- **Provable sekarang: 5 dari 6 LULUS pada bentuk yang bisa dibuktikan di free tier**
  (#1 retrieval, #2 fitur+retrieval, #4, #5, #6) — mencakup **pemblokir mutlak** gerbang
  (#4 retrieval hit-rate) dan klaim arsitektural inti (#1).
- **Bentuk akurasi #1/#2/#3 tetap dibatasi lantai reader** — reader kuat mustahil di free
  tier (qwen-plus mati). Bedah 3.1 menunjukkan sisa kegagalan knowledge-update adalah
  lantai reader (evidence hit 100%) + satu rasa soal ("nilai lampau") yang menunggu 3.2.
- **#3 (temporal) satu-satunya fitur inti yang belum dibangun.** Bukti empiris dari 3.1
  sudah menentukan bentuknya: validity interval + recall yang menyajikan fakta
  tersupersede ber-tag usang.

**Keputusan (7 Jul): TAHAN grounded.** Sesuai aturan gerbang ("kriteria 2/3 gagal →
tahan") dan tenggat 9 Jul: sisa waktu dialokasikan ke penguatan inti (3.1 ✅), bukti
terukur, dan kesiapan submission (deploy Alibaba Cloud + demo). Grounded tetap peta jalan
Fase 3 setelah inti melewati gerbang penuh; 3.2 (temporal validity) adalah pekerjaan inti
berikutnya.
