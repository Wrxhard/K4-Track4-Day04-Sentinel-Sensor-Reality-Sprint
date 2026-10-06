# Báo cáo cá nhân Lab: Track 4 - Day 3
**Người nộp:** Nguyễn Triều Vương - 2A202602422 (Implement Dynamic FPS)
**Nhóm:** Sentinel
**Lớp:** 3A · **Phòng:** H209 · **Track:** Multi-camera bandwidth profiling

---

## 1. Problem (Bài toán & Nền tảng)
* **Nền tảng:** Robot tự hành / Hệ thống xe ADAS giám sát môi trường.
* **Tính năng:** Phát hiện vật thể (Object Detection) thời gian thực thông qua nhiều luồng camera.
* **Sensor:** Đa camera truyền dữ liệu qua băng thông giới hạn.
* **Failure Case:** Nghẽn băng thông mạng dẫn đến rớt khung hình (drop frame), video delay và model AI không còn nhận diện chuẩn xác (do không có frame mới).
* **Claim:** Kết hợp **Dynamic FPS** và **Adaptive Resolution** giúp giảm áp lực băng thông, đảm bảo vẫn duy trì FPS mượt ở những cảnh quan trọng và độ chính xác của AI không giảm đáng kể.

## 2. Method (Phương pháp giải quyết)
* **Tài liệu tham khảo:** [DeepStream: Bandwidth Efficient Multi-Camera Video Streaming](https://arxiv.org/pdf/2306.15129). 
* **Setup Benchmark:** Code demo local (`demo/backend/app.py`). Dataset: Giao thông thực tế qua webcam.
* **Paper cho biết:** Hệ thống tự động giảm FPS và Resolution vùng nền giúp giảm nửa băng thông, nhưng limitation là dễ lỡ vật thể di chuyển chéo vào khung hình.
* **Cơ chế triển khai của nhóm:** 
  * **Dynamic FPS (Vương phụ trách):** Theo dõi mức độ thay đổi giữa các frame. Nếu dưới ngưỡng (cảnh tĩnh), drop FPS từ 30fps xuống 5fps. Khi phát hiện thay đổi mạnh (có phương tiện chạy), đẩy FPS về 30fps.
  * **Adaptive Resolution (Phúc phụ trách):** Nén mờ (blur) những vị trí trên khung ảnh không có vật thể để giảm Bitrate frame đó.

## 3. Benchmark (Kết quả thử nghiệm)
* **Metric tự đo:** 1. FPS, Độ trễ (Latency); 2. Tỉ lệ rớt khung hình (Drop frame); 3. CPU Load.
* **Kết quả:** So với Baseline bị rớt frame, phương pháp Kết hợp (Dynamic FPS + Adaptive Res) loại bỏ hẳn hiện tượng Drop frame, duy trì Latency ổn định ở mức ~200ms, đồng thời giảm mức chiếm dụng CPU Edge. Hệ thống truyền dẫn mượt mà dù băng thông giả lập bị giới hạn.

## 4. Failure Case (Phân tích lỗi)
* **Quan sát trực tiếp:** **Nhóm quan sát được** trên màn hình Demo, khi một xe máy chạy ngang qua rìa màn hình, xảy ra hiện tượng Latency tăng, AI bị delay detection mất 1-2 frame.
* **Suy luận nguyên nhân:** Quá trình chuyển đổi trạng thái của Dynamic FPS (từ tĩnh sang động) có độ trễ nhỏ (lag 1 frame). Kết hợp với vùng biên bị Adaptive Resolution làm mờ, khiến AI phải mất thời gian lấy nét để đẩy FPS lên.

## 5. Engineering Decision (Quyết định kỹ thuật & Trade-off)
* **Trade-off thực tế:** Kỹ thuật này lý tưởng cho camera giao thông tĩnh ngã tư, nhưng **không phù hợp** trên xe ô tô ADAS cao tốc vì rủi ro delay 1 frame là rất lớn.
* **Đề xuất cải tiến (Vương):** Cải thiện cơ chế Wake-up của Dynamic FPS bằng "Safety Zones" (Kênh an toàn 2 bên mép). Có chuyển động nhẹ ở rìa lập tức đẩy FPS lên 30 ngay, không chờ xe vào giữa khung hình.

---
*(Bản nộp này sử dụng dữ liệu và nghiên cứu chung của nhóm Sentinel)*
