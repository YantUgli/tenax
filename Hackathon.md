# Analisis Komprehensif: Global AI Hackathon Series with Qwen Cloud

## Gambaran Umum

Ini adalah hackathon global yang diselenggarakan oleh **Alibaba Cloud** (sebagai sponsor) dan dikelola oleh **Devpost**. Temanya: membangun AI Agent produksi-grade menggunakan **Qwen Cloud** — platform cloud milik Alibaba yang menyediakan akses ke model Qwen dan model unggulan lain dengan kemampuan reasoning dan multimodal tingkat lanjut.

**Fakta kunci:**
- Total hadiah: **$70,000+** (cash + cloud credits), dengan **$45,000** khusus dalam bentuk cash yang tercatat resmi di halaman prize
- Sudah ada **1.914 peserta terdaftar** saat ini
- Sifat kompetisi: online, terbuka untuk publik
- Managed by Devpost (platform hackathon terverifikasi)

## Jadwal Lengkap

| Periode | Mulai | Selesai |
|---|---|---|
| Submission (pengumpulan) | 26 Mei 2026, 08:00 PDT | 9 Juli 2026, 14:00 PDT |
| Judging (penjurian) | 10 Juli 2026, 08:00 PDT | 31 Juli 2026, 14:00 PDT |
| Pengumuman pemenang | — | ~7 Agustus 2026, 14:00 PDT |

Jadi kamu masih punya waktu sampai **9 Juli 2026** untuk submit — cukup mepet dari hari ini (2 Juli 2026), sekitar seminggu lagi.

## Cara Mulai (Onboarding)

