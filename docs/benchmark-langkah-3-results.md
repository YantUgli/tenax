# Langkah 3 — Iterasi 1: perbaikan ekstraksi turn informatif asisten (7 Jul 2026)

Target #1 dari gerbang Langkah 2: titik lemah retrieval `single-session-assistant`
(2/2 miss di Tahap 1). Lanjutan dari [baseline Langkah 2](benchmark-baseline-results.md).

## Diagnosis (bebas kuota)
Dua mode kegagalan berbeda pada item yang gagal di Tahap 1:

- **`41275add` — ekstraksi kurang-tangkap (mode dominan).** Asisten merekomendasikan video
  Mayo Clinic spesifik (judul + URL). Ekstraktor menyimpannya sebagai satu memori kabur:
  *"The assistant provided four YouTube video links..."* — **judul & URL (inti pertanyaan)
  hilang**. Ini menjelaskan kegagalan di dua jalur: retrieval miss di `_s` (tak ada term
  "Mayo Clinic"/URL untuk dicocokkan) DAN reader salah di oracle (100% hit tapi fakta tak
  ada di memori).
- **`6ae235be` — ekstraksi baik, ranking kalah di distraktor.** Satu memori = jawaban gold
  persis ("Lake Charles Refinery uses atmospheric distillation, FCC, alkylation,
  hydrotreating"). Benar di oracle; miss di `_s` = isu ranking/kompetisi budget, bukan
  ekstraksi. (Bobot recency hanya 0.1, jadi bukan soal recency.)

## Perubahan (bebas kuota)
1. **Prompt ekstraksi** ([app/memory/extract.py](../app/memory/extract.py)) — tambah aturan:
   tangkap fakta dari KEDUA pembicara (jawaban asisten sering memuat substansi yang ditanya
   ulang); pertahankan spesifik VERBATIM (nama, judul, URL, angka, tanggal); satu memori per
   item saat sebuah turn memberi daftar (mis. beberapa video, masing-masing judul + URL).
2. **Robustness parse JSON** ([app/qwen_client.py](../app/qwen_client.py)) — `_loads_lenient`
   kini menyelamatkan objek lengkap dari respons yang **terpotong** (truncated) alih-alih
   kehilangan seluruh memori satu sesi. Output yang lebih rinci menaikkan peluang JSON
   terpotong; ini membuatnya tak-fatal (item `778164c6` di run di bawah akan pulih, bukan error).

## Bukti kausal — smoke test (qwen-turbo, item & model SAMA, prompt lama vs baru)
| Item | Prompt LAMA | Prompt BARU |
|---|---|---|
| `41275add` | 2 memori kabur; **judul + URL Mayo Clinic hilang** | 4 memori, tiap video judul+URL — termasuk gold verbatim: *"The Mayo Clinic has a YouTube video titled 'How to Sit Properly at a Desk to Avoid Back Pain' with the URL https://www.youtube.com/watch?v=UfOvNlX9Hh0"* |
| `6ae235be` | 6 memori, fakta Lake Charles benar | 7 memori, **tanpa regresi** — fakta Lake Charles tetap verbatim |

Karena model & item ditahan tetap, ini mengisolasi efek prompt: prompt baru memulihkan
spesifik yang dulu dibuang, tanpa merusak kasus yang sudah benar. Biaya: 5.709 tok (turbo).

## Konfirmasi retrieval — `_s`, single-session-assistant, retrieval-only
`--categories single-session-assistant --sample 6 --max-sessions-per-item 15 --retrieval-only
--cheap --keep-users` (ekstraksi qwen-turbo, prompt baru).

| Metrik | Tahap 1 baseline | Langkah 3 iterasi 1 |
|---|---|---|
| single-session-assistant retrieval hit | **0/2 (0%)** | **5/5 (100%)** |

Tiap item menarik sesi bukti ke recall (1/1) meski bersaing dengan **30–46 memori** yang
mengisi budget 1200 token → 100% kokoh, bukan lolos-tipis. 1 item (`778164c6`) error karena
JSON terpotong (kini diperbaiki oleh salvage; tak diulang — 5/5 sudah konklusif).
Biaya: chat 260.380 (81 calls) / embed 20.033. Data: `benchmark/results/langkah3_ssa_retrieval.*`.

**Caveat validitas:** angka 0/2 → 5/5 bersifat **direksional** — baseline diekstraksi di
qwen-plus (kuota habis), run ini di qwen-turbo, dan item sampelnya berbeda. Bukti kausal yang
bersih adalah smoke test (model & item ditahan tetap). Keduanya konsisten: fix memulihkan
spesifik, dan dengan spesifik itu hadir, retrieval single-session-assistant jadi kuat.

## Status kuota (7 Jul, mungkin reset harian)
- `qwen-plus`: **HABIS** (403 FreeTierOnly sejak Tahap 1) — belum bisa re-ukur akurasi di model kuat.
- `qwen-turbo`: dipakai +266k iterasi ini (5.7k smoke + 260k run) di atas ~387k Langkah 2.
- `text-embedding-v4`: +20k (nyaris tak tersentuh, ratusan-ribu sisa).

## Sisa untuk iterasi berikut (butuh konfirmasi + kuota)
- **Case-2 ranking tidak berulang** di sampel segar (5/5 hit). Miss `6ae235be` asli tak
  direproduksi (state `_s`-nya sudah tertimpa oracle); mengejar diagnosisnya butuh re-ingest
  = kuota. Ditunda sampai ada sinyal berulang.
- **Re-ukur akurasi end-to-end** (oracle + `_s` reader) pada model lebih kuat begitu kuota
  qwen-plus kembali — untuk mengukur apakah fix ekstraksi menaikkan akurasi, bukan hanya retrieval.
- **Kriteria #1 (hybrid > naif) di haystack berdistraktor** masih tertunda dari Langkah 2.
