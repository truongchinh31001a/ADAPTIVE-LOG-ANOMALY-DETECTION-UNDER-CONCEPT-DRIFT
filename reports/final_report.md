# Phát hiện bất thường log thích nghi dưới sự trôi phân phối

## Tóm tắt

Các mô hình phát hiện bất thường log thường được huấn luyện trên một giai đoạn lịch sử
và suy giảm khi hệ thống sinh template mới hoặc thay đổi tần suất sự kiện. Cập nhật liên
tục có thể cải thiện độ thích nghi nhưng đồng thời tốn chi phí và có nguy cơ học nhầm
anomaly thành normal. Nghiên cứu này xây dựng một lớp quyết định độc lập detector để trả
lời hai câu hỏi vận hành: **có nên thích nghi hay không, và nên thích nghi khi nào**.

Phương pháp kết hợp Jensen--Shannon divergence của phân phối template, tỷ lệ template
mới, độ lớn và độ bền của thay đổi, cùng bằng chứng anomaly từ detector. Cơ chế cập nhật
dùng buffer ba cửa sổ đã loại bỏ nhãn, chỉ giữ mẫu điểm thấp hoặc template mới xuất hiện
lặp lại; mọi mẫu được chọn/loại đều được audit. Thực nghiệm sử dụng BGL, Drain3 và một
DeepLog-style LSTM trên sáu kịch bản có ground truth, so sánh static, periodic, naive và
proposed. Cấu hình được chọn trên validation ba seed rồi đánh giá một lần trên năm test
seed đóng băng.

Trên S1--S4, proposed tăng F1 tổng thể so với static từ 0,215 đến 0,549 điểm tuyệt đối và
đạt post-adaptation F1 0,993/0,993/0,526/0,484. Phương pháp cập nhật đúng một lần ở mọi
primary persistent-drift run, không cập nhật ở transient/no-drift controls và đạt FAR
0. Kết quả không khẳng định proposed luôn có F1 tổng thể cao nhất: persistence guard làm
tăng Adaptation Delay so với naive/periodic. Đóng góp chính là trade-off an toàn--độ trễ
có thể đo, tái lập và bảo vệ được, không phải một detector mới hay tuyên bố SOTA.

## 1. Bài toán và khoảng trống nghiên cứu

DeepLog và các mô hình kế tiếp thường tối ưu representation/detector. LogOnline học
online liên tục; OMLog dùng MMD để quyết định online meta-learning hay offline inference;
IDLLog kích hoạt fine-tuning khi tỷ lệ template thay đổi vượt ngưỡng. Vì vậy nghiên cứu
không tuyên bố adaptive LAD là mới. Khoảng trống được giới hạn ở bằng chứng thực nghiệm
cho một lớp quyết định detector-agnostic có đủ ba tính chất:

1. đặc trưng hóa đồng thời template emergence và frequency drift;
2. phân biệt persistent normal-regime change với transient anomaly/no drift;
3. đánh giá hành vi policy bằng Adaptation Delay và False Adaptation Rate bên cạnh F1.

Khái niệm được dùng thận trọng là **observable log-distribution drift**. Thay đổi phân
phối template không mặc nhiên chứng minh thay đổi trong quan hệ nhãn `P(Y|X)`.

## 2. Câu hỏi nghiên cứu

- **RQ1:** Drift quan sát được làm suy giảm static detector đến mức nào?
- **RQ2:** Tổ hợp tín hiệu có phân biệt persistent drift với anomaly burst/no drift
  không?
- **RQ3:** Selective adaptation có phục hồi detector mà không tạo unnecessary update
  hay học anomaly thành normal không?

## 3. Dữ liệu và tiền xử lý

