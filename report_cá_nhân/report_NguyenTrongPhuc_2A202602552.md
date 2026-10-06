# Báo cáo cá nhân Lab: Track 4 - Day 4
**Người nộp:** Nguyễn Trọng Phúc - 2A202602552 (Project Lead & Implement Adaptive Resolution)
**Nhóm:** Sentinel
**Lớp:** 3A · **Phòng:** H209 · **Track:** Multi-camera bandwidth profiling

---

## 1. Problem (Bài toán & Nền tảng)
* **Nền tảng:** Robot tự hành / Hệ thống xe ADAS giám sát môi trường.
* **Tính năng:** Phát hiện vật thể (Object Detection) thời gian thực thông qua nhiều luồng camera.
* **Sensor:** Đa camera truyền dữ liệu qua băng thông giới hạn.
* **Failure Case:** Nghẽn băng thông mạng. Khi số lượng camera tăng, việc truyền nhiều luồng video cùng lúc ở độ phân giải và FPS cố định gây quá tải băng thông, dẫn đến tình trạng rớt gói tin, tăng độ trễ, hoặc giảm chất lượng đột ngột khiến mô hình AI nhận diện sai.
* **Claim:** Giải pháp kết hợp **Dynamic FPS** và **Adaptive Resolution** (ROI nén background) giúp giảm mạnh dung lượng truyền tải mà không làm giảm đáng kể độ chính xác của AI.

## 2. Method (Phương pháp giải quyết)
* **Tài liệu tham khảo:** [DeepStream: Bandwidth Efficient Multi-Camera Video Streaming](https://arxiv.org/pdf/2306.15129).
* **Setup Benchmark:** Code demo nội bộ. Lệnh chạy: `python demo/backend/app.py`. Dataset: Webcam/Video giả lập cảnh giao thông.
* **Paper cho biết:** Phương pháp này giảm data hiệu quả nhưng hạn chế (limitation) ở việc theo dõi vật thể đột ngột ở biên ảnh.
* **Cơ chế triển khai của nhóm:** 
  * **Dynamic FPS (Vương phụ trách):** Giảm FPS ở cảnh tĩnh (còn 5fps), tăng lên 30fps khi có hoạt động.
  * **Adaptive Resolution (Phúc phụ trách):** Nhận diện nhanh vùng có vật thể (ROI) tại Edge. Nén/giảm chất lượng vùng Background để tiết kiệm bit truyền tải, giữ nguyên chất lượng ở vùng ROI.

## 3. Benchmark (Kết quả thử nghiệm)
* **Metric tự đo:** 1. FPS, Độ trễ (Latency); 2. Tỉ lệ rớt khung hình (Drop frame); 3. CPU Load.
* **Kết quả:** So với Baseline bị rớt frame trầm trọng, phương pháp Kết hợp (Dynamic FPS + Adaptive Res) giúp duy trì FPS ổn định, giảm trễ xuống mức ~200ms và loại bỏ hẳn Drop frame khi mạng nghẽn. CPU load cũng giảm còn khoảng 55%.

## 4. Failure Case (Phân tích lỗi)
* **Quan sát trực tiếp (Từ Log Demo):** Ở giây thứ 12 của clip thử nghiệm, một xe máy lao vào từ mép khung hình với tốc độ cao. **Nhóm quan sát được** có sự gia tăng Detection Latency cục bộ (trễ nhận diện) do model lỡ 1-2 frame đầu.
* **Suy luận nguyên nhân:** Do Frame trước tĩnh, Adaptive Resolution nén quá mạnh vùng rìa. Vật thể mới lao vào vùng mờ nên model thiếu tự tin. FPS cũng chưa kịp scale up.

## 5. Engineering Decision (Quyết định kỹ thuật & Trade-off)
* **Trade-off thực tế:** Áp dụng tốt cho camera giám sát đứng im. **Không phù hợp** cho xe chạy cao tốc vì độ trễ 1-2 frame ở biên có thể gây tai nạn.
* **Cải tiến của Phúc (Đã cập nhật code):** Mở rộng vùng đệm ROI (Buffer Padding) khoảng 20-30 pixels xung quanh vật thể kết hợp theo dõi chuyển động, giúp giữ độ sắc nét ở vùng viền.

---
*(Bản nộp này sử dụng dữ liệu và nghiên cứu chung của nhóm Sentinel)*
