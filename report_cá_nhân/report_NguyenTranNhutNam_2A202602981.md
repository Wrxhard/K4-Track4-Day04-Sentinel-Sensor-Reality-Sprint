# Báo cáo cá nhân Lab: Track 4 - Day 3
**Người nộp:** Nguyễn Trần Nhựt Nam - 2A202602981 (Phát triển AI, tìm Paper, Tối ưu)
**Nhóm:** Sentinel
**Lớp:** 3A · **Phòng:** H209 · **Track:** Multi-camera bandwidth profiling

---

## 1. Problem (Bài toán & Nền tảng)
* **Nền tảng:** Robot tự hành / Hệ thống xe ADAS giám sát môi trường.
* **Tính năng:** Phát hiện vật thể (Object Detection) thời gian thực thông qua nhiều luồng camera.
* **Sensor:** Đa camera truyền dữ liệu qua băng thông giới hạn.
* **Failure Case:** Nghẽn băng thông mạng. Việc truyền nhiều luồng video cùng lúc gây quá tải băng thông, dẫn đến drop frame và AI lỡ vật thể.
* **Claim:** Kết hợp **Dynamic FPS** và **Adaptive Resolution** (ROI nén background) giúp giảm băng thông, duy trì độ chính xác của mô hình nhận diện.

## 2. Method (Phương pháp giải quyết)
* **Tài liệu tham khảo (Nam tìm):** [DeepStream (arXiv:2306.15129)](https://arxiv.org/pdf/2306.15129).
* **Setup Benchmark:** Code demo local (`demo/backend/app.py`). Dataset: Giao thông qua webcam.
* **Paper cho biết:** Phương pháp ROIDet giảm không gian dư thừa trong video. Limitation là nó phản ứng chậm với sự thay đổi quá nhanh ở vùng ngoài rìa ROI cũ.
* **Cơ chế triển khai của nhóm:** 
  * **Dynamic FPS (Vương phụ trách):** Giảm FPS ở cảnh tĩnh, tăng lên khi có hoạt động.
  * **Adaptive Resolution (Phúc phụ trách):** Giữ độ nét ở vùng ROI, nén vùng background.

## 3. Benchmark (Kết quả thử nghiệm)
* **Metric tự đo:** 1. FPS, Độ trễ (Latency); 2. Tỉ lệ rớt khung hình (Drop frame); 3. CPU Load.
* **Kết quả:** So với Baseline bị rớt frame, phương pháp Kết hợp giải quyết triệt để Drop frame (0%), Latency ổn định ~200ms và CPU Edge load chỉ còn 55%. Hệ thống đáp ứng tốt khi mạng bị bóp (throttled).

## 4. Failure Case (Phân tích lỗi)
* **Quan sát trực tiếp:** **Nhóm quan sát được** trên log Demo, ở giây thứ 12 khi vật thể lao vào rất nhanh từ rìa, Latency tăng vọt do AI lỡ 1-2 frame đầu tiên.
* **Suy luận nguyên nhân:** Thuật toán Adaptive Resolution đã nén mạnh vùng rìa, làm mờ chi tiết vật thể mới xuất hiện. Dynamic FPS cũng chưa bắt kịp tốc độ xe.

## 5. Engineering Decision (Quyết định kỹ thuật & Trade-off)
* **Trade-off thực tế:** Phù hợp triển khai cho Robot cảnh vệ (chạy chậm). **Không nên dùng** cho Drone bay nhanh vì latency tăng đột ngột có thể làm mất dấu mục tiêu.
* **Đề xuất cải tiến (Nam):** Tối ưu hóa model AI tại Edge, có thể chạy một detector phát hiện chuyển động siêu nhẹ toàn màn hình liên tục để trigger Keyframe nét toàn cảnh khi có biến, thay vì nén biên tuyệt đối.

---
*(Bản nộp này sử dụng dữ liệu và nghiên cứu chung của nhóm Sentinel)*
