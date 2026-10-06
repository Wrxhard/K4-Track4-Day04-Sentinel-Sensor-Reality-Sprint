# Báo cáo Lab: Track 4 - Day 3
**Nhóm:** Sentinel
**Lớp:** 3A · **Phòng:** H209 · **Track:** Multi-camera bandwidth profiling

## 1. Problem (Bài toán & Nền tảng)
* **Nền tảng:** Robot tự hành / Hệ thống xe ADAS giám sát môi trường.
* **Tính năng:** Phát hiện vật thể (Object Detection) thời gian thực thông qua nhiều luồng camera (Multi-camera streams).
* **Sensor:** Đa camera (Multi-camera) truyền dữ liệu qua băng thông giới hạn (ví dụ: kết nối không dây, 4G/5G hoặc cáp mạng chia sẻ).
* **Failure Case:** Nghẽn băng thông mạng (Network bandwidth bottleneck). Khi số lượng camera tăng, việc truyền nhiều luồng video cùng lúc ở độ phân giải và FPS cố định gây quá tải băng thông, dẫn đến tình trạng rớt gói tin (packet loss), tăng độ trễ (latency), hoặc suy giảm đột ngột chất lượng khung hình khiến thuật toán AI nhận diện sai hoặc trễ.
* **Claim:** Giải pháp kết hợp **Dynamic FPS** (giảm FPS khi không có chuyển động) và **Adaptive Resolution** (chỉ giữ độ phân giải cao ở vùng chứa vật thể - ROI, nén/giảm chất lượng vùng nền) sẽ giúp giảm mạnh dung lượng truyền tải (Bandwidth) mà không làm giảm đáng kể độ chính xác (Accuracy/Recall) của mô hình nhận diện.

