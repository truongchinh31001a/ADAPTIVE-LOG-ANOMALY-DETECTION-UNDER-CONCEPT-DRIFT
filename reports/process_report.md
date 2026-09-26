# Báo cáo toàn bộ quá trình hoàn thiện nghiên cứu

## 1. Điểm xuất phát

Ban đầu repository mới ở mức **research scaffold**: đã có cấu trúc package Python,
khung cấu hình S1--S6, interface detector, một baseline đơn giản và các thư mục dự kiến
cho dữ liệu/báo cáo. Phần code chứng minh được luồng xử lý cơ bản trên dữ liệu demo,
nhưng chưa đủ để tạo thành một nghiên cứu có thể bảo vệ vì còn thiếu:

- research gap được đối chiếu với các công trình adaptive/evolving-log gần nhất;
- dữ liệu BGL thật cùng checksum và provenance;
- parser đã kiểm định và cấu hình đóng băng;
- detector khoa học chính thay cho baseline kỹ thuật;
- EDA theo thời gian và chronological split rõ ràng;
- cơ chế update không đọc nhãn và không học anomaly thành normal;
- kịch bản S1--S6 có negative controls hợp lệ;
- thí nghiệm nhiều seed trên validation/test tách biệt;
- kết quả F1, Adaptation Delay, False Adaptation Rate và báo cáo trả lời RQ1--RQ3.

Do đó, công việc không dừng ở “viết thêm code”, mà chuyển repository thành một
**experimental research pipeline** có giả thuyết, protocol, bằng chứng và audit trail.

## 2. Chuyển đề tài thành câu hỏi nghiên cứu có thể kiểm chứng

### 2.1. Vấn đề của cách phát biểu ban đầu

Tên đề tài dùng “concept drift”, nhưng thay đổi tần suất/template trong log có thể chỉ là
thay đổi phân phối quan sát được, không nhất thiết là thay đổi thật của `P(Y|X)`. Nếu gọi
mọi thay đổi frequency là concept drift thì dễ bị phản biện về thuật ngữ.

Vì vậy nghiên cứu dùng cách gọi thận trọng hơn:

> Observable log-distribution drift gồm template-frequency drift và benign template
> emergence có khả năng làm suy giảm detector.

### 2.2. Đối chiếu related work

Literature matrix được mở rộng thành 19 công trình. Nhóm gần nhất gồm:

- DeepLog và các detector kế tiếp: chủ yếu cải thiện detector/representation;
- LogOnline: học normal sequence liên tục bằng online learning;
- OMLog: dùng MMD để quyết định online meta-learning hay offline inference;
- IDLLog: fine-tune khi tỷ lệ changed template vượt ngưỡng;
- EvLog/LogRobust: tăng robustness trước log evolution nhưng không lấy decision quality
  bằng AD/FAR làm trọng tâm.

Kết luận quan trọng là không được tuyên bố “adaptive log anomaly detection là mới”.
Khoảng trống cuối được thu hẹp thành:

> Một lớp quyết định detector-agnostic kết hợp loại, độ lớn, persistence và anomaly
> evidence để quyết định có nên/bao giờ update; đồng thời được đánh giá bằng F1, AD, FAR
> trên persistent drift, transient anomaly và no-drift controls.

Ba câu hỏi nghiên cứu được đóng lại:

- **RQ1:** Drift làm static detector suy giảm như thế nào?
- **RQ2:** Các tín hiệu quan sát có phân biệt persistent drift với anomaly burst/no drift
  không?
- **RQ3:** Selective adaptation có phục hồi detector mà không tạo false adaptation hoặc
  học anomaly thành normal không?

Artefact: `literature/literature_matrix.csv` và `literature/research_gap.md`.

## 3. Chốt dữ liệu và provenance

### 3.1. Nguồn dữ liệu

BGL được lấy từ bản phân phối Loghub/Zenodo. Cả archive và raw log được giữ nguyên trong
bronze zone và loại khỏi Git. Dataset registry ghi URL, ngày lấy, citation, điều kiện sử
dụng, kích thước và checksum.

Thông số đã xác minh:

- 4.747.963 dòng log;
- thời gian từ 03/06/2005 đến 04/01/2006;
- raw SHA-256:
  `666130b15ef44eb32fd02bd053e6c6e007c37696b5e7e8b9d8e45b729876a5d2`;
- 4.399.503 normal event và 348.460 anomaly event.

Artefact: `data/metadata/dataset_registry/bgl.yaml`.

### 3.2. Lý do chọn BGL

BGL có chronology dài, event-level anomaly label và đủ biến động template/tần suất để
kiểm tra detector sequence-based. Tuy nhiên nhãn BGL là system alert, không phải causal
annotation cho mọi distribution shift; vì vậy nó phù hợp để đo anomaly detection nhưng
không tự cung cấp ground truth “đây là concept drift”. Ground truth adaptation phải được
tạo bằng controlled scenarios.

## 4. Kiểm định và đóng băng parser

### 4.1. Lựa chọn parser

Drain3 0.9.11 được chọn làm parser chính vì có thiết kế streaming/online và có thể đóng
băng đầy đủ version/config. Parser chỉ nhận phần message, tuyệt đối không nhận timestamp,
host, severity hay anomaly label để tránh template leakage.

### 4.2. Parser validation

Ba similarity threshold 0,30/0,40/0,50 được thử trên:

1. BGL 2k structured sample có EventId tham chiếu;
2. chronological training prefix 100.000 dòng.

Threshold 0,40 đạt Adjusted Rand 0,9996 và V-measure 0,9948, tốt nhất trong ba lựa chọn.
Cấu hình cuối:

- Drain3 0.9.11;
- similarity threshold 0,40;
- depth 4;
- max children 100;
- parameterize numeric token;
- không lowercase message.

Full parse không có malformed/skipped row và tạo 1.823 cluster. Processed event Parquet
có SHA-256:
`03c06bbc4b2a50c152bc4c331d361351938168c9256a3d8f10815a424ccdbd9f`.

Artefact: `reports/parser_validation.md`, `configs/data/bgl.yaml` và
`data/silver/events/bgl_events.parquet`.

## 5. EDA theo thời gian và đóng băng data protocol

### 5.1. Vì sao không random split

Random split sẽ đưa template/regime tương lai vào train và làm mất chính hiện tượng cần
nghiên cứu. Toàn bộ xử lý được sort chronology ổn định; window và split được tạo một lần
trước mọi thí nghiệm.

### 5.2. Chọn window

Ba count-window 5.000, 10.000 và 20.000 event được so sánh chỉ trên train+validation.

- 5.000: median chỉ 3 template, quá thưa;
- 20.000: giảm một nửa temporal resolution;
- 10.000: median 5 template, là cân bằng giữa stability và response resolution.

Window được đóng băng ở 10.000 event. Vì arrival rate thay đổi lớn, cùng một count-window
có elapsed time không đều; AD chính vì vậy được định nghĩa theo số window và hạn chế này
được ghi trong threat-to-validity.

### 5.3. Chronological split

- Train: window 0--94, 950.000 event;
- Validation: 95--189, 950.000 event;
- Test: 190--474, 2.847.963 event;
- window 474 là cửa sổ partial duy nhất.

Training labels được dùng duy nhất để lọc normal event khi fit bán giám sát. Validation
và test labels chỉ đi vào evaluator.

### 5.4. Template emergence pool

Benign future templates phải:

- xuất hiện lần đầu trong target split;
- có zero anomaly label;
- có ít nhất 500 event;
- xuất hiện trong ít nhất hai window.

Pool validation và test rời nhau, ngăn việc chọn template test trong lúc tuning.

Artefact: `reports/eda_report.md`, `artifacts/bgl/eda/` và
`configs/data/bgl_heldout_templates.yaml`.

## 6. Xây detector khoa học chính

Baseline template-frequency ban đầu chỉ đủ làm smoke test. Detector chính được triển
khai theo DeepLog-style next-template prediction:

- chuỗi tạo theo từng host và chronology;
- context length 10;
- embedding + LSTM + linear output;
- anomaly nếu true next template không nằm trong top-k;
- fit offline chỉ trên normal training event;
- vocabulary expansion cho normal template mới;
- update bằng năm epoch và replay 20.000 event lịch sử.