1. **Daftar di Devpost** (~2 menit)
2. **Daftar Qwen Cloud** di qwencloud.com, cek kuota gratis, atau ajukan voucher **$40 kredit gratis** lewat form kupon khusus hackathon ([link](https://www.qwencloud.com/challenge/hackathon/voucher-application))
3. **Join Discord Qwen Cloud** (link tersedia di halaman resources)
4. **Pilih track**, review sample project & reference architecture, mulai build

Catatan penting: jika kredit gratis $40 habis, kamu bertanggung jawab atas biaya tambahan yang melebihi itu.

**Detail teknis platform:**
- API Base URL: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- API **OpenAI-compatible** — bisa langsung pakai OpenAI SDK (Python/Node.js) tinggal ganti base URL & key
- Ada dokumentasi resmi: intro platform, first API call, model selection guide, pricing guide, dan cara generate API key

## Lima Track yang Bisa Dipilih

Setiap track punya fokus penilaian teknis yang berbeda — pilih sesuai kekuatanmu:

**Track 1 — MemoryAgent**
Agent dengan memori persisten yang mengakumulasi pengalaman antar sesi. Fokus: efisiensi penyimpanan/pengambilan memori, "forgetting" informasi usang, dan recall memori kritis dalam context window terbatas.
> Ide proyek: research assistant yang mengingat semua paper yang dibaca, customer support agent yang tidak perlu bertanya ulang, personal knowledge base yang proaktif menyodorkan konteks relevan.

**Track 2 — AI Showrunner**
Manfaatkan model generasi video (Wan/HappyHorse) untuk pipeline pembuatan drama pendek end-to-end: naskah → storyboard → generasi video → editing. Ini **track dengan alokasi token tertinggi**.
> Ide proyek: pipeline podcast otomatis, game engine naratif dinamis, "writers' room" multi-agent yang brainstorm dan revisi kolaboratif.

**Track 3 — Agent Society**
Sistem multi-agent yang berkolaborasi lewat pembagian tugas, dialog, dan negosiasi. Penilaian menekankan pada bagaimana agent membagi peran, menyelesaikan konflik, dan menunjukkan efisiensi terukur dibanding baseline single-agent.
> Ide proyek: marketplace simulasi dengan agent pembeli/penjual bernegosiasi, platform debat multi-agent, swarm pemecah masalah kooperatif.

**Track 4 — Autopilot Agent**
Otomatisasi workflow bisnis nyata end-to-end (skenario terbuka: email → quote, alert sistem → remediasi otomatis, screening CV → penjadwalan interview). Penekanan pada **production-readiness**, bukan demo mainan — harus bisa menangani input ambigu, memanggil tool eksternal, dan punya human-in-the-loop checkpoint.
> Ide proyek: pipeline code review otomatis, analis data otonom, sistem deployment self-healing.

**Track 5 — EdgeAgent**
Perangkat fisik bertenaga Qwen — robot, IoT, smart hardware — yang mempersepsi via sensor edge, bernalar via cloud API, dan bertindak lokal. Harus menunjukkan orkestrasi edge-cloud yang tangguh di bawah keterbatasan bandwidth/latensi, penanganan data privacy-aware, dan graceful degradation saat offline/koneksi lemah.
> Ide proyek: asisten personal on-device tanpa koneksi cloud konstan, field agent offline untuk pekerja remote, aplikasi real-time sensitif-latensi.

## Yang Harus Dikumpulkan (Submission Requirements)

Ini bagian paling detail dan krusial — sering jadi sumber diskualifikasi kalau terlewat:

1. **URL repository kode** — harus publik, open source, dengan file lisensi open source yang **terlihat jelas di bagian "About" repo** (bukan cuma file LICENSE tersembunyi)
2. **Bukti Deployment di Alibaba Cloud** — rekaman singkat (terpisah dari video demo) yang membuktikan backend berjalan di Alibaba Cloud, disertai link ke file kode di repo yang menunjukkan penggunaan layanan/API Alibaba Cloud
3. **Diagram Arsitektur** — representasi visual jelas: bagaimana Qwen Cloud terhubung ke backend, database, dan frontend
4. **Video demo** — maksimal 3 menit (juri tidak wajib menonton lebih dari itu), diunggah ke YouTube/Vimeo/Youku, publik, tanpa musik/trademark berhak cipta tanpa izin
5. **Deskripsi teks** — jelaskan fitur & fungsionalitas proyek
6. **Identifikasi track** yang dipilih (hanya boleh masuk minimal 1 track)
7. **Opsional**: link blog/social post tentang journey membangun dengan Qwen Cloud — untuk eligible Blog Post Prize

Aturan tambahan penting:
- Proyek harus **baru dibuat** selama periode submission, atau jika sudah ada sebelumnya harus **di-update signifikan** setelah hackathon mulai (dan harus dijelaskan updatenya apa)
- Boleh submit lebih dari satu proyek, tapi tiap proyek harus **substansial berbeda**
- Semua materi harus dalam **Bahasa Inggris** (atau disertai terjemahan Inggris)
- Proyek harus tetap bisa diakses/diuji gratis oleh juri sampai periode judging berakhir

## Struktur Hadiah

| Kategori | Hadiah | Jumlah Pemenang |
|---|---|---|
| Tiap track (1–5) | $7.000 cash + $3.000 cloud credit + blog feature + swag + peluang jadi Ambassador | 1 pemenang/track (total 5) |
| Top 10 Honorable Mention | $500 cash + $500 cloud credit | 10 pemenang |
| Blog Post Award | $500 cash + $500 cloud credit | 10 pemenang |

**Catatan penting:** satu proyek hanya bisa menang **1 grand prize** dan maksimal **1 blog post prize** — tidak bisa menyapu bersih semua track.

## Kriteria Penilaian (Judging Criteria)

Ada 2 tahap:

**Stage 1 — Pass/Fail:** apakah proyek sesuai tema dan benar-benar menggunakan API/SDK Qwen Cloud yang disyaratkan.

**Stage 2 — Penilaian berbobot:**
- **Innovation & AI Creativity — 30%**: penggunaan API Qwen Cloud yang sophisticated (custom skills, integrasi MCP), inovasi algoritma/engineering
- **Technical Depth & Engineering — 30%**: kualitas arsitektur (modularitas, skalabilitas, error handling), clean code, kecanggihan tech stack
- **Problem Value & Impact — 25%**: relevansi dunia nyata, potensi skalabilitas untuk produk/komunitas open-source
- **Presentation & Documentation — 15%**: kejelasan demo teknis, dokumentasi arsitektur yang jelas

Ini menunjukkan juri sangat menghargai **kedalaman teknis dan integrasi MCP/custom skills**, bukan sekadar demo yang "kelihatan bagus" — 60% bobot ada di sisi teknis-inovasi.

## Eligibilitas & Batasan Penting

- Harus sudah dewasa (usia mayoritas) di negara domisili
- **Negara/wilayah yang dikecualikan**: sanksi PBB/AS/UK/EU/Singapura/China, termasuk Iran, Korea Utara, Kuba, Suriah, Crimea, wilayah Donetsk/Luhansk, Rusia, Belarus, **dan juga Brazil serta Quebec** (kemungkinan karena regulasi lokal, bukan sanksi)
- Tidak boleh ada konflik interest (karyawan Alibaba Cloud/Devpost, keluarga juri, dsb.)
- Perselisihan diselesaikan lewat **arbitrase SIAC di Singapura**, hukum Singapura yang berlaku

## Poin Strategis untuk Peserta

Kalau kamu berencana ikut, beberapa hal yang layak diperhatikan:

- **Waktu sangat sempit** — deadline 9 Juli, tinggal ~1 minggu dari sekarang. Prioritaskan pilih track dan mulai setup API dulu.
- **Proof of Alibaba Cloud deployment adalah wajib mutlak** — banyak hackathon serupa gagal di sini karena peserta hanya deploy di Vercel/local dan lupa syarat ini.
- Track 2 (AI Showrunner) punya alokasi token tertinggi — cocok kalau proyekmu memang video-heavy.
- Karena bobot "Technical Depth" dan "Innovation" masing-masing 30%, integrasi **MCP (Model Context Protocol)** dan custom skills tampaknya jadi diferensiator kuat yang secara eksplisit disebut juri.
- Lisensi open source di repo harus **terlihat di bagian About** — bukan cuma ada file LICENSE, tapi harus terdeteksi otomatis oleh GitHub/repo host.

Mau saya bantu susun rencana teknis untuk salah satu track spesifik (misalnya arsitektur MemoryAgent atau Autopilot Agent), atau bantu setup API call pertama ke Qwen Cloud?