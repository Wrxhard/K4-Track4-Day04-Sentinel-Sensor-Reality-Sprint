# 🚀 Đồ án Lab: Track 4 - Day 4| Nhóm Sentinel

**Lớp:** 3A · **Phòng:** H209 · **Track:** Multi-camera bandwidth profiling

Dự án này là bài Lab thực hành ứng dụng các phương pháp tối ưu băng thông cho hệ thống nhiều camera AI (ADAS, Robot, Drone) trong điều kiện mạng giới hạn, mô phỏng theo nghiên cứu **DeepStream (arXiv:2306.15129)**.

---

## 👥 Danh sách thành viên
Chi tiết phân công, vui lòng xem tại [`TEAMMATES.md`](./TEAMMATES.md).
- **Nguyễn Trọng Phúc (2A202602552)**: Project Lead & Implement Adaptive Resolution.
- **Nguyễn Trần Nhựt Nam (2A202602981)**: Tìm kiếm Paper, Tối ưu hóa AI.
- **Nguyễn Triều Vương (2A202602422)**: Implement thuật toán Dynamic FPS.

*(Báo cáo cá nhân của từng thành viên được đặt trong thư mục [`report/`](./report/))*

---

## 📖 Bài toán và Giải pháp
* **Vấn đề (Problem):** Khi truyền tải nhiều luồng camera cùng lúc với độ phân giải và FPS cố định, mạng dễ bị nghẽn (bandwidth bottleneck), làm rớt khung hình (drop frame), tăng độ trễ (latency) và khiến model AI tại Edge/Server bỏ lỡ các vật thể quan trọng.
* **Giải pháp (Method):** 
  * **Dynamic FPS:** Giảm FPS xuống thấp (5fps) khi không có chuyển động, và tăng lên cao (30fps) khi phát hiện người/vật thể.
  * **Adaptive Resolution:** Sử dụng Bounding box của YOLO làm ROI. Vùng chứa vật thể giữ nguyên độ phân giải, vùng nền (Background) bị nén mạnh và làm mờ để tiết kiệm băng thông cực đại.

---

## 🛠 Hướng dẫn cài đặt và Tái hiện Benchmark

Hệ thống được code bằng Python (Backend dùng FastAPI/OpenCV/YOLOv8) và thao tác thông qua Webcam. Toàn bộ metric như **FPS, Latency, Drop frame, CPU/GPU load** sẽ được đẩy trực tiếp lên màn hình Dashboard.

### 1. Yêu cầu hệ thống
- Máy tính có Webcam.
- Python 3.11 hoặc 3.12.

### 2. Cài đặt môi trường
Mở Terminal tại thư mục gốc của Repo, di chuyển vào thư mục `demo` và chạy các lệnh sau:
```powershell
cd demo

# Cài đặt các thư viện cần thiết
pip install -r requirements.txt

# Tải model weights (YOLOv8n) cho lần chạy đầu tiên
python setup_demo.py
```

### 3. Khởi động Demo
Chạy trực tiếp file script PowerShell có sẵn:
```powershell
.\start.ps1
```
*(Lệnh này tương đương với việc dùng `uvicorn` để khởi chạy ứng dụng FastAPI tại cổng 8765)*

### 4. Tái hiện các thao tác Benchmark
1. Mở trình duyệt, truy cập vào trang Dashboard: **http://127.0.0.1:8765**
2. Cấp quyền truy cập Webcam cho trình duyệt và bấm nút **Start camera**.
3. **Kiểm chứng Metric "Dynamic FPS" (Của Vương):** Hãy lách người ra khỏi khung hình Webcam (cảnh tĩnh). Bạn sẽ thấy thông số FPS hiển thị rớt xuống mức Idle (ví dụ 2fps - 5fps). Khi bạn bước lại vào khung hình, FPS lập tức vọt lên 15-30fps.
4. **Kiểm chứng Metric "Adaptive Resolution" (Của Phúc):** Thuật toán nén nền đã được chèn vào `backend/app.py`. Bạn sẽ thấy những vùng không chứa người sẽ bị mờ/pixelated đi rất nhiều, nhưng khu vực chứa người thì vẫn rõ nét.
5. **Quan sát Bảng Metric Tổng hợp:** Trên giao diện cũng sẽ có báo cáo Real-time về:
   - **Độ trễ (Latency):** Thời gian tính từ lúc chụp ảnh tới lúc nhận kết quả.
   - **Drop frame:** Số khung hình bị drop do nghẽn hàng đợi (queue).
   - **CPU / GPU Load:** Tỉ lệ chiếm dụng tài nguyên hệ thống từ `psutil` và `nvidia-smi`.

---
**📘 Xem thêm:** 
Chi tiết các bảng số liệu Benchmark, Failure Case (Trễ nhận diện) và Đề xuất cải tiến (Trade-off) đã được ghi rõ tại file báo cáo chính thức: [`report_sentinel.md`](./report_sentinel.md)