Factory/interface cho phép policy không phụ thuộc nội bộ detector. Đây là điểm quan
trọng: đóng góp nằm ở adaptation decision layer, không nằm ở thiết kế LSTM.

Artefact: `src/adaptive_lad/detectors/deep_log.py` và
`configs/detector/deep_log.yaml`.

## 7. Thiết kế characterization và safe adaptation

### 7.1. Drift features

Mỗi window tạo:

- template-frequency vector;
- Jensen--Shannon divergence với frozen reference;
- số/tỷ lệ template mới;
- composite drift magnitude;
- persistence;
- detector anomaly evidence.

Reference được freeze sau warm-up. Sau một update hợp lệ, characterizer rebase bằng tập
candidate đã chấp nhận.

### 7.2. Policy

Cấu hình validation cuối:

- JS threshold 0,05;
- magnitude/persistence threshold 0,03;
- minimum persistence 6 window;
- adaptation buffer 3 window;
- rearm sau 3 stable window;
- recurrent template phải có mặt trong cả 3 window và ít nhất 200 event.

S5 burst được thiết kế dài đúng năm window. Vì vậy magnitude có thể rất mạnh nhưng chưa
đủ persistence 6 để update.

### 7.3. Ngăn học anomaly thành normal

Trước khi event vào buffer, `anomaly_label` và `drift_label` bị xóa. Candidate selection
chỉ dùng:

- normalized detector score;
- prediction;
- template novelty so với reference;
- recurrence theo window và số event.

Anomaly nền là 0,5%, tương đương 50 event/window và 150 event trong buffer ba window.
Ngưỡng recurrence 200 loại nhóm này mà không cần đọc label. Audit trail ghi observed,
selected, rejected, recurrent và recurrent-novel counts.

Trong diagnostics seed 1101:

- S1/S2: quan sát 30.000, chọn 29.850, loại 150;
- S3: chọn 29.525, loại 475;
- S4: chọn 29.607, loại 393;
- S5/S6: không có action.

Artefact: `src/adaptive_lad/adaptation/selection.py`,
`src/adaptive_lad/policies/strategies.py` và `configs/policy/default.yaml`.

## 8. Sửa lại semantics của S1--S6

### 8.1. Vấn đề của chronology tự nhiên

Pilot đầu dùng untreated chronological BGL làm S6. Static DeepLog có recall 1 nhưng
38.224 false positive, chứng minh đoạn chronology đó có regime shift tự nhiên. Gọi nó là
“no drift” sẽ làm ground truth sai.

### 8.2. Controlled stationary backbone

S1--S6 được chuyển sang stationary replay:

- chọn latest clean pre-evaluation window đủ đa dạng;
- replay real BGL identities/sequences;
- thêm cố định 0,5% anomaly nền;
- inject đúng một cơ chế cần kiểm tra.

Reference window validation là 92; test là 187.

### 8.3. Sáu kịch bản

- S1: sudden persistent frequency drift;
- S2: gradual persistent frequency drift;
- S3: sudden benign template emergence;
- S4: gradual benign template emergence;
- S5: transient anomaly burst, không được adapt;
- S6: no injected drift, không được adapt.

Với frequency drift, chỉ năm template phổ biến của reference bị tác động thay vì đảo
hàng trăm template lịch sử. Emergence injection thay thế event nhưng giữ nguyên số event
mỗi window.

Artefact: `configs/scenarios/bgl_validation/`, `configs/scenarios/bgl_test/` và
`src/adaptive_lad/drift/generator.py`.

## 9. Validation và đóng băng protocol

Validation dùng seed 101, 202, 303 và magnitude 0,25. Tổng cộng 72 run:

`6 scenarios x 4 methods x 3 seeds`.

Kết quả validation của proposed:

| Scenario | Overall F1 | Post-adaptation F1 | AD | FAR | Update |
|---|---:|---:|---:|---:|---:|
| S1 | .520 +/-.018 | .915 +/-.005 | 5 | 0 | 1 |
| S2 | .426 +/-.022 | .909 +/-.014 | 13 | 0 | 1 |
| S3 | .281 +/-.000 | .772 +/-.014 | 5 | 0 | 1 |
| S4 | .354 +/-.004 | .774 +/-.016 | 8 | 0 | 1 |
| S5 | .959 +/-.009 | n/a | n/a | 0 | 0 |
| S6 | .835 +/-.037 | n/a | n/a | 0 | 0 |

Sau đó toàn bộ threshold, seeds, magnitude, test horizon, parser, detector và policy được
đóng băng trong `configs/experiments/frozen_test_v1.yaml`. Test seed là
1101/1202/1303/1404/1505 và không được dùng để tune.

Artefact: `reports/validation_tuning.md` và `artifacts/bgl/validation_final/`.

## 10. Primary held-out test

Primary test được chạy riêng từng seed để mỗi phần hoàn tất được lưu an toàn. Mỗi seed
fit một DeepLog checkpoint, sau đó deep-copy checkpoint cho static/periodic/naive/
proposed trên cùng stream. Tổng số run:

`6 scenarios x 4 methods x 5 seeds = 120`.

### 10.1. Kết quả cuối

| Scenario | Static F1 | Periodic F1 | Naive F1 | Proposed F1 | Proposed post-update | AD | FAR |
|---|---:|---:|---:|---:|---:|---:|---:|
| S1 | .286 | .893 | .921 | .715 | .993 | 5.0 | 0 |
| S2 | .245 | .994 | .883 | .793 | .993 | 11.8 | 0 |
| S3 | .045 | .320 | .177 | .259 | .526 | 5.0 | 0 |
| S4 | .045 | .512 | .420 | .302 | .484 | 8.0 | 0 |
| S5 | .992 | .943 | .653 | .992 | n/a | n/a | 0 |
| S6 | .965 | .997 | .965 | .965 | n/a | n/a | 0 |

### 10.2. Diễn giải

- Static suy giảm rất mạnh ở S1--S4, trả lời RQ1.
- S1--S4 đạt persistence 6; S5 dừng ở 5; S6 ở 0, trả lời RQ2.
- Proposed phục hồi detector, FAR 0, một update ở S1--S4 và zero update ở S5--S6,
  trả lời RQ3.
- Proposed không có overall F1 cao nhất ở mọi nơi vì phải chờ sáu window. Đây là
  safety--latency trade-off, không phải kết quả cần che giấu.
- Naive nhanh nhưng false-adapt ở S3/S5; S5 F1 giảm còn 0,653.
- Periodic thường có F1 cao nhưng update 14 lần và FAR khoảng 0,20 ở controls.

Artefact: `artifacts/bgl/test_primary_fixed/` và `reports/analysis.md`.

## 11. Sensitivity và failure case

Sensitivity được định trước ở seed 1101, magnitude 0,10 và 0,40, tổng cộng 44 run.

- FAR của proposed vẫn bằng 0;
- S2 AD giảm từ 23 xuống 9 khi magnitude tăng;
- S4 AD giảm từ 14 xuống 7;
- S1/S3 giữ AD 5 do persistence floor;
- post-update frequency F1 vẫn 1,0;
- emergence post-update nằm khoảng 0,56--0,70.

Failure mode: S2 magnitude 0,40 update hai lần. Sau first rebase, strong gradual drift
làm signal ổn định rồi tăng lại đủ để rearm. Hai action đều nằm trong persistent-drift
region nên FAR vẫn 0, nhưng không thể tuyên bố “luôn đúng một update” ngoài primary
magnitude. Hướng tiếp theo là episode-aware rearm hoặc longer stable horizon, nhưng phải
được tune trong một protocol mới chứ không sửa sau test.

Artefact: `artifacts/bgl/test_sensitivity_fixed_seed1101/`.

## 12. Lỗi tái lập đã phát hiện và cách xử lý

Trong lúc tái chạy diagnostics, metrics gần giống nhưng stream SHA-256 của cùng seed S1
khác nhau. Nguyên nhân được truy đến đoạn:

```python
for template_id in set(sampled_templates):
```

Thứ tự `set` phụ thuộc `PYTHONHASHSEED`; mỗi template lại tiêu thụ RNG draw riêng nên
thứ tự này làm source-row sampling khác giữa process.