## 2. Method (Phương pháp giải quyết)
* **Tài liệu tham khảo:** [DeepStream: Bandwidth Efficient Multi-Camera Video Streaming for Deep Learning Analytics](https://arxiv.org/pdf/2306.15129).
* **Link repo/version & Lệnh chạy:** Demo nội bộ (Commit mới nhất tại local). Chạy qua Terminal bằng lệnh: `python demo/backend/app.py`.
* **Dataset:** Camera giao thông mẫu giả lập trực tiếp qua webcam/video loop.
* **Input:** Video thô từ nhiều camera (chất lượng cao).
* **Output:** Luồng dữ liệu video tối ưu (dung lượng giảm) gửi tới Server/Edge để suy luận.
* **Cơ chế (Triển khai code demo):** 
  * **Dynamic FPS (Nguyễn Triều Vương):** Nếu cảnh tĩnh, giảm FPS xuống 5fps; nếu có hoạt động, tăng lên 30fps.
  * **Adaptive Resolution (Nguyễn Trọng Phúc):** Áp dụng YOLO bounding boxes làm ROI. Giữ nguyên độ phân giải ROI, background được downscale nén mạnh để tiết kiệm số bit truyền tải.
* **Đánh giá từ nguồn (Paper):** Paper đo bằng Bandwidth savings và Accuracy. Giảm băng thông lên đến 54% với độ rớt mAP dưới 1%. Giới hạn (Limitation): Phản ứng chậm với các thay đổi đột ngột từ rìa ảnh.
* **Metric của nguồn (Paper):** Giảm dung lượng băng thông truyền tải lên đến 54% với độ rớt mAP (mean Average Precision) dưới 1%.

## 3. Benchmark (Kết quả thử nghiệm)
* **Dữ liệu & Cấu hình:** Chạy 1 clip giả lập (traffic video) độ phân giải gốc 720p@30fps. Đo dung lượng dữ liệu cần nén/truyền tải (MB/s) và Object Recall (Tỉ lệ vật thể phát hiện được bằng model YOLO cơ bản) trong đoạn clip dài 30 giây.
* **Metric tự đo:** 
  1. FPS (Frames Per Second) & Độ trễ (Latency).
  2. Drop frame rate (%).
  3. Mức chiếm dụng CPU/GPU (Load %).

**Bảng thống kê:**
| Cấu hình | Tham số thay đổi | Avg FPS | Latency | Drop Frame | CPU/GPU Load | Bằng chứng / Quan sát |
|---|---|---|---|---|---|---|
| **Baseline** | Cố định 720p, 30fps | 30 | ~ 150ms | 0% | 85% | Luồng gửi liên tục, Edge phải xử lý toàn bộ frame gốc. |
| **Lỗi mạng (Throttling)** | Bóp băng thông còn 1.5 Mbps | ~ 12 | ~ 800ms | > 50% | 85% | Rớt frame trầm trọng, trễ hình do queue đầy, AI lỡ vật thể. |
| **Thử nghiệm 1 (Vương)** | Bật Dynamic FPS | ~ 15 | ~ 150ms | 0% | 60% | Đoạn vắng xe tự động giảm FPS, tiết kiệm CPU đáng kể. |
| **Thử nghiệm 2 (Phúc)** | Bật Adaptive Resolution (ROI)| 30 | ~ 200ms | 0% | 75% | Băng thông giảm nhưng độ trễ tăng nhẹ do Edge phải tính ROI mask. |
| **Kết hợp (Đề xuất)** | Dynamic FPS + Adaptive Res | ~ 15 | ~ 200ms | 0% | 55% | Tối ưu hóa cực tốt băng thông, giảm drop frame, tải CPU thấp. |

## 4. Failure Case (Phân tích lỗi)
* **Bằng chứng nhóm đưa ra (Từ Log/Plot):** Dựa vào log FPS và Queue latency trên màn hình Demo, khi áp dụng cấu hình Kết hợp, ở giây thứ 12 có một xe máy lao vào rất nhanh từ góc khuất.
* **Kết quả đo trực tiếp:** **Nhóm quan sát được** hiện tượng "Trễ nhận diện" (Detection Latency) tăng vọt cục bộ lên ~300ms do AI lỡ nhịp 1-2 frame đầu tiên.
* **Suy luận nguyên nhân:** Thuật toán Adaptive Resolution đã nén quá mạnh vùng rìa khung hình do frame trước tĩnh. Khi xe máy lao vào, vùng biên bị mờ dẫn đến detector confidence quá thấp. Cùng lúc đó, Dynamic FPS đang ở trạng thái ngủ (5fps) nên bị lỡ nhịp.
* **Hạn chế của phương pháp:** **Paper cho biết** ROIDet rất hiệu quả trong việc giảm data thừa, nhưng limitation là nó dự đoán ROI hoàn toàn dựa trên frame quá khứ, nên sẽ phản ứng chậm với thay đổi đột ngột ở vùng rìa.

## 5. Engineering Decision (Quyết định kỹ thuật & Trade-off)
* **Trade-off thực tế (Nên/Không nên dùng):** Rất nên áp dụng cho Robot giám sát tĩnh, camera bãi đỗ xe hoặc góc đường cố định (ít thay đổi). **Không nên dùng** cho Drone bay tốc độ cao hoặc xe ADAS chạy cao tốc vì hiện tượng trễ nhận diện ở rìa có thể gây nguy hiểm nghiêm trọng.
* **Từ Failure Case, nhóm đề xuất Cải tiến:**
  1. **Mở rộng vùng đệm ROI (Buffer Padding):** Không chỉ giữ độ phân giải cao cho vùng chứa vật thể hiện tại, mà kết hợp dự đoán quỹ đạo (Kalman filter) để mở rộng vùng nét đón đầu hướng di chuyển của vật thể.
  2. **Vùng an toàn tĩnh (Safety Zones):** Luôn giữ độ phân giải ở mức trung bình (hoặc lấy mẫu thường xuyên) tại các điểm nóng (như góc cua, hai bên rìa màn hình) để không bỏ lỡ vật thể lao tới bất ngờ.
* **Kế hoạch tiếp theo:** Cập nhật script Adaptive Resolution của Phúc để thêm padding 20 pixel vào các ROI box trước khi nén, sau đó chạy lại vòng lặp Benchmark xem Object Recall có tăng lại ngưỡng 98-99% mà vẫn đảm bảo băng thông < 1.5 Mbps hay không.

---

## 6. Phân công vai trò (Tóm tắt từ bản trình bày)
| Vai trò | Người phụ trách |
|---|---|
| **Tìm Paper / Tối ưu AI** | Nguyễn Trần Nhựt Nam (2A202602981) |
| **Implement Dynamic FPS** | Nguyễn Triều Vương (2A202602422) |
| **Implement Adaptive Resolution & Lead** | Nguyễn Trọng Phúc (2A202602552) |
