# AI Auto Video

Biến kịch bản của bạn thành **video dọc 9:16** có giọng đọc tiếng Việt, chạy hoàn toàn trên Google Colab.

**Kịch bản → giọng đọc (OmniVoice) → hình ảnh động (HTML + Chromium) → ghép video (FFmpeg)**

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/saigonvet8312-coder/AI_video/blob/main/AI_auto_video.ipynb)

## Cách dùng

1. Mở notebook bằng nút Colab ở trên, chọn **Runtime → Change runtime type → T4 GPU**.
2. Chạy lần lượt 3 phần (mỗi phần là một cell riêng):
   - **Phần 1 — Cài đặt:** chỉ chạy một lần mỗi phiên Colab.
   - **Phần 2 — Mã nguồn & thư viện giọng:** gắn Google Drive (chỉ để lưu giọng), lấy mã mới nhất.
   - **Phần 3 — Mở giao diện:** hiện đường link, mở ở tab mới.
3. Trong giao diện, đi qua 4 tab. Mỗi tab có nút chạy riêng:

| Tab | Việc làm |
|---|---|
| ① Kịch bản | Dán kịch bản, tách cảnh, chỉnh sửa trong bảng |
| ② Giọng đọc | Chọn giọng trong thư viện (hoặc lưu giọng mới), tạo giọng từng cảnh, nghe thử |
| ③ Hình ảnh | Chọn chủ đề, thương hiệu, thư viện ảnh/ảnh AI, dựng hình, xem thử từng cảnh |
| ④ Xuất video | Ghép video cuối, hoặc “Chạy tất cả” |

Kết quả tải về ở tab ④: `ket-qua.zip` (gồm `video.mp4`, `voice.mp3`, `script.txt`, `captions.srt`) hoặc từng file.

## Làm video bớt nhàm chán

- **6 chủ đề hình ảnh** (tab ③): Cực quang, Neon công nghệ, Điện ảnh tối, Giấy sáng, Hoàng hôn, Tối giản đậm. Mỗi chủ đề có nền, màu, kiểu chữ và hiệu ứng riêng; đổi chủ đề không cần tạo lại giọng.
- **8 mẫu cảnh:** hero, stat (số tự chạy lên), statement (từ khoá được tô sáng), list, quote, compare, image, outro. Mẫu và hiệu ứng vào cảnh được tự luân phiên để các cảnh không giống nhau.
- **Ảnh nền cho từng cảnh** (cột “Ảnh nền”): tên file đã tải lên thư viện, đường link ảnh, hoặc **một mô tả để AI tạo ảnh** (tab ③ → “Tạo ảnh AI”). Cảnh có ảnh nền có chuyển động máy quay.
- **Đạo diễn AI** (tab ①, tuỳ chọn, cần Anthropic API key): Claude đọc kịch bản rồi chọn chủ đề, mẫu cảnh, chữ ngắn gọn và mô tả ảnh nền cho từng cảnh.

- **Nhạc nền tự tạo** (tab ④): hai kiểu *Êm dịu* và *Trầm tối*, được tổng hợp ngay trong Colab nên không phải tải nhạc và không vướng bản quyền. Nhạc **tự hạ nhỏ khi có giọng đọc**, tự vào/ra êm ở đầu và cuối video. Cũng có thể tải **file nhạc của bạn** lên (mp3/wav/m4a…), nhạc ngắn sẽ được lặp lại.
- **Hiệu ứng chuyển cảnh**: tiếng vút ở mỗi lần đổi cảnh, thêm tiếng bụp trầm ở cảnh số liệu và cảnh kết.
- **Phụ đề cháy sẵn** (tab ④, tuỳ chọn): hiện từng cụm ngắn, từ đang đọc được tô sáng dần theo màu nhấn của chủ đề; đặt ở phía dưới hoặc giữa khung. Bấm “Xem thử” ở tab ③ để xem phụ đề của từng cảnh. Thời gian từng từ được ước lượng theo độ dài chữ và dấu câu trong đoạn giọng thật sự vang lên.

- **Video AI cho từng cảnh** (tab ③, mục "Video AI"): ảnh AI của mỗi cảnh (tạo từ kịch bản) được Stable Video Diffusion biến thành đoạn video chuyển động thật, rồi làm chậm, nội suy khung và chạy xuôi–ngược cho vừa độ dài giọng đọc. Áp dụng cho cảnh `hero`, `image`, `statement`, `quote`; cảnh số liệu/danh sách/so sánh/kết giữ nguyên đồ hoạ. Cách dùng: tạo ảnh AI → bấm **Tạo video AI** → ghép video ở tab ④. Cảnh video AI không có chữ trên hình nên phụ đề tự bật. Cần GPU, mỗi cảnh mất vài phút trên T4, và cần đồng ý điều khoản mô hình `stabilityai/stable-video-diffusion-img2vid-xt` trên Hugging Face rồi dán token vào ô "Hugging Face token". Đây là mô hình ảnh → video: nội dung theo ảnh, còn chuyển động do mô hình tự suy ra. Đổi mô hình bằng biến môi trường `AVG_VIDEO_MODEL`.

## Phong cách ảnh AI riêng (JSON)

