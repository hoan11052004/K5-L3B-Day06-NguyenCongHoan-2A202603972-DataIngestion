# Day 06 · Data Ingestion Engineering

**Học viên:** Nguyễn Công Hoàn  
**MSSV:** 2A202603972  
**Lớp:** L3B  
**Repo:** `K5-L3B-Day06-NguyenCongHoan-2A202603972-DataIngestionEngineering`  
**Báo cáo cá nhân:** [report/individual/2A202603972_NguyenCongHoan.md](report/individual/2A202603972_NguyenCongHoan.md)  

---

## 1. Giới thiệu tổng quan

Dự án hiện thực trọn vẹn quy trình **Data Ingestion Engineering** biến tài liệu kỹ thuật dài thành kho tri thức ngữ nghĩa (Semantic Knowledge Store) cho AI agent, lưu trữ bền vững trong cơ sở dữ liệu **PostgreSQL 16 + pgvector** (kèm fallback ChromaDB), và đánh giá so sánh có kiểm soát ba chiến lược ingestion trên bộ benchmark 20 câu hỏi (15 Dev / 5 Test) theo đúng 5 tiêu chí của môn học.

| 📄 Dữ liệu thực tế | 🧩 Ba chiến lược | 🎯 Bộ Benchmark | ⚙️ Vector Database |
|---|---|---|---|
| **73 trang nội dung** (144.872 ký tự) từ Sách Deep Learning (Chương 5: ML cơ bản) | Strategy A (Fixed-size 500/50)<br>Strategy B (Paragraph max 800)<br>Strategy C (Paragraph + Filter) | **20 câu hỏi** có gold evidence (15 Dev / 5 Test, 4 câu filter metadata) | **PostgreSQL 16 + pgvector** (4096-dim `qwen3-embedding-8b` qua OpenRouter) |

---

## 2. Kết quả thực nghiệm

```text
==================================================================
KẾT QUẢ ĐÁNH GIÁ BENCHMARK RETRIEVAL TRÊN 3 CHIẾN LƯỢC
==================================================================
Strategy   | Split  | Hit@1           | Evidence Hit@3     | Chunks   | Time (s)  
---------------------------------------------------------------------------
A          | dev    | 12/15 (80.0%)   | 15/15 (100.0%)     | 347      | 73.93     
A          | test   | 2/5 (40.0%)     | 4/5 (80.0%)        | 347      | 73.93     
A          | all    | 14/20 (70.0%)   | 19/20 (95.0%)      | 347      | 73.93     
B          | dev    | 13/15 (86.7%)   | 15/15 (100.0%)     | 230      | 88.90     
B          | test   | 2/5 (40.0%)     | 5/5 (100.0%)       | 230      | 88.90     
B          | all    | 15/20 (75.0%)   | 20/20 (100.0%)     | 230      | 88.90     
C          | dev    | 12/15 (80.0%)   | 13/15 (86.7%)      | 230      | 88.90     
C          | test   | 2/5 (40.0%)     | 5/5 (100.0%)       | 230      | 88.90     
C          | all    | 14/20 (70.0%)   | 18/20 (90.0%)      | 230      | 88.90     
```

### Đánh giá 5 Khía cạnh chất lượng (Rubric 100 điểm)
1. **Độ chính xác truy xuất (Retrieval Accuracy):** Strategy B đạt điểm tuyệt đối **100% Evidence Hit@3** trên cả tập Dev và tập Test (20/20 câu hỏi).
2. **Tính mạch lạc (Chunk Coherence):** Strategy B và C đạt điểm tối đa **2.00 / 2.0** (so với 0.40/2 của Strategy A do A bị cắt đứt từ/câu cơ học).
3. **Tính hữu dụng metadata (Metadata Usefulness):** 100% bản ghi kiểm tra (15/15) có metadata đúng và đủ; tỷ lệ tuân thủ filter đạt **100%** (1/1 ở Test set, 4/4 trên toàn bộ benchmark).
4. **Chất lượng Grounding:** Strategy B và C đạt **2.00 / 2.0** trên tập test độc lập (5/5 câu đạt mức 2, cung cấp đủ ngữ cảnh và điều kiện để trả lời).
5. **Tác động chiến lược (Strategy Impact):** Strategy B giảm **33.7% số lượng chunk** so với A (từ 347 xuống 230 chunks), tiết kiệm dung lượng lưu trữ vector và cải thiện chất lượng grounding rõ rệt.

---

## 3. Cấu trúc mã nguồn

```text
├── STUDENT.md                                      # Thông tin học viên và commit chốt
├── README.md                                       # Hướng dẫn setup, cấu trúc dự án và kết quả
├── data/
│   ├── dlbookvn_chap05.pdf                         # Corpus 75 trang (73 trang nội dung)
│   └── manifest.json                               # Manifest chi tiết nguồn và số ký tự
├── benchmark/
│   └── benchmark.json                              # Bộ 20 câu hỏi (15 Dev / 5 Test)
├── artifacts/
│   └── experiment_log.csv                          # Nhật ký thực nghiệm 3 chiến lược
├── results/
│   ├── benchmark_summary.json                      # Thống kê Hit@1, Hit@3
│   ├── traces_strategy_A.json                      # Trace top-3 của Strategy A
│   ├── traces_strategy_B.json                      # Trace top-3 của Strategy B
│   ├── traces_strategy_C.json                      # Trace top-3 của Strategy C
│   └── manual_audit.json                           # Đánh giá thủ công Coherence & Grounding
├── report/individual/
│   └── 2A202603972_NguyenCongHoan.md               # Báo cáo cá nhân chi tiết
├── src/ & starter/src/
│   ├── models.py                                   # Data models (DocumentPage, Chunk, Hit, Trace)
│   ├── ingestion.py                                # Đọc PDF, trích xuất text, chuẩn hóa Unicode
│   ├── chunking.py                                 # Fixed-size và By-paragraph chunking
│   ├── embeddings.py                               # Embedder OpenRouter API & local fallback
│   ├── store.py                                    # PgVectorStore (PostgreSQL + pgvector)
│   ├── evaluation.py                               # Đánh giá Hit@1, Hit@3 và xuất trace
│   └── run.py                                      # Điều phối toàn bộ pipeline
└── starter/
    ├── docker-compose.yml                          # PostgreSQL 16 + pgvector container
    └── .env                                        # Cấu hình API key và Database URL
```

---



