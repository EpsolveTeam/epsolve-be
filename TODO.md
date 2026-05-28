# TODO - Implementasi Hybrid Retriever, Ticket-Flag, dan faq_id CRUD (sesuai notebook capstone_rag_testing.ipynb)

## 0. Setup & Referensi
- [ ] Buat checklist tujuan implementasi:
  - (1) Hybrid retriever = Vector + BM25 + fusion
  - (2) Ticket-flag logic: jika jawaban tidak ada di context => balas `CREATE_SUPPORT_TICKET_FLAG`
  - (3) Tambahkan kolom `faq_id` di `KnowledgeBase`, dan gunakan untuk update/delete mirip LlamaIndex.
- [ ] Tambahkan/cek dependency yang diperlukan:
  - `rank_bm25` (atau implementasi BM25 lain)
  - library tokenizer/normalisasi teks (jika perlu)

## 1. Tambah `faq_id` ke KnowledgeBase (dan migration)
- [ ] Update model `app/models/knowledge.py`:
  - Tambahkan field `faq_id: str` (atau UUID string) dengan unique index.
- [ ] Buat migration Alembic/SQL untuk menambah kolom `faq_id` ke tabel knowledge_base.
- [ ] Update seed/import (kalau ada) agar setiap knowledge lama mendapat `faq_id` (generate jika null).
- [ ] Update skema API `app/schemas/knowledge.py`:
  - tambahkan `faq_id` pada request/response.
- [ ] Update endpoint CRUD `app/api/api_v1/endpoints/knowledge.py`:
  - gunakan `faq_id` sebagai identitas update/delete *selain* atau *menggantikan* `id`.
  - contoh perubahan:
    - DELETE berdasarkan `faq_id` (atau path `/knowledge/by-faq/{faq_id}`)
    - PUT berdasarkan `faq_id`
    - (opsional) keep existing `/knowledge/{kb_id}` untuk backward compatibility.

## 2. Hybrid Retriever = Vector (pgvector) + BM25 + Fusion
- [ ] Implementasi BM25 retrieval berbasis keyword dari `KnowledgeBase.content`:
  - Tambahkan modul/kelas BM25 engine (bisa di `app/services/` atau di dalam `rag_service.py`).
  - Bentuk dokumen BM25 dari `KnowledgeBase.content` (kemungkinan precompute per kategori jika performa perlu).
- [ ] Tentukan strategi fusion:
  - Opsi A: simple merge top-k
  - Opsi B: reciprocal rank fusion (`reciprocal_rerank` ala notebook)
  - Opsi C: rerank kecil dengan aturan heuristik (tanpa LLM)
- [ ] Update `app/services/rag_service.py`:
  - tambah function `search_hybrid_docs(query_embedding, query_text, limit, category)`
  - hasil hybrid menggabungkan kandidat dari vector + BM25.
- [ ] Update `rag_service.query()` agar memanggil hybrid retrieval (bukan vector-only).
- [ ] Pastikan output `sources` tetap sesuai format API.

## 3. Ticket-Flag Logic Persis Seperti Notebook
- [ ] Update `custom_system_prompt` logic di service supaya:
  - Jawaban harus berdasarkan context saja.
  - Bila tidak ada jawaban di context, output **harus persis**: `CREATE_SUPPORT_TICKET_FLAG`.
- [ ] Implementasi deteksi “tidak ada jawaban” yang robust:
  - Pilihan implementasi:
    - (a) pakai system prompt ketat + verifikasi output (tepat string)
    - (b) (lebih aman) lakukan post-check: jika answer mengandung frase “tidak menemukan”/“not in context” => set flag
- [ ] Update `app/services/rag_service.py`:
  - Pastikan `generate_response()` memakai system prompt yang memaksa flag.
- [ ] Update endpoint `app/api/api_v1/endpoints/chat.py`:
  - Jika answer mengandung `CREATE_SUPPORT_TICKET_FLAG`, set field status chat/ticket trigger sesuai kebutuhan.
  - Jika ada integrasi ticket creation di backend, pastikan terpicunya.

## 4. Update & Test
- [ ] Jalankan unit/integration test minimal:
  - Query yang mengandung keyword/error code → pastikan BM25 membantu retrieval.
  - Query yang tidak ada di KB → pastikan output sama persis `CREATE_SUPPORT_TICKET_FLAG`.
  - CRUD berbasis `faq_id`:
    - tambah knowledge baru dengan faq_id → update/delete bekerja.
- [ ] Lakukan smoke test pada endpoint `/chat/` dengan dan tanpa image.

## 5. Performance/Cache (opsional tapi disarankan)
- [ ] Jika BM25 index build mahal:
  - implement cache BM25 per kategori (refresh saat knowledge berubah)
  - atau lazy-load dan invalidate pada create/update/delete.

## Done Criteria (Acceptance)
- [ ] Hybrid retriever aktif dan kualitas retrieval meningkat (dibuktikan dengan contoh pertanyaan internal).
- [ ] Ticket-flag muncul persis `CREATE_SUPPORT_TICKET_FLAG` ketika jawaban tidak ditemukan di context.
- [ ] CRUD update/delete memakai `faq_id` dan berperilaku sesuai notebook.

