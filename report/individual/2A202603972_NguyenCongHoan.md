# Báo cáo cá nhân — Day 6: Data Ingestion Engineering

**Học viên:** Nguyễn Công Hoàn  
**MSSV:** 2A202603972  
**Lớp:** L3B  

---

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:**
  - **Chủ đề:** Giáo trình nền tảng *Machine Learning cơ bản* (Chương 5 của cuốn sách kinh điển *Deep Learning* - Ian Goodfellow, Yoshua Bengio, Aaron Courville).
  - **Nguồn & Quyền:** Bản dịch tiếng Việt mã nguồn mở phục vụ học thuật phi thương mại do cộng đồng `dlbookvietnam` thực hiện (`starter/data/dlbookvn_chap05.pdf`).
  - **Số trang vật lý:** 75 trang.
  - **Quy tắc tính trang nội dung:** Loại bỏ 2 trang đầu (trang 1: bìa & mục lục tổng quát; trang 2: danh mục đề mục chi tiết); giữ lại **73 trang nội dung chuyên sâu** từ trang 3 đến trang 75. Tổng số ký tự sau chuẩn hóa: **144.872 ký tự** (vượt xa ngưỡng tối thiểu 30 trang theo yêu cầu của đề bài). Manifest chi tiết được lưu tại `data/manifest.json`.

- **Chuẩn hóa, lỗi và giới hạn:**
  - **Chuẩn hóa:** Áp dụng Unicode NFC (`unicodedata.normalize('NFC', text)`), loại bỏ các ký tự ẩn/zero-width space (`\u200b`, `\ufeff`, `\u00a0`), chuẩn hóa ngắt dòng (`\r\n` -> `\n`), hợp nhất các dòng bị ngắt giữa câu trong cùng một đoạn văn mà không phá vỡ ranh giới phân tách đoạn (`\n\n`).
  - **Lỗi & Giới hạn:** Tài liệu PDF chứa nhiều công thức toán học dạng LaTeX nhúng và vector ký hiệu đặc biệt. Một số ký hiệu toán học chỉ số dưới hoặc chữ Hy Lạp khi trích xuất có thể bị lược bớt hoặc mất định dạng; pipeline tập trung vào việc bảo toàn tối đa ngữ nghĩa văn bản tiếng Việt và các thuật ngữ kỹ thuật cốt lõi.

