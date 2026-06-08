# Báo Cáo Cá Nhân - Pipeline RAG Pháp Luật Ma Túy

## Tổng Quan

Dự án xây dựng pipeline RAG trả lời câu hỏi về pháp luật ma túy Việt Nam và một số tin tức liên quan. Phần cá nhân đã hoàn thành đầy đủ từ thu thập dữ liệu, chuẩn hóa tài liệu, indexing, retrieval, reranking đến generation có citation.

Kết quả chính:

| Hạng mục | Kết quả |
|---|---|
| Văn bản pháp luật gốc | 5 tài liệu PDF/DOC |
| Bài báo đã crawl | 6 bài báo |
| Markdown chuẩn hóa | 11 file |
| Chunks đã tạo | 1,481 chunks |
| Embedding model | Cohere `embed-multilingual-v3.0` |
| Embedding dimension | 1024 |
| Vector store chính | Weaviate Cloud, collection `DrugLawDocs` |
| Lexical search | BM25 local trên `chunks.json` |
| Reranker | Jina `jina-reranker-v2-base-multilingual` |
| Fallback retrieval | PageIndex Vectorless, có local BM25 fallback |
| Chatbot generation | LLM qua OpenRouter/OpenAI, có extractive fallback khi API rate limit |

## Task 1 - Thu Thập Văn Bản Pháp Luật

Yêu cầu: thu thập tối thiểu 3 văn bản pháp luật về ma túy/chất cấm và lưu vào `data/landing/legal/`.

Đã thu thập 5 tài liệu:

| File | Nội dung chính |
|---|---|
| `73_2021_QH14(2).doc` | Luật Phòng, chống ma túy 2021 |
| `luat-phong-chong-ma-tuy-2021.pdf` | Bản PDF Luật Phòng, chống ma túy 2021 |
| `135-vbhn-vpqh.pdf` | Bộ luật Hình sự hợp nhất, có các điều về tội phạm ma túy |
| `105.2021.ND.CP.doc` | Nghị định 105/2021/NĐ-CP về quản lý chất ma túy, tiền chất |
| `109_2021_ND-CP_497098.doc` | Nghị định 109/2021/NĐ-CP liên quan cơ sở y tế/cai nghiện |

Kết quả: đạt yêu cầu vì có nhiều hơn 3 văn bản pháp luật và bao phủ cả luật, nghị định, bộ luật hình sự.

## Task 2 - Crawl Bài Báo

Yêu cầu: crawl tối thiểu 5 bài báo về nghệ sĩ/người nổi tiếng Việt Nam liên quan đến ma túy, lưu metadata và nội dung vào `data/landing/news/`.

Đã triển khai trong `src/task2_crawl_news.py`:

- Đọc URL từ `data/landing/news/urls_to_crawl.txt`.
- Crawl nội dung từng bài.
- Lưu kết quả thành JSON gồm URL, tiêu đề, thời điểm crawl, nội dung markdown và số từ.

Kết quả đã có 6 bài báo:

| File | Nguồn/nội dung chính |
|---|---|
| `article_01.json` | Thanh Niên, vụ Chi Dân, An Tây, Trúc Phương |
| `article_02.json` | Dân trí, vụ Andrea Aybar/An Tây và Chi Dân |
| `article_03.json` | VOV, truy tố trong chuyên án VN10 |
| `article_04.json` | Pháp Luật TP.HCM, chuyên án VN10 |
| `article_05.json` | Tin tức liên quan nghệ sĩ và ma túy |
| `article_06.json` | Tin tức liên quan nghệ sĩ và ma túy |

Kết quả: đạt yêu cầu vì có 6 bài báo, có metadata và nội dung đủ để đưa vào pipeline.

## Task 3 - Convert Sang Markdown

Yêu cầu: convert toàn bộ dữ liệu trong `data/landing/` sang Markdown và lưu vào `data/standardized/`.

Đã triển khai trong `src/task3_convert_markdown.py`:

- Với PDF/DOC/DOCX: dùng MarkItDown khi phù hợp.
- Với `.doc` cũ: dùng Microsoft Word COM để convert tạm sang `.docx`, sau đó extract paragraph/table.
- Với JSON bài báo: chuyển metadata và nội dung sang Markdown có header chuẩn.
- Xử lý lỗi encoding/mojibake tiếng Việt khi convert tài liệu Word/PDF.

