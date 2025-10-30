# Chat Memory Bot

**Chat Memory Bot**, kullanıcıyla yaptığı konuşmalardan öğrenen, uzun vadeli bilgileri koruyan ve gerektiğinde gerçek zamanlı web araması yaparak güncel bilgilere erişebilen bir **LLM tabanlı akıllı asistan** projesidir.

Bu proje, **Jetlink AI Engineer Assessment v1.3** kapsamında geliştirilmiş olup, sıfırdan modüler bir yapay zekâ mimarisi sunar.  
Her bileşen kendi sorumluluk alanına sahiptir ve proje, **LangChain gibi framework’lere bağımlı olmadan**, doğrudan Python tabanlı olarak tasarlanmıştır.

---

## Özellikler

### 1. Hafıza Sistemi (Memory Architecture)
Chat Memory Bot, insan benzeri hafıza sistemini iki katmanda uygular:

- **STM (Short-Term Memory)**  
  - Aktif konuşma sırasında geçici bilgileri saklar.  
  - Token limitine ulaşıldığında otomatik özetleme veya temizleme yapar.  
  - Diyalog bağlamını koruyarak model çağrılarını güçlendirir.

- **LTM (Long-Term Memory)**  
  - Kalıcı kullanıcı bilgilerini SQLite veritabanında saklar.  
  - `google_embed.py` üzerinden embedding işlemleri yapılır.  
  - `retrieval.py` dosyası, semantik benzerlik sorgularını yönetir.  
  - Böylece model, geçmiş konuşmalardan bağlamsal olarak “hatırlayabilir”.

---

### 2. Web Araması (Real-Time Knowledge Access)
- Model, **güncel bilgi gerektiğinde** otomatik olarak web araması yapılması gerektiğini belirler.  
  Bu durumda sadece şu şekilde bir yanıt döner:

SEARCH_NEEDED: <arama sorgusu>

- Ardından `src/web/search.py` modülü devreye girer:
- `ddgs` (DuckDuckGo Search API) üzerinden arama yapılır.
- `enrich_results_with_snippets()` ile sayfa özetleri alınır.
- Sonuçlar biçimlendirilip **WEB CONTEXT** olarak modele geri gönderilir.

Bu yapı sayesinde model hem geçmiş bağlamı (LTM) hem de güncel web verilerini harmanlayarak en uygun cevabı üretir.

---

### 3. Çok Formatlı Dosya Girişi (Multimodal Input)
Kullanıcılar, metin dışında **dosya veya görsel** de yükleyebilir.  
Desteklenen formatlar:
- PDF (`PyMuPDF`)
- TXT (`utf-8` parsing)
- DOCX (`python-docx`)
- Görsel (PNG / JPG / JPEG)

Yüklenen dosyalar `src/utils/file_parser.py` içinde işlenir:
1. Dosya tipi tespit edilir.  
2. İçerik okunur ve sadeleştirilir.  
3. Model çağrısına **ek bağlam (document context)** olarak dahil edilir.

Bu sayede kullanıcı PDF veya Word dosyasını yüklediğinde, model içerikten anlayarak yanıt verir.

---

### 4. Seç & Sor Etkileşimi
- Her mesajın altında **“Seç & Sor”** butonu bulunur.  
- Kullanıcı geçmişteki bir mesajı seçip doğrudan o metin üzerinden soru yöneltebilir.  
- Seçilen içerik otomatik olarak alıntılanır (`> quote` biçiminde).  
- Kullanıcı isterse **“İptal”** butonuyla seçimi geri alabilir.

Bu özellik, doküman temelli veya uzun konuşmalarda doğrudan odaklanmayı kolaylaştırır.

---

### 5. Modüler Kod Mimarisi
Proje tamamen modüler Python yapısına göre tasarlandı:


chat-memory-bot/
├── src/

│ ├── app.py # Streamlit arayüz ve kontrol akışı

│ ├── config.py # Genel yapılandırmalar

│ │

│ ├── llm/

│ │ └── gemini_client.py # Google Gemini API istemcisi

│ │

│ ├── memory/

│ │ ├── stm.py # Kısa süreli bellek (Session State)

│ │ ├── ltm_store.py # Kalıcı hafıza (SQLite)

│ │ ├── retrieval.py # Embedding tabanlı benzerlik arama

│ │ └── policy.py # Hafıza politikaları ve eşik değerleri

│ │

│ ├── embed/

│ │ └── google_embed.py # Google Embedding işlemleri

│ │

│ ├── chat/

│ │ └── store.py # Konuşma kayıt yönetimi

│ │

│ ├── web/

│ │ └── search.py # DuckDuckGo tabanlı web arama

│ │

│ ├── utils/

│ │ ├── text.py # Yardımcı metin fonksiyonları

│ │ ├── pii.py # PII (kişisel veri) tespiti ve temizleme

│ │ ├── similarity.py # Benzerlik ölçümü (cosine, dot)

│ │ 

│ │