- **Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí:**
  - **Embedding model:** `qwen/qwen3-embedding-8b` thông qua OpenRouter API (hỗ trợ đa ngữ vượt trội, số chiều: **4096 dimensions**). Đồng thời hệ thống có module dự phòng `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions) chạy local.
  - **Vector store:** PostgreSQL 16.16 kết hợp extension `pgvector 0.8.7` chạy Docker container (`day6_student_starter`, cổng local `55433`).
  - **Metric đo khoảng cách:** Cosine distance (`<=>` trong pgvector, tương ứng với `1.0 - (embedding <=> query_vec)` làm điểm tương đồng Cosine Similarity).
  - **Lệnh chạy:** Kích hoạt môi trường và chạy `python -m src.run` (từ thư mục `starter/`) hoặc `python -m starter.src.run` (từ thư mục gốc).
  - **Chi phí:** ~0.005 USD (OpenRouter token API cho việc embed toàn bộ chunks và benchmark queries).

- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:**
  - **Metadata bắt buộc:** `document_id` ("dlbookvn-chap05"), `source` ("starter/data/dlbookvn_chap05.pdf"), `page` (số trang vật lý 1-indexed trong PDF), `strategy` ("A" / "B" / "C").
  - **Trường lọc bổ sung (`section`):** Trích xuất tự động từ tiêu đề mục cấp 2 của sách (ví dụ: `5.1 Learning algorithms`, `5.2 Capacity, Overfitting, Underfitting`, `5.3 Siêu tham số và tập xác thực`, `5.7 Các thuật toán học có giám sát`, v.v.).
  - **Nguồn giá trị & Lý do chọn:** Tiêu đề mục xuất hiện rõ ràng ở đầu mỗi phần của tài liệu. Việc lọc theo `section` giúp AI agent giới hạn phạm vi tìm kiếm vào đúng chủ đề kỹ thuật mong muốn, giảm thiểu hiện tượng hallucination và triệt tiêu các đoạn văn gây nhiễu từ các chương mục khác.

---

## Cấu hình và benchmark

- **A / B / C (tham số cụ thể, khác biệt duy nhất B–C):**
  - **Strategy A (Fixed-size Window):** Cửa sổ trượt cố định kích thước `chunk_size = 500` ký tự, bước trượt `overlap = 50` ký tự. Lưu trữ metadata đầy đủ nhưng không áp dụng lọc metadata khi truy xuất.
  - **Strategy B (By-paragraph Structure-aware):** Phân chia theo ranh giới đoạn văn tự nhiên (`\n\n`), gộp các đoạn ngắn và cắt các đoạn dài tại ranh giới câu (`.` hoặc `\n`) với ngưỡng tối đa `max_size = 800` ký tự. Cùng metadata với A, không áp dụng lọc metadata khi truy xuất.
  - **Strategy C (By-paragraph + Metadata Filter):** Cấu trúc chunking, kích thước và vector embedding **hoàn toàn đồng nhất với Strategy B** (so sánh có kiểm soát). Khi câu hỏi có chỉ định trường lọc `filter: {"section": "..."}`, câu truy vấn SQL sẽ kích hoạt điều kiện `WHERE section = %s` để lọc chính xác phạm vi. Nếu câu hỏi không có filter, hệ thống chạy truy vấn tương tự Strategy B.

- **≥20 câu: phân chia ≥15 dev / ≥5 test, câu metadata filter và cách kiểm chứng evidence:**
  - **Tổng số câu hỏi:** 20 câu hỏi (15 câu tập Dev, 5 câu tập Test) được biên soạn trước khi thử nghiệm, lưu tại `benchmark/benchmark.json`.
  - **Phân loại câu hỏi:** Gồm đầy đủ các nhóm câu hỏi: trực tiếp (`truc_tiep`), diễn đạt lại (`dien_dat_lai`), điều kiện/ngoại lệ (`dieu_kien`), và câu hỏi phân biệt bằng metadata (`filter_metadata`).
  - **Câu metadata filter:** Có 4 câu có điều kiện lọc (3 câu ở Dev: `q03`, `q06`, `q10`; 1 câu ở Test: `q18`). Giá trị filter được xác định từ trước ngữ cảnh truy vấn, không đưa đáp án hay gold page vào query/filter.
  - **Kiểm chứng evidence:** 100% câu hỏi (20/20 câu) đều có chuỗi `evidence_quote` được kiểm chứng tự động bằng script đối chiếu trực tiếp với trang nguồn `gold_page` trong tệp PDF gốc, bảo đảm bằng chứng tồn tại và hỗ trợ đầy đủ cho `expected_answer`.

- **Tiêu chí chọn chiến lược đã chốt trước khi xem test:**
  - Tiêu chí ưu tiên số 1: **Evidence Hit@3 trên tập Dev** (phải đạt ≥ 80%).
  - Tiêu chí ưu tiên số 2: **Grounding Quality và Chunk Coherence** (không bị cắt cụt câu/từ để agent có đủ ngữ cảnh trả lời).
  - Tiêu chí ưu tiên số 3: **Hiệu quả tài nguyên** (số lượng chunk tối ưu, giảm chi phí lưu trữ vector và thời gian tìm kiếm).

---

## Kết quả

### Bảng 1: Chỉ số Retrieval & Tài nguyên

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian ingest | Chi phí API |
|---|---|---|---|---|---|---|
| **A** (Fixed 500/50) | Dev | 12/15 (80.0%) | 15/15 (100.0%) | 347 | 73.93s | ~0.002$ |
| **A** (Fixed 500/50) | Test | 2/5 (40.0%) | 4/5 (80.0%) | 347 | 73.93s | ~0.002$ |
| **A** (Fixed 500/50) | **All** | **14/20 (70.0%)** | **19/20 (95.0%)** | 347 | 73.93s | ~0.002$ |
| **B** (Paragraph 800) | Dev | 13/15 (86.7%) | 15/15 (100.0%) | 230 | 88.90s | ~0.002$ |
| **B** (Paragraph 800) | Test | 2/5 (40.0%) | 5/5 (100.0%) | 230 | 88.90s | ~0.002$ |
| **B** (Paragraph 800) | **All** | **15/20 (75.0%)** | **20/20 (100.0%)** | 230 | 88.90s | ~0.002$ |
| **C** (Paragraph + Filter) | Dev | 12/15 (80.0%) | 13/15 (86.7%) | 230 | 88.90s | ~0.002$ |
| **C** (Paragraph + Filter) | Test | 2/5 (40.0%) | 5/5 (100.0%) | 230 | 88.90s | ~0.002$ |
| **C** (Paragraph + Filter) | **All** | **14/20 (70.0%)** | **18/20 (90.0%)** | 230 | 88.90s | ~0.002$ |

### Bảng 2: Đánh giá Chất lượng Thủ công (Manual Audit)

| Strategy | Coherence trung bình /2 (n=10) | Metadata đủ và đúng (n/N, n=15) | Filter tuân thủ (n/N) | Grounding 0/1/2 (số câu) và trung bình /2 (n=5) |
|---|---|---|---|---|
| **A** | **0.40 / 2.0** (0: 6, 1: 4, 2: 0) | 15/15 (100%) | N/A | [0: 1, 1: 1, 2: 3] -> **1.40 / 2.0** |
| **B** | **2.00 / 2.0** (0: 0, 1: 0, 2: 10) | 15/15 (100%) | N/A | [0: 0, 1: 0, 2: 5] -> **2.00 / 2.0** |
| **C** | **2.00 / 2.0** (0: 0, 1: 0, 2: 10) | 15/15 (100%) | **1/1 (100% test)**, **4/4 (100% all)** | [0: 0, 1: 0, 2: 5] -> **2.00 / 2.0** |

- **Đường dẫn trace và nhãn thủ công:**
  - Trace top-3 đầy đủ: `results/traces_strategy_A.json`, `results/traces_strategy_B.json`, `results/traces_strategy_C.json`.
  - Tóm tắt benchmark: `results/benchmark_summary.json`.
  - Bảng nhãn kiểm định thủ công: `results/manual_audit.json`.
- **Cách chọn mẫu audit:**
  - *Coherence:* Chọn cố định 10 vị trí trang đại diện trải đều 73 trang nội dung (`Pages 3, 4, 7, 10, 16, 25, 29, 39, 51, 66`), đối chiếu ranh giới cắt của Chunk đầu tiên giữa Strategy A và Strategy B.
  - *Metadata & Grounding:* Kiểm tra toàn bộ 5 câu test độc lập (`q16` đến `q20`) với 3 kết quả top-ranked tương ứng của mỗi chiến lược (tổng cộng 45 lượt đánh giá metadata và 15 lượt đánh giá grounding).

---

## Phân tích và kết luận

### So sánh A–B và B–C

1. **So sánh A–B (Tác động của chiến lược Chunking):**
   - **Chất lượng ngữ nghĩa và Coherence:** Strategy A sử dụng sliding window cố định 500 ký tự cắt cơ học qua giữa các từ và câu văn (ví dụ: cắt đứt từ `bởi` thành `bở`, `đại lượng` thành `đại`, `cải thiện` thành `cả`), khiến điểm Coherence chỉ đạt **0.40 / 2.0**. Ngược lại, Strategy B tôn trọng ranh giới đoạn văn và ranh giới kết thúc câu, đạt điểm Coherence tuyệt đối **2.00 / 2.0**.
   - **Retrieval Hit Rate:** Strategy B giảm được **33.7% số lượng chunk** (từ 347 xuống 230 chunk), nhưng tỷ lệ Evidence Hit@3 lại tăng từ **95.0% lên 100.0%** trên toàn bộ 20 câu hỏi (trên Test set tăng từ 80.0% lên 100.0%). Điều này chứng minh rằng việc giữ trọn vẹn ngữ cảnh đoạn văn giúp vector embedding mô tả chính xác nội dung ngữ nghĩa hơn nhiều so với các đoạn văn bị chặt nhỏ.
   - **Grounding Quality:** Điểm Grounding của Strategy B đạt **2.00 / 2.0** (so với 1.40 / 2.0 của A), vì các chunk của B cung cấp trọn vẹn luận điểm và điều kiện kèm theo mà không bắt LLM phải đoán phần bị cắt.

2. **So sánh B–C (Tác động của Metadata Filtering):**
   - **Khả năng cách ly nhiễu:** Khi áp dụng metadata filter cho câu hỏi nhắm mục tiêu (như câu `q18` về dịch máy trong section `5.1`), Strategy C lọc bỏ 100% các đoạn văn gây nhiễu từ các section khác, bảo đảm top-3 chỉ chứa đúng phạm vi kỹ thuật liên quan.
   - **Đánh đổi của Metadata Filter:** Trên tập Dev, 2 câu hỏi (`q06` về Định lý No Free Lunch và `q10` về Kernel Trick) có nội dung mang tính liên ngành hoặc được thảo luận rải rác giữa các đề mục. Khi bộ lọc metadata quá cứng nhắc (`section = ...`), không gian tìm kiếm bị thu hẹp quá mức khiến các đoạn văn bổ trợ nằm ở ranh giới section bị loại trừ, dẫn đến Hit@3 Dev của C giảm xuống 86.7% (so với 100% của B).

### Phân tích 2 ví dụ lỗi điển hình

- **Ví dụ lỗi 1 (Câu `q16` - Strategy A - Thất bại do cắt cụt ngữ cảnh):**
  - *Câu hỏi:* "Các yếu tố quyết định để đánh giá một thuật toán ML có tốt hay không là khả năng của nó khi làm gì?"
  - *Nguồn gold:* Trang 18, section `5.2 Capacity, Overfitting, Underfitting`.
  - *Hiện tượng:* Strategy A trượt hoàn toàn trang 18 trong top-3 (Rank 1 rơi vào Trang 8, Rank 2 rơi vào Trang 25, Rank 3 rơi vào Trang 8). Nguyên nhân là cửa sổ 500 ký tự đã chia cắt câu mở đầu ("Các yếu tố quyết định...") khỏi mệnh đề điều kiện sai số kiểm thử và sai số huấn luyện ở đoạn dưới, làm giảm cosine similarity. Trong khi đó, Strategy B gộp trọn vẹn đoạn văn vào chunk `dlbookvn-chap05_p18_pb000`, đạt Hit@3 thành công ở Rank 3 (`score = 0.6144`).
- **Ví dụ lỗi 2 (Câu `q17` - Strategy A - Thất bại về Grounding Quality):**
  - *Câu hỏi:* "Thủ thuật chọn hàm lõi trong SVM được đánh giá là một công cụ mạnh mẽ bởi mấy lý do?"
  - *Nguồn gold:* Trang 51.
  - *Hiện tượng:* Strategy A tìm được trang 51 ở Rank 3, nhưng chunk `dlbookvn-chap05_p51_fa001` bị cắt cụt ngay giữa chừng lý do thứ nhất, hoàn toàn làm biến mất lý do thứ hai ("Thứ hai, hàm lõi thường có chi phí tính toán hiệu quả hơn..."). Nếu AI agent sinh câu trả lời dựa trên chunk này, câu trả lời sẽ bị thiếu thông tin nghiêm trọng (chỉ đạt 1/2 điểm Grounding). Trong khi đó, Strategy B giữ trọn vẹn cả 2 lý do trong cùng 1 chunk, giúp grounding đạt trọn vẹn 2/2 điểm.

### Chiến lược được chọn, đánh đổi và điều kiện áp dụng

- **Chiến lược được chọn:** **Strategy B (Structure-aware / Paragraph Chunking)** là chiến lược tổng thể xuất sắc nhất cho bài toán này, kết hợp cơ chế lọc mềm (soft filtering / re-ranking) của Strategy C khi người dùng xác định rõ phạm vi.
- **Đánh đổi (Trade-offs):** Strategy B yêu cầu thuật toán chunking tinh vi hơn (phải phân tích cú pháp câu và đoạn văn), nhưng bù lại tiết kiệm 33.7% chi phí lưu trữ vector, tăng tốc độ truy vấn cơ sở dữ liệu và mang lại điểm retrieval Hit@3 tuyệt đối 100%.
- **Điều kiện áp dụng:** Strategy B phù hợp tối đa cho các tài liệu có cấu trúc văn bản học thuật, sách giáo trình, tài liệu đặc tả phần mềm (spec) và quy trình nghiệp vụ.

### Hạn chế của dữ liệu, nhãn, test nhỏ và đo đạc

- Tập test gồm 5 câu là kích thước mẫu tương đối nhỏ, có thể mang sai số thống kê nhất định khi suy rộng.
- Tài liệu chứa một số công thức toán học bị giản lược khi trích xuất text thuần từ PDF.
- Việc đo thời gian phụ thuộc vào độ trễ mạng khi gọi API OpenRouter; tuy nhiên cơ chế lưu trữ pgvector local chạy cực kỳ ổn định (< 5ms cho mỗi truy vấn tìm kiếm vector).

### Định hướng cải tiến mở rộng

Cấu hình D (Semantic / Adaptive Chunking theo biến thiên ngữ nghĩa):

Thông số: Cắt theo từng câu, đo Cosine similarity giữa 2 câu liên tiếp, ngắt chunk tự động khi độ tương đồng tụt dưới similarity_threshold = 0.75.
Tác dụng: Thay vì chia theo ký tự cứng nhắc, hệ thống tự động nhận biết khi nào bài giảng chuyển sang chủ đề mới để ngắt chunk, bảo đảm một chunk chỉ chứa đúng 1 chủ đề thuần nhất.