Ảnh AI luôn được tạo theo **JSON phong cách do bạn cung cấp cho từng video** (tab ③ → “Phong cách ảnh AI”, dán JSON hoặc tải file `.json`). Mẫu nằm ở `examples/style-cosmic-tech-brain.json`.

| Trường | Ý nghĩa |
|---|---|
| `style_name` | Tên phong cách |
| `full_prompt_string` | **Bắt buộc.** Mô tả phong cách chung |
| `composition` | Bố cục |
| `lighting` | Ánh sáng |
| `color_palette` | Bảng màu |
| `negative_prompt` | Những thứ cần tránh |

**Có JSON là tự tạo ảnh cho mọi cảnh** (trừ cảnh kết): tool tự viết mô tả chủ thể từ lời đọc (Claude nếu bạn nhập API key, nếu không thì dịch tự động), rồi tạo ảnh theo JSON. Bấm “Điền mô tả ảnh vào bảng” để xem/sửa mô tả trước khi tạo ảnh; ô nào bạn tự điền thì được giữ nguyên.

Cột **Ảnh nền** của từng cảnh có thể ghi **chủ thể** thủ công (ví dụ `a robot hand holding a glowing smartphone`); phong cách lấy từ JSON. Đổi JSON thì ảnh được tạo mới, còn đổi chủ đề giao diện thì ảnh giữ nguyên. Đạo diễn AI cũng đọc JSON này để viết mô tả chủ thể cho hợp phong cách.

## Lưu trữ

- **Dự án không được lưu lại** sau phiên Colab: làm xong thì tải kết quả về. Trong lúc làm, từng bước vẫn được nhớ: sửa một cảnh thì chỉ cảnh đó được tạo giọng/dựng hình lại.
- **Chỉ thư viện giọng đọc được lưu trên Google Drive** (thư mục `AI_video_voices`). Lưu một giọng ở tab ② (tên + file mẫu 3–15 giây + lời của mẫu nếu có), lần sau chọn trong danh sách.

## Bảng kịch bản

Chỉ cần điền cột **Lời đọc**, các ô trống còn lại được tự điền (bấm “Điền tự động” để xem).

| Cột | Ý nghĩa |
|---|---|
| Mẫu | `hero` · `stat` · `statement` · `list` · `quote` · `compare` · `image` · `outro` |
| Nhãn | Chữ nhỏ phía trên tiêu đề |
| Tiêu đề | Chữ lớn trên màn hình (`|` xuống dòng, `*từ khoá*` để tô sáng) |
| Phụ đề | Dòng mô tả bên dưới |
| Danh sách | Các mục của mẫu `list`, cách nhau bằng `|` |
| Ảnh nền | Tên file trong thư viện, link ảnh, hoặc mô tả để AI tạo ảnh |
| Lời đọc | Nội dung được đọc. Số, %, đơn vị (MP, GB, mAh…) tự đọc thành chữ |

## Cấu trúc mã

```
AI_auto_video.ipynb   notebook Colab (3 phần)
app/
  main.py        giao diện Gradio
  scriptkit.py   tách cảnh, điền tự động, kiểm tra
  vnnum.py       đọc số/ký hiệu thành chữ tiếng Việt
  tts.py         tạo giọng bằng OmniVoice, có cache
  templates.py   6 chủ đề + 8 mẫu cảnh (HTML/CSS)
  media.py       ảnh nền: tải lên, link, ảnh AI
  aiimage.py     tạo ảnh nền bằng AI
  director.py    đạo diễn AI (Claude)
  subjects.py    tự viết mô tả chủ thể ảnh từ lời đọc
  autobg.py      tự điền mô tả ảnh cho các cảnh trống
  voices.py      thư viện giọng đọc (Google Drive)
  render.py      dựng hình bằng Chromium + FFmpeg
  assemble.py    ghép video, trộn âm thanh, xuất phụ đề
  aivideo.py     ảnh → video bằng Stable Video Diffusion, khớp độ dài giọng
  audiofx.py     nhạc nền tự tạo, hiệu ứng chuyển cảnh, tự hạ nhạc khi có giọng
  captions.py    phụ đề cháy sẵn kiểu karaoke (ASS)
  jobs.py        chạy nền, phát nhật ký trực tiếp
  project.py     dự án, cài đặt, cache
```

## Xử lý sự cố

| Triệu chứng | Cách xử lý |
|---|---|
| Phần 1 báo cần khởi động lại | Restart session rồi chạy lại từ Phần 1 |
| Giọng mỗi cảnh một khác | Chọn một **giọng trong thư viện** ở tab ② |
| Dựng hình lâu | Chọn chất lượng “Nhanh”, tắt “Nền chuyển động suốt cảnh” |
| Chữ tiếng Việt lỗi dấu | Chạy lại Phần 1 (cài font) |
| Muốn làm lại một bước | Tick “Tạo lại / Dựng lại từ đầu” rồi chạy |

## Giấy phép các thành phần

Giọng đọc: [OmniVoice](https://github.com/k2-fsa/OmniVoice) (Apache-2.0) · Ảnh AI: segmind/SSD-1B (Apache-2.0, đổi được bằng biến `AVG_AI_MODEL`) · Trình duyệt tự động: Playwright (Apache-2.0) · Giao diện: Gradio (Apache-2.0) · FFmpeg.
