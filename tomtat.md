# 📌 KẾ HOẠCH TÓM TẮT – AI TRỢ LÝ ẢO (CO3107)

## 🧠 Mô tả chung
Nhóm xây dựng một **AI trợ lý ảo điều khiển thiết bị gia dụng bằng giọng nói**.  
Hệ thống có khả năng:
- Nhận diện giọng nói / văn bản từ người dùng
- Hiểu yêu cầu (bật/tắt thiết bị, truy vấn trạng thái)
- Phản hồi lại người dùng
- Gửi lệnh xuống vi xử lý (ESP32 / YoLo UNO / YoLo:Bit) để điều khiển thiết bị vật lý

Kiến trúc được chia thành **2 lớp chính**:
- **Lớp thấp (IoT / hệ thống vật lý):** thu thập dữ liệu, điều khiển thiết bị
- **Lớp cao (AI):** xử lý ngôn ngữ, ra quyết định, điều phối lệnh

Dự án được triển khai theo **4 giai đoạn**, trong đó:
- **2 giai đoạn trước midterm**: hoàn thành tối thiểu **Module 1–3** (tối đa Module 4) để có demo
- **2 giai đoạn sau midterm**: hoàn thiện các module còn lại, tích hợp AI và nâng cao hệ thống

---

## 🔧 Quy ước hàng tuần
- **Thứ 6**: Nhóm mình sẽ cập nhật tiến độ công việc, thảo luận các khó khăn gặp phải, định hướng xử lý và thống nhất kế hoạch tuần tiếp theo.  
- **Thứ 7 – Chủ nhật**: Thời gian linh hoạt để fix các vấn đề phát sinh (nếu có); nếu hệ thống ổn định thì dành để nghỉ ngơi hoặc chạy deadline các môn khác.  
- **Trước midterm**: Hoàn thành **Module 1–3** (tối đa **Module 4**) để đảm bảo có demo MVP.  
- **Sau midterm**: Hoàn thiện các **module còn lại**, tích hợp **AI / Machine Learning**, cải thiện độ ổn định và hiệu năng hệ thống, nâng cấp giao diện dashboard, fix bug và hoàn thiện đồ án cuối để nộp cho giảng viên.

---

## 🧭 Chia 4 giai đoạn

### 🔹 Giai đoạn 1 (9.2 → 22.3 – Midterm) – Lấy được raw data & điều khiển
**Phụ trách:** T. Hưng, K. Vy

- Nhận & gửi dữ liệu:
  - Trạng thái đèn                  (xong phần nhận dữ liệu)
  - Nhiệt độ, độ ẩm                 (xong phần nhận dữ liệu)
  - ...
- Điều khiển thiết bị:
  - Bật / tắt đèn                   (đã xong)
  - Quạt                            (T7 t lên trường lấy cái quạt xong mới làm được)
  - Dùng Relay để làm gì đó         (T7 t test)
- Hiển thị:
  - LCD                             (đã xong)
- (Optional) Hồng ngoại / Servo     (mua thêm đầu phát hồng ngoại thì xong, hoặc có thể đổi lại thành dùng remote của thầy để điều khiển thiết bị 
                                    (cách sau khi đổi không hay!))

**Đầu ra:**  
- Điều khiển được thiết bị
- Dữ liệu gửi & nhận ổn định

---

### 🔹 Giai đoạn 2 (9.2 → 22.3 – Midterm) – Dashboard (chắc phải làm thêm nhma tui chưa biết chia việc sao :Đ )
**Phụ trách:** K. Hưng, Đức

- Thiết kế & triển khai dashboard
- Hiển thị dữ liệu gần realtime
- Cảnh báo vượt ngưỡng
- Điều khiển thiết bị từ dashboard
- (Optional) Log cơ bản

**Output (Midterm):**  
- Demo MVP hoàn thành **Module 1–3**  
- (Tối đa) chạm **Module 4**

---

### 🔹 Giai đoạn 3 (22.3 → 17.5 – Final) – AI / NLP  
**Phụ trách:** Đức + chưa biết (T.Hưng làm chân sai vặt)

- Nhận giọng nói / văn bản
- Xử lý yêu cầu người dùng
- Phản hồi lại end user
- Gửi lệnh xuống vi điều khiển

**Output:**  
- AI điều khiển được thiết bị
- Hiểu và phản hồi lại được end user

---

### 🔹 Giai đoạn 4 (22.3 → 17.5 – Final) – Hoàn thiện  
**Phụ trách:** Cả nhóm bàn lại xong giải quyết các vấn đề còn tồn đọng

- Hoàn thiện dashboard
- Phân tích & dự đoán xu hướng dữ liệu
- Ứng dụng mạng nơ-ron nhân tạo
- Fix bug, tối ưu hệ thống
- Chuẩn bị báo cáo & demo cuối kỳ

**Output (Final):**  
- Hệ thống hoàn chỉnh  
- Demo final + báo cáo nộp giảng viên

---

## ⚠️ Nguyên tắc làm việc
- Ưu tiên **ổn định > thêm tính năng**
- Không mở scope mới sát mốc báo cáo
- Feature nâng cao chỉ làm khi core chạy tốt