Kết quả:

| Nhóm | Số file Markdown | Thư mục |
|---|---:|---|
| Legal | 5 | `data/standardized/legal/` |
| News | 6 | `data/standardized/news/` |
| Tổng | 11 | `data/standardized/` |

Test đã chạy: Task 3 pass các kiểm tra riêng về convert và output Markdown.

## Task 4 - Chunking & Indexing

Yêu cầu: chọn chunking strategy, embedding model và index toàn bộ Markdown vào vector store.

Đã triển khai trong `src/task4_chunking_indexing.py`.

Chunking:

```python
CHUNKING_METHOD = "recursive"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
```

Lý do chọn:

- `RecursiveCharacterTextSplitter` an toàn cho dữ liệu hỗn hợp gồm văn bản luật dài và bài báo ngắn.
- `chunk_size=800` đủ giữ ngữ cảnh điều luật hoặc đoạn báo.
- `chunk_overlap=120` giảm mất thông tin ở ranh giới chunk.

Embedding:

```python
EMBEDDING_PROVIDER = "cohere"
EMBEDDING_MODEL = "embed-multilingual-v3.0"
EMBEDDING_DIM = 1024
```

Lý do chọn:

- Máy không có GPU nên dùng API embedding.
- Dữ liệu tiếng Việt, cần model multilingual.
- Vector 1024 chiều phù hợp cho dense retrieval.

Vector store:

```python
VECTOR_STORE = "weaviate"
COLLECTION_NAME = "DrugLawDocs"
```

Kết quả:

- Input: 11 Markdown documents.
- Output: 1,481 chunks.
- Đã embed 1,481 vectors bằng Cohere.
- Đã index vào Weaviate Cloud collection `DrugLawDocs`.
- Cache local tại `data/index/chunks.json`, `data/index/embeddings.npy`, `data/index/index_meta.json`.

## Task 5 - Semantic Search

Yêu cầu: viết module dense retrieval trên vector store.

Đã triển khai trong `src/task5_semantic_search.py`:

```python
def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    ...
```

Luồng hoạt động:

1. Embed query bằng Cohere `embed-multilingual-v3.0`.
2. Query Weaviate collection `DrugLawDocs` bằng `near_vector`.
3. Trả về list chunks gồm `content`, `score`, `metadata`.
4. Nếu Weaviate lỗi tạm thời, fallback local cosine search từ `embeddings.npy`.

Test mẫu:

| Query | Kết quả mong đợi |
|---|---|
| `hình phạt tàng trữ trái phép chất ma túy` | Trả về chunk Điều 249 trong Bộ luật Hình sự |
| `Luật phòng chống ma túy quy định gì về cai nghiện?` | Trả về chunk Luật Phòng, chống ma túy |
| `nghệ sĩ nào liên quan đến ma túy?` | Trả về các bài báo về Chi Dân, An Tây, Trúc Phương |

## Task 6 - Lexical Search BM25

Yêu cầu: viết module lexical search, mặc định dùng BM25.

Đã triển khai trong `src/task6_lexical_search.py`:

```python
def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    ...
```

Cách làm:

- Đọc corpus từ `data/index/chunks.json`.
- Tokenize tiếng Việt theo hướng đơn giản nhưng có xử lý accent-stripped tokens để tăng khả năng match.
- Dùng `rank-bm25` với `BM25Okapi`.
- Trả về chunks có `content`, `score`, `metadata`, sort giảm dần theo score.

Vai trò trong hệ thống:

- Bù cho semantic search ở các truy vấn có keyword rất cụ thể như tên riêng, số điều luật, tên nghị định.
- Ví dụ: `Chi Dân`, `An Tây`, `Điều 249`, `Nghị định 105/2021/NĐ-CP`.

## Task 7 - Reranking

Yêu cầu: viết module rerank để chấm lại độ liên quan của retrieval candidates.

Đã triển khai trong `src/task7_reranking.py`.

Model chính:

```text
jina-reranker-v2-base-multilingual
```

Lý do chọn:

- Multilingual, phù hợp tiếng Việt.
- Chạy qua Jina API, không cần GPU.
- Phù hợp để rerank kết quả sau hybrid retrieval.

