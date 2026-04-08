# javaxFlash

`javaxFlash` adalah library Python kecil untuk mengakses beberapa endpoint AI lewat satu client API yang sederhana.

Tujuan library ini:

- memberi satu entry point yang ringan: `FlashClient`
- memudahkan pindah antara provider `flash` dan `deepseek`
- mendukung auto routing atau provider manual
- mengembalikan format respons yang konsisten

## Cocok untuk apa

- pertanyaan cepat dengan provider default `flash`
- prompt reasoning yang lebih berat dengan `deepseek`
- eksperimen lokal tanpa harus menulis wrapper request berulang-ulang

## Install

Install package inti:

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
```

Kalau ingin menjalankan contoh interaktif di folder `examples`, install juga `rich`:

```bash
python -m pip install rich
```

## Quick Start

Contoh paling sederhana:

```python
from javaxFlash import FlashClient

client = FlashClient()

response = client.flash("Jelaskan konsep Q-learning dengan sederhana")

print(response.text)
print(response.provider)
print(response.model_used)
```

Alias `ask()` juga tersedia:

```python
response = client.ask("Apa itu Python?")
print(response.text)
```

## Cara Kerja Singkat

Secara default, `FlashClient` akan:

1. menerima prompt dari user
2. memilih provider berdasarkan mode atau auto routing
3. mengirim request ke endpoint provider
4. mengembalikan hasil dalam bentuk `FlashResponse`

Kalau provider utama gagal dan fallback aktif, client akan mencoba provider cadangan.

## Memilih Provider

### 1. Auto routing

Auto routing cocok kalau kamu ingin library memilih provider secara otomatis.

```python
response = client.flash("Bandingkan REST dan GraphQL untuk project kecil", auto_route=True)
```

### 2. Fast mode

Gunakan saat ingin jawaban cepat.

```python
response = client.flash("Apa itu Python?", mode="fast")
```

### 3. Reasoning mode

Gunakan saat prompt butuh analisis lebih dalam.

```python
response = client.flash("Kenapa algoritma ini gagal dan bagaimana cara debug-nya?", mode="reasoning")
```

### 4. Paksa provider tertentu

Kalau kamu sudah tahu provider mana yang ingin dipakai:

```python
response = client.flash("Gunakan provider cepat", provider="flash")
response = client.flash("Analisis bug ini", provider="deepseek")
```

## Konfigurasi Dasar

Kalau ingin mengubah perilaku default client:

```python
from javaxFlash import FlashClient, FlashConfig

config = FlashConfig(
    timeout=30.0,
    auto_route=True,
    fallback_enabled=True,
    default_system_instruction="You are javaxFlash, a concise and practical AI assistant.",
)

client = FlashClient(config=config)
```

Field config yang paling sering dipakai:

- `timeout`: timeout request HTTP
- `auto_route`: aktif/nonaktif routing otomatis
- `fallback_enabled`: coba provider cadangan saat request gagal
- `default_system_instruction`: system prompt default
- `default_gemini_model`: nama model untuk provider `flash`
- `deepseek_temperature`: temperature default untuk DeepSeek
- `debug`: tampilkan log sederhana saat development
- `request_logging`: aktifkan logging request

## Custom System Instruction

Kamu bisa memberi system instruction per request:

```python
response = client.flash(
    "Bantu saya menyusun rencana automation",
    system_instruction="You are an AI assistant focused on backend automation and practical implementation.",
)
```

Atau menjadikannya default lewat `FlashConfig`.

## Response Object

Setiap request mengembalikan `FlashResponse` dengan struktur yang konsisten:

```python
response.text
response.model_used
response.provider
response.raw
response.route_reason
response.error
```

Penjelasan singkat:

- `text`: isi jawaban utama
- `model_used`: nama model yang dilaporkan provider
- `provider`: provider yang benar-benar dipakai
- `raw`: payload JSON mentah dari endpoint
- `route_reason`: alasan routing yang dipilih client
- `error`: pesan error jika request gagal

Contoh:

```python
response = client.flash("Jelaskan recursion")

if response.error:
    print("Error:", response.error)
else:
    print(response.text)
    print("Provider:", response.provider)
    print("Reason:", response.route_reason)
```

## Parameter yang Bisa Dipakai Saat Request

API utama:

```python
client.flash(
    prompt,
    mode=None,
    provider=None,
    auto_route=None,
    system_instruction=None,
    fallback_provider=None,
    **kwargs,
)
```

Parameter penting:

- `prompt`: isi permintaan user
- `mode`: `fast` atau `reasoning`
- `provider`: paksa provider tertentu
- `auto_route`: override perilaku routing default
- `system_instruction`: system instruction per request
- `fallback_provider`: provider cadangan jika request utama gagal
- `**kwargs`: parameter tambahan yang diteruskan ke provider

Contoh `kwargs`:

```python
response = client.flash(
    "Jelaskan greedy algorithm",
    provider="deepseek",
    temperature=0.2,
)
```

## Menjalankan Contoh Interaktif

Contoh interaktif ada di `examples/basic_usage.py`.

Jalankan dengan:

```bash
python examples/basic_usage.py
```

atau:

```bash
python -m examples.basic_usage
```

## Struktur Project

File yang paling penting:

- `javaxFlash/client.py`: entry point utama library
- `javaxFlash/config.py`: konfigurasi client
- `javaxFlash/router.py`: logika pemilihan provider
- `javaxFlash/providers.py`: implementasi request ke provider
- `javaxFlash/models.py`: model respons

## Catatan Penting

- `flash` di library ini adalah nama provider cepat yang dibacking oleh endpoint Gemini Lite.
- `deepseek` dipakai untuk prompt yang lebih berat atau mode reasoning.
- Output akhir tetap bergantung pada endpoint upstream yang dipanggil library ini.
- Library ini sekarang stateless; tidak ada fitur memory atau penyimpanan percakapan lokal.

## Minimal Example

Kalau ingin contoh paling ringkas untuk dipakai di project lain:

```python
from javaxFlash import FlashClient

client = FlashClient()
response = client.flash("Buat ringkasan tentang REST API", mode="fast")

if response.error:
    raise RuntimeError(response.error)

print(response.text)
```