Fix:

```python
for template_id in sorted(set(sampled_templates)):
```

Sau đó:

1. thêm regression test chạy hai Python process với hash seed 1 và 2;
2. xác minh S3--S6 hash trùng giữa independent runs;
3. chạy lại toàn bộ 40 primary S1/S2;
4. chạy lại 16 sensitivity S1/S2;
5. chạy lại 2 diagnostic S1/S2;
6. hợp nhất theo run key, ghi source SHA trong merge manifest;
7. xác minh diagnostic và primary fixed có stream hash cùng metrics tuyệt đối giống.

Sự cố này là ví dụ quan trọng về lý do checksum và rerun audit cần thiết trong nghiên
cứu thực nghiệm.

## 13. Quality assurance và completion audit

Các cổng kiểm tra cuối:

- Ruff lint: pass;
- Ruff format: pass;
- mypy: pass;
- 27 YAML configs: hợp lệ;
- 29/29 unit/integration tests: pass;
- source coverage: 71%;
- final-result audit: 120 primary unique runs, 44 sensitivity runs, seed/method/scenario
  đầy đủ, replacement rows đúng source và proposed invariants đúng;
- figure regeneration: pass.

Các script quan trọng:

- `scripts/summarize_results.py`: merge, phát hiện duplicate và ghi merge manifest;
- `scripts/build_analysis.py`: tái tạo table/figure từ final results;
- `scripts/audit_final_results.py`: kiểm tra final-result invariants;
- `scripts/quality.ps1`: quality gates thông thường.

## 14. Danh sách artefact cuối

### Nghiên cứu

- `literature/literature_matrix.csv`
- `literature/research_gap.md`
- `docs/research_decisions.md`
- `docs/experiment_protocol.md`

### Dữ liệu và parser

- `data/metadata/dataset_registry/bgl.yaml`
- `configs/data/bgl.yaml`
- `data/silver/events/bgl_events.parquet`
- `data/silver/events/templates.parquet`
- `reports/parser_validation.md`
- `reports/eda_report.md`

### Thí nghiệm

- `artifacts/bgl/validation_final/`
- `artifacts/bgl/test_primary_fixed/`
- `artifacts/bgl/test_sensitivity_fixed_seed1101/`
- `artifacts/bgl/test_diagnostics_frequency_fixed_seed1101/`
- `artifacts/bgl/test_diagnostics_seed1101/`

### Báo cáo

- `reports/analysis.md`: số liệu đầy đủ và câu trả lời RQ1--RQ3;
- `reports/final_report.md`: bản tổng hợp tiếng Việt theo cấu trúc luận văn;
- `reports/process_report.md`: báo cáo toàn bộ quá trình này;
- `reports/figures/`: bốn hình kết quả;
- `reports/tables/drift_signal_summary.csv`.

## 15. Kết luận quá trình

Quá trình bắt đầu từ một code scaffold và kết thúc bằng một protocol có thể tái lập:
dữ liệu có provenance/checksum, parser được kiểm định, chronology được đóng băng,
detector khoa học được triển khai, update không đọc nhãn, negative controls có semantics
hợp lệ, validation/test tách biệt, nhiều seed, ba metric chính, sensitivity, audit và báo
cáo trực tiếp RQ1--RQ3.

Điểm mạnh nhất để bảo vệ không phải “mô hình luôn tốt nhất”, mà là:

1. bài toán và novelty được giới hạn đúng;
2. unsafe adaptation được biến thành đại lượng đo được bằng FAR;
3. transient anomaly/no drift được kiểm tra như negative controls;
4. mọi trade-off và failure case đều được công bố;
5. lỗi reproducibility thực tế đã được phát hiện bằng checksum, sửa và rerun có audit.

Nếu tiếp tục sang giai đoạn nộp/bảo vệ, công việc hợp lý tiếp theo là chuyển
`final_report.md` vào template luận văn của trường, dựng slide theo ba RQ, và chuẩn bị
phần hỏi đáp tập trung vào terminology, ground-truth design, label leakage, FAR, AD và
external validity.