Ngoài Jina cross-encoder rerank, module còn có helper:

- RRF để merge nhiều retriever.
- MMR để tăng diversity nếu cần.
- Fallback giữ nguyên score ban đầu nếu Jina API lỗi.

## Task 8 - PageIndex Vectorless Fallback

Yêu cầu: tích hợp PageIndex Vectorless làm fallback retrieval.

Đã triển khai trong `src/task8_pageindex_vectorless.py`.

Luồng hoạt động:

- Chuẩn bị manifest tài liệu tại `data/index/pageindex_documents.json`.
- Nếu PageIndex API hoạt động, query qua PageIndex.
- Nếu chưa upload được hoặc API lỗi, fallback local BM25 trên corpus Markdown/chunks.

Vai trò trong pipeline:

- Không phải vector store chính.
- Không lưu embedding chunks.
- Chỉ dùng làm fallback khi hybrid retrieval không đủ tốt hoặc cần kiểm tra phương án vectorless.

## Task 9 - Retrieval Pipeline Hoàn Chỉnh

Yêu cầu: kết hợp semantic search, lexical search, rerank và fallback PageIndex.

Đã triển khai trong `src/task9_retrieval_pipeline.py`:

```python
def retrieve(query: str, top_k: int = 5, score_threshold: float = 0.3) -> list[dict]:
    ...
```

Luồng:

```text
Query
  -> Semantic Search bằng Cohere + Weaviate
  -> Lexical Search bằng BM25
  -> Merge bằng RRF
  -> Optional Jina Rerank
  -> Nếu top score thấp: PageIndex fallback
  -> Return top_k chunks
```

UI hiện có toggle `Bật rerank` để demo hai cấu hình:

- Bật rerank: hybrid + Jina reranker.
- Tắt rerank: hybrid/RRF trực tiếp.

## Task 10 - Generation Có Citation

Yêu cầu: reorder context, inject prompt, gọi LLM và trả lời có citation.

Đã triển khai trong `src/task10_generation.py`.

Các điểm chính:

- `reorder_for_llm()` sắp xếp chunks theo pattern giảm “lost in the middle”.
- Citation label được làm đẹp:
  - `[Thanh Niên, 2024]`
  - `[VOV, 2026]`
  - `[Bộ luật Hình sự 2015, Điều 249]`
- Prompt yêu cầu chỉ trả lời dựa trên context.
- Có guardrail cho prompt injection và câu ngoài phạm vi.
- Có fallback extractive khi LLM provider bị rate limit.
- Có enrich nguồn luật cho câu hỏi kiểu “An Tây vi phạm điều luật nào?” để tổng hợp nguồn báo và Bộ luật Hình sự.

Ví dụ output:

```text
Ca sĩ Chi Dân và người mẫu An Tây bị khởi tố, bắt tạm giam về hành vi tổ chức sử dụng trái phép chất ma túy [Thanh Niên, 2024]. Riêng người mẫu An Tây còn bị khởi tố thêm về hành vi tàng trữ trái phép chất ma túy [Thanh Niên, 2024].
```

## Tổng Kết Kỹ Thuật

Pipeline end-to-end:

```text
PDF/DOC/JSON
  -> Markdown
  -> Chunking
  -> Cohere embedding
  -> Weaviate index

User query
  -> Semantic search + BM25
  -> RRF merge
  -> Optional Jina rerank
  -> PageIndex fallback nếu cần
  -> LLM/extractive generation
  -> Answer có citation + source documents
```

Các file chính:

| Task | File |
|---|---|
| Task 1 | `src/task1_collect_legal_docs.py` |
| Task 2 | `src/task2_crawl_news.py` |
| Task 3 | `src/task3_convert_markdown.py` |
| Task 4 | `src/task4_chunking_indexing.py` |
| Task 5 | `src/task5_semantic_search.py` |
| Task 6 | `src/task6_lexical_search.py` |
| Task 7 | `src/task7_reranking.py` |
| Task 8 | `src/task8_pageindex_vectorless.py` |
| Task 9 | `src/task9_retrieval_pipeline.py` |
| Task 10 | `src/task10_generation.py` |

Hệ thống hiện đã sẵn sàng tích hợp vào group project chatbot và evaluation pipeline.
