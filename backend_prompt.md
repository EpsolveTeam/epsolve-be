# Prompt Perbaikan Backend — Chat History

## Masalah

Endpoint `GET /chat/history/{session_id}` tidak mengembalikan field `no_answer` dan `ticket_flag` untuk setiap entry chat log. Akibatnya, saat user melakukan refresh halaman atau pindah session chat, banner "Maaf, belum ditemukan jawaban..." dan tombol "Ajukan ke Customer Support" tidak muncul meskipun sesi chat tersebut sebelumnya mendapatkan jawaban "tidak ditemukan" dari knowledge base.

## Perubahan yang Dibutuhkan

### 1. Simpan field `no_answer` dan `ticket_flag` di tabel/model `chat_logs`

Saat menyimpan chat log (proses di endpoint `POST /chat/`), simpan dua field boolean ini:

- `no_answer`: `true` jika pertanyaan user tidak ditemukan di knowledge base (sehingga bot mengembalikan jawaban default "Maaf, belum ditemukan jawaban...")
- `ticket_flag`: `true` jika respons bot mengandung flag `CREATE_SUPPORT_TICKET_FLAG` (menandakan perlu dibuat tiket)

### 2. Kembalikan field `no_answer` dan `ticket_flag` di endpoint history

Endpoint `GET /chat/history/{session_id}` saat ini mengembalikan array JSON, contoh:

```json
[
  {
    "id": 1,
    "user_query": "...",
    "bot_response": "...",
    "image_query_url": "...",
    "created_at": "..."
  }
]
```

**Harus diubah menjadi:**

```json
[
  {
    "id": 1,
    "user_query": "...",
    "bot_response": "...",
    "image_query_url": "...",
    "created_at": "...",
    "no_answer": true,
    "ticket_flag": false,
    "category": "Produksi & Operasi"
  }
]
```

### 3. Field yang perlu ditambahkan:

| Field | Type | Keterangan |
|-------|------|------------|
| `no_answer` | boolean (`true`/`false`) | `true` jika pertanyaan tidak ditemukan di KB |
| `ticket_flag` | boolean (`true`/`false`) | `true` jika respons mengandung CREATE_SUPPORT_TICKET_FLAG |
| `category` | string atau null | Kategori yang dipilih user saat mengirim chat |

### 4. Proses penyimpanan (saat `POST /chat/`)

Ketika backend memproses chat dan mengembalikan respons, pastikan field-field di atas ikut disimpan ke database bersamaan dengan `bot_response`, `user_query`, `session_id`, dll.

---

**Prioritas:** High — karena mempengaruhi user experience fitur chat yang tidak bisa menyimpan status "tidak ditemukan jawaban" dengan benar.