BGL raw gồm 4.747.963 dòng từ Loghub, trải từ 03/06/2005 đến 04/01/2006. SHA-256 raw là
`666130b15ef44eb32fd02bd053e6c6e007c37696b5e7e8b9d8e45b729876a5d2`. Drain3 0.9.11
được đóng băng ở similarity 0,40, depth 4, max children 100. Parser tạo 1.823 template,
4.399.503 event normal và 348.460 event anomaly; không có dòng lỗi.

EDA chỉ dùng train+validation để chọn count window 10.000 event. Chronological split là
train 0--94, validation 95--189 và test 190--474. Detector fit bán giám sát bằng normal
label trong train; validation/test label chỉ đi vào evaluator. Template emergence của
validation và test lấy từ hai pool normal future-template rời nhau.

Raw chronology BGL chứa nhiều regime shift tự nhiên nên không thể được gọi là no-drift.
S1--S6 dùng stationary replay của một cửa sổ BGL sạch đủ đa dạng, cộng anomaly nền cố
định 0,5%. Cách này hy sinh một phần realism để có negative control và ground truth
adaptation rõ ràng; raw chronology chỉ là ecological analysis.

## 4. Phương pháp

### 4.1. Detector

Detector chính là LSTM dự đoán next-template theo chuỗi từng host, quyết định anomaly
theo top-k. Vocabulary có thể mở rộng khi template normal mới được chấp nhận. Update
fine-tune năm epoch với replay 20.000 event lịch sử. Template-frequency detector chỉ là
engineering baseline.

### 4.2. Characterization và policy

Mỗi cửa sổ sinh ra `new_template_rate`, Jensen--Shannon divergence, drift magnitude,
persistence và anomaly evidence. Proposed yêu cầu magnitude/structural signal bền sáu
cửa sổ; S5 chỉ dài năm cửa sổ. Hysteresis chỉ cho phép một action trong một regime liên
tục và rearm sau ba cửa sổ ổn định.

Buffer cập nhật giữ ba cửa sổ gần nhất nhưng xóa `anomaly_label` và `drift_label` trước
khi lưu. Template điểm cao phải xuất hiện trong cả ba cửa sổ và ít nhất 200 event. Vì
anomaly nền chỉ đóng góp 150 event trong buffer đầy đủ, nó không đủ recurrence để được
học thành normal. Update audit ghi số observed, selected, rejected và recurrent template.

### 4.3. Kịch bản và baseline

- S1/S2: frequency drift sudden/gradual.
- S3/S4: benign template emergence sudden/gradual.
- S5: transient anomaly burst, adaptation bị cấm.
- S6: no injected drift, adaptation bị cấm.
- Baseline: static, periodic mỗi năm cửa sổ, naive single-alarm và proposed.

Primary magnitude là 0,25. Validation seed 101/202/303 tách khỏi test seed
1101/1202/1303/1404/1505. Sensitivity dùng seed 1101, magnitude 0,10 và 0,40. Mỗi method
trong một seed nhận bản sao của cùng checkpoint và cùng scenario stream.

## 5. Kết quả

### 5.1. RQ1

Static đạt F1 0,992 ở S5 và 0,965 ở S6 nhưng giảm còn 0,286/0,245 trên frequency drift
và 0,045/0,045 trên emergence. Vì vậy cả hai drift mechanism đều phá vỡ mô hình frozen;
unseen benign template gây tác động mạnh nhất.

### 5.2. RQ2

Trên diagnostics seed 1101, divergence nền xấp xỉ 0,0025. S1--S4 đạt persistence 6 và
trigger một action. S5 có peak magnitude/anomaly evidence rất cao nhưng chỉ persistence
5 nên bị từ chối. S6 có peak magnitude 0,00285 và persistence 0. Magnitude đơn lẻ không
đủ; persistence và transient guard là thành phần quyết định để tránh false adaptation.

### 5.3. RQ3

