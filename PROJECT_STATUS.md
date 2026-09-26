# Trạng thái dự án

Cập nhật: 25/09/2026.

## Hoàn tất và đã kiểm chứng

- Research gap được chốt thành lớp quyết định *whether/when to adapt* độc lập detector,
  đánh giá bằng F1, Adaptation Delay, False Adaptation Rate và negative controls.
- Literature matrix gồm 19 nguồn; novelty statement không tuyên bố adaptive LAD nói
  chung là mới vì đã có LogOnline, OMLog và IDLLog.
- BGL raw 4.747.963 dòng đã đăng ký SHA-256; bản processed có 4.399.503 normal,
  348.460 anomaly và 1.823 template.
- Parser chính Drain3 0.9.11 được đóng băng (similarity .40, depth 4, max children 100)
  và có parser-validation report.
- EDA thời gian đóng băng window 10.000 event; chronological split train 0--94,
  validation 95--189, test 190--474.
- Detector chính là DeepLog-style next-template LSTM; template-frequency giữ làm
  engineering baseline.
- Adaptation buffer không chứa ground-truth, lọc anomaly bằng score và recurrence;
  selected/rejected counts được audit theo từng action.
- S1--S6 dùng stationary replay của log BGL thật để có ground truth xác định; raw
  chronology được giữ làm ecological analysis, không giả định là no-drift.
- Validation hoàn tất 72 run (3 seed). Primary held-out test hoàn tất 120 run
  (5 seed), sensitivity 44 run và diagnostic telemetry 6 run.
- Audit phát hiện và sửa phụ thuộc `PYTHONHASHSEED` trong frequency generator; có
  regression test chéo process và rerun toàn bộ 40 primary + 16 sensitivity + 2
  diagnostics bị ảnh hưởng.
- Báo cáo `reports/analysis.md` trả lời trực tiếp RQ1--RQ3, nêu cả trade-off và failure
  mode; bốn figure cùng bảng signal được tái tạo bởi `scripts/build_analysis.py`.

## Kết quả chính

- Static DeepLog giảm từ F1 .965 ở S6 xuống .286/.245 ở frequency drift và .045 ở
  emergence drift.
- Proposed đạt post-adaptation F1 .993/.993/.526/.484 trên S1--S4.
- Proposed có FAR 0 trên cả năm test seed, đúng một update ở mọi primary S1--S4 và
  không update ở S5--S6.
- Trade-off: proposed phản ứng chậm hơn naive/periodic nên overall F1 không luôn cao
  nhất; đổi lại không false-adapt và chỉ dùng một update thay vì 14.

## Artefact chính

- Frozen config: `configs/experiments/frozen_test_v1.yaml`
- Final primary: `artifacts/bgl/test_primary_fixed/`
- Final sensitivity: `artifacts/bgl/test_sensitivity_fixed_seed1101/`
- Final analysis: `reports/analysis.md`
- Validation record: `reports/validation_tuning.md`
- Research decisions: `docs/research_decisions.md`

## Việc ngoài phạm vi hiện tại

- Lặp lại trên dataset/domain thứ hai để tăng external validity.
- Đánh giá thêm parser/detector family khác như robustness study.
- Viết/chuyển nội dung báo cáo vào mẫu luận văn chính thức và slide bảo vệ.