│ ├── prompts/

│ │ ├── compuse.py # Sistem promptları

│ │ └── system.txt # Sistem tanımları

│ │

│ └── tests/

│ ├── test_ltm_store.py

│ ├── test_retrieval.py

│ └── test_similarity.py

│

├── data/

│ ├── uploads/ # Kullanıcı yüklediği dosyalar

│ └── memory.db # Kalıcı hafıza veritabanı

│

├── scripts/

│ ├── init_db.py # Veritabanı kurulum betiği

│ ├── export_memories.py # Hafıza dışa aktarma

│ └── seed_memories.py # Örnek veri yükleme

│

├── Dockerfile

├── docker-compose.yml

├── requirements.txt

├── .env

└── README.md


---

### 6. Docker Desteği

#### `Dockerfile`

dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8501

CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]

docker-compose.yml

version: "3.9"

services:
  app:
    build: .
    container_name: chat-memory-bot
    ports:
      - "8501:8501"
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./src:/app/src
    restart: unless-stopped

Mimari Akış

USER MESSAGE
    │
    ▼
 STM  →  geçici bağlam
    │
    ▼
 LTM  →  embedding tabanlı hafıza araması
    │
    ▼
Gemini LLM
    │
    ├─ Eğer güncel bilgi gerekliyse:
    │     SEARCH_NEEDED: <query>
    │         │
    │         ▼
    │     Web Search (DuckDuckGo)
    │         │
    │         ▼
    │     WEB CONTEXT oluşturulur
    │
    ▼
 Nihai Yanıt (STM + LTM + WEB)


Örnek Kullanım Senaryoları

| Kullanıcı Sorusu                                | Beklenen Davranış                                 |
| ----------------------------------------------- | ------------------------------------------------- |
| “TÜİK’in son açıkladığı enflasyon oranı nedir?” | Web araması yapılır, güncel bilgiyle yanıt döner. |
| “Bu PDF’in içeriğini özetle.”                   | Dosya okunur, model içerikten özet üretir.        |
| “Ali ile ilgili geçmiş notları hatırlat.”       | LTM üzerinden ilgili içerik çağrılır.             |
| “Bugün dolar kaç TL?”                           | Web araması tetiklenir, kaynaklı cevap üretilir.  |


 Kurulum
1. Ortam Değişkenleri

    .env dosyasına ekleyin:

      GOOGLE_API_KEY=your_gemini_api_key_here

        GEMINI_MODEL=gemini-2.0-flash

2. Docker Üzerinden Çalıştırma

    docker compose up -d

3. Uygulamayı Açın

    localhost:8501


Test Örnekleri

| Kullanıcı Sorusu                                | Beklenen Davranış                                 |
| ----------------------------------------------- | ------------------------------------------------- |
| “TÜİK’in son açıkladığı enflasyon oranı nedir?” | Web araması yapılır, güncel bilgiyle yanıt döner. |
| “Bu PDF’in içeriğini özetle.”                   | Dosya okunur, model içerikten özet üretir.        |
| “Ali ile ilgili geçmiş notları hatırlat.”       | LTM üzerinden ilgili içerik çağrılır.             |
| “Bugün dolar kaç TL?”                           | Web araması tetiklenir, kaynaklı cevap üretilir.  |


Kullanılan Teknolojiler

| Alan      | Teknoloji          |
| --------- | ------------------ |
| LLM       | Google Gemini API  |
| Embedding | Google Embeddings  |
| Web Arama | DuckDuckGo (ddgs)  |
| Hafıza    | STM + LTM (SQLite) |
| Arayüz    | Streamlit          |
| Konteyner | Docker + Compose   |
| Test      | PyTest             |
| Dil       | Python 3.12        |

Teknik Notlar

-  LLLM çağrıları doğrudan google.generativeai SDK'sı ile yapılır.

-  Web araması için ddgs (v9.6.1) sürümü kullanılmıştır.

-  Tüm hafıza verileri data/memory.db içinde saklanır.

-  Kod yapısı test edilebilir, bağımsız ve genişletilebilir olacak şekilde tasarlanmıştır.


## Projeyi Çalıştırma (Hızlı Başlangıç)

Projeyi klonlayıp yerel ortamda veya Docker üzerinden kolayca çalıştırabilirsiniz.

### Adım Adım Kurulum

#### 1. Reponun klonlanması
bash

git clone https://github.com/Emirhan-Denizyol/Jetlink_Project.git

cd chat-memory-bot

#### 2. Ortam değişkeni dosyasının oluşturulması
cp .env.example .env

#### 3. .env dosyasına Gemini API anahtarınızı ekleyin
GOOGLE_API_KEY=your_gemini_api_key_here

GEMINI_MODEL=gemini-2.0-flash

#### 4. Docker imajını oluşturup çalıştırın
docker compose up -d --build

#### 5. Uygulama başlatıldıktan sonra, tarayıcınızdan şu adrese giderek erişebilirsiniz:
http://localhost:8501
```