| Scenario | Static F1 | Proposed F1 | Post-adaptation F1 | AD | FAR | Updates |
|---|---:|---:|---:|---:|---:|---:|
| S1 | .286 | .715 | .993 | 5.0 | 0 | 1 |
| S2 | .245 | .793 | .993 | 11.8 | 0 | 1 |
| S3 | .045 | .259 | .526 | 5.0 | 0 | 1 |
| S4 | .045 | .302 | .484 | 8.0 | 0 | 1 |
| S5 | .992 | .992 | n/a | n/a | 0 | 0 |
| S6 | .965 | .965 | n/a | n/a | 0 | 0 |

Periodic thường có F1 cao nhưng thực hiện 14 update và FAR khoảng 0,20 ở S5/S6. Naive
phản ứng sớm nhưng false-adapt ở S3/S5 và làm S5 F1 giảm còn 0,653. Proposed bảo toàn
đúng static F1 ở controls và FAR 0, đổi lại overall F1 thấp hơn các policy nhanh trong
một số persistent scenarios vì phải chờ bằng chứng sáu cửa sổ.

Trong diagnostics primary seed 1101, mỗi action quan sát 30.000 event. S1/S2 loại đúng
150 anomaly nền; S3/S4 loại 475/393 event và vẫn giữ recurrent benign emergence. Không
có evaluation label trong buffer. Sensitivity giữ FAR 0, nhưng S2 magnitude 0,40 rearm
và update hai lần — một failure mode được báo cáo công khai.

## 6. Độ tin cậy và tái lập

Primary cuối gồm 120 run unique; validation 72 run; sensitivity 44 run. Audit phát hiện
frequency generator từng phụ thuộc `PYTHONHASHSEED` do lặp qua `set`. Lỗi được sửa bằng
stable order, có regression test chéo process, và toàn bộ 40 primary, 16 sensitivity,
2 diagnostic run bị ảnh hưởng đã chạy lại. S3--S6 chỉ được giữ sau khi stream SHA-256
trùng giữa các process độc lập.

Mọi cấu hình, seed, input-frame checksum, resolved detector/policy config và environment
được ghi trong manifest. Quality gates cuối gồm Ruff, formatting, mypy, YAML validation
và unit/integration tests.

## 7. Hạn chế

- Chỉ có một dataset HPC, một parser chính và một detector family.
- Stationary replay tạo ground truth tốt nhưng không giữ mọi phụ thuộc của chronology tự
  nhiên.
- Năm test seed đủ mô tả biến thiên nhưng chưa đủ cho khẳng định thống kê mạnh.
- Post-adaptation F1 emergence còn thấp; policy quyết định đúng lúc nhưng update operator
  chưa học đầy đủ context của template hoàn toàn mới.
- AD được báo cáo theo window; vì count-window có duration không đều, diễn giải theo thời
  gian thực cần thêm elapsed-time mapping.

## 8. Kết luận

Nghiên cứu chứng minh static DeepLog suy giảm mạnh dưới observable log-distribution
drift và một policy đa tín hiệu có thể phục hồi mô hình với FAR 0 trên protocol đã kiểm
soát. Kết quả ủng hộ selective adaptation như một lớp quyết định an toàn hơn continuous
hay single-alarm update, đồng thời chỉ ra chi phí độ trễ và giới hạn emergence. Đây là
một kết luận hẹp, có thể tái lập và phù hợp để bảo vệ; không phải tuyên bố universal hay
SOTA.

## Tài liệu cốt lõi

- Drain: https://doi.org/10.1109/ICWS.2017.13
- DeepLog: https://doi.org/10.1145/3133956.3134015
- Concept drift survey: https://doi.org/10.1145/2523813
- Loghub: https://doi.org/10.1109/ISSRE59848.2023.00071
- LogOnline: https://doi.org/10.1109/ASE56229.2023.00043
- OMLog: https://arxiv.org/abs/2410.16612
- IDLLog: https://doi.org/10.1016/j.infsof.2026.108199

Chi tiết số liệu, figure và threat-to-validity đầy đủ nằm trong `reports/analysis.md`.
