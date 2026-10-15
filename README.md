# MangaTrans

개인용 일본어 만화 → 한국어 번역·역식 웹앱. **Next.js + FastAPI + MangaOCR + Qwen3 4B Q4_K_M + OpenCV + Pillow**. Tesseract는 영역 검출에, MangaOCR는 말풍선 문장 읽기에 사용한다. 번역은 llama.cpp CPU 실행기로 처리한다. 유료 API나 유료 서버가 기본 구성에 없으며 스마트폰 Chrome에서 완료된 페이지부터 읽는다.

> 자체 제작 그림으로 실제 OCR·번역·식자와 다중 페이지를 검사한다. Tesseract/NLLB 조합의 실제 사용 결과에서 오인식과 오역이 보고되어 기본 엔진을 교체했다. **번역 의미의 완전한 정확성, 보고된 실제 페이지의 개선 결과, Windows 실기·원격 연결·특정 외부 사이트를 검증했다고 주장하지 않는다.** 최신 실행 기록은 [검증 기록](docs/validation.md)을 참고한다.

## 구현 범위

- 비밀번호 로그인, 서명된 HttpOnly/SameSite 쿠키, 로그인 시도 제한, API와 원본·결과 이미지 접근 제한
- 여러 이미지 업로드, 등록 호스트의 HTTPS 이미지 직접 URL, 여러 페이지 JSON 매니페스트
- 실제 일본어 가로/세로 OCR → 로컬 일본어·한국어 번역 → 글자 마스크 → OpenCV Telea 복원 → 한글 자동 줄바꿈·크기 맞춤 식자
- SQLite 작업 기록, 한 개의 CPU 워커와 제한된 대기열, 페이지별 상태와 처리 단계, 완료 페이지의 즉시 공개
- 세로 스크롤 뷰어, 원본/한국어 전환, OCR 텍스트·번역 확인, 완료/실패 작업과 저장 이미지 삭제
- 직접 그린 테스트 페이지 생성. 제3자 만화나 미리 정해둔 번역 결과를 포함하지 않음

기본 MangaOCR와 Qwen3 가중치는 **Apache-2.0**, llama.cpp와 앱 코드는 MIT다. Qwen은 Unsloth 공개 Q4_K_M 양자화본을 고정 리비전·SHA-256으로 검증한다. 이전 엔진도 명시적으로 선택 가능하다: `MANGATRANS_MODEL=nllb`는 CC-BY-NC-4.0, `m2m100`은 MIT다. `MANGATRANS_OCR=tesseract`로 이전 OCR을 선택한다. 이전 엔진은 더 가벼운 대안이며 보고된 품질 문제를 해결한 대안이라고 주장하지 않는다.

초기 버전은 **선명한 인쇄체와 흰 말풍선**에 맞췄다. 효과음, 손글씨, 루비, 작은 글자, 복잡한 배경, 말풍선 밖 텍스트, 컷 사이의 문맥·독서 순서는 부정확하거나 누락될 수 있다. OCR이 인식한 영역만 처리한다. OpenCV의 주변 픽셀 보간은 원래 그림을 재생성하는 생성형 복원이 아니며, 복잡한 그림 위에서는 흔적이 남을 수 있다. 이 버전은 LaMa·전용 만화 텍스트 검출기·수동 편집기·작품 전체 용어집을 구현하지 않았다.

## ChatGPT Plus를 사용하나요?

현재 앱은 무료 로컬 모델을 사용한다. 추가 확인에서 **공식 Sign in with ChatGPT의 로컬 오픈소스 앱용 OAuth 및 ChatGPT 플랜 사용 기능이 존재함**을 확인했다. 초기의 “Codex용 인증만 확인됨” 판단을 수정했다. 이 기능은 아직 MangaTrans에 구현·연결하지 않았다. 공식 흐름은 사용자의 실제 로그인·동의, 127.0.0.1 콜백, 검증된 OAuth 토큰 및 플랜 권한 확인을 요구하며 원격 웹사이트는 별도 제약이 있다. 기존 Codex 세션이나 숨겨진 ChatGPT 엔드포인트를 재사용하지 않는다. 상세 근거와 미구현 범위는 [인증 검증 기록](docs/chatgpt-auth.md)에 남겼다.

## Windows PC에서 실행하고 휴대폰으로 읽기

**휴대폰에서 조작하고 읽을 수 있지만, 이 버전은 PC가 뒤에서 번역을 처리한다.** PC를 끄거나 절전 상태로 두면 번역·열람도 중단된다. 휴대폰 자체에서 OCR·번역을 실행하는 온디바이스 버전은 구현하지 않았다.

윈도우용 배치 도우미를 추가했다. **이 개발 머신은 Linux이므로 Windows 실기 실행은 미검증**이다. 처음부터 돌아가는 독립 EXE 배포판이라고 주장하지 않는다. 상세 안내는 [START-HERE-KO.txt](START-HERE-KO.txt)에 있다.

1. 소스 폴더 전체를 PC에 준비하고 압축을 받았다면 먼저 압축 해제한다.
2. `setup-windows.bat` 실행: 필요한 Python 3.12/Node/Tesseract가 없으면 공식 winget 원본의 설치 확인을 거쳐 설치한다. 잠금 파일의 의존성, 고정 체크섬의 Noto 폰트, 공식 CPU 모델을 설치한다. 최초에 개인 비밀번호를 정한다. 기존 `.env`는 보존한다.
3. `start-windows.bat` 실행: 로컬 API와 웹을 시작하고 PC 브라우저를 연다. 실행 창을 닫으면 서버도 중단된다.
4. 휴대폰 연결은 `phone-windows.bat`: 공식 Tailscale 설치·로그인을 진행하고 개인 tailnet의 HTTPS 주소를 안내한다. 휴대폰에도 공식 Tailscale 앱을 설치해 **동일 계정**으로 로그인한다. 주소를 Chrome으로 열어 읽는다.
5. 휴대폰 설정 후 기존 실행 창을 종료하고 `start-windows.bat`를 다시 실행한다. 이후에는 PC를 켜 두고 휴대폰에서만 조작할 수 있다.

### 이미 설치한 Windows PC에서 업데이트

1. 현재 MangaTrans 실행 창에서 `Ctrl+C`로 종료한다.
2. 최신 ZIP을 전체 압축 해제하고 **새 폴더 안의 내용 전체를 기존 설치 폴더에 덮어쓴다.** 기존 설치 폴더를 삭제하지 않는다. ZIP에는 개인 `.env`, 모델, 사용자 데이터가 포함되지 않으므로 기존 파일이 유지된다.
3. 기존 설치 폴더의 `update-windows.bat`를 실행한다. **이번 업데이트는 새 모델 약 3GB와 CPU 실행기를 한 번 내려받아 검증하고 MangaOCR/Qwen3를 선택한다.** 기존 비밀번호·세션 키·폰트·접근 설정·저장 페이지는 유지한다. 이전 모델은 다시 받거나 삭제하지 않는다. 모델 준비와 웹 화면 빌드가 성공한 후 새 설정을 활성화한다.
4. 완료되면 `start-windows.bat` 실행 후 브라우저를 새로고침한다. 이전 작업 결과는 자동으로 다시 만들지 않으므로 이미지를 새 작업으로 업로드한다.

업데이트 도우미와 시작 도우미는 포트가 이미 사용 중이면 종료하며 기존 프로세스를 임의로 죽이지 않는다. 이는 예전 서버가 계속 실행되는 상태에서 새 코드가 적용된 것으로 오해하는 일을 막기 위한 검사다. Windows 실기 검증은 아직 하지 못했다.

도우미는 PowerShell 실행 정책을 해당 프로세스에서만 설정하며, 시스템의 영구 실행 정책이나 TLS/패키지 체크섬 검증을 해제하지 않는다. Windows 설치나 Tailscale 계정 로그인은 사용자의 PC에서 직접 완료해야 한다. 이 채팅의 “환경 게시”가 스마트폰용 사이트를 인터넷에 배포해 주지는 않는다.

### Windows에서 일본어 OCR 데이터 경로 오류

`Error opening data file "C:\\...\\tessdata"/jpn.traineddata`처럼 경로의 따옴표가 그대로 표시되면 이전 OCR 호출 코드의 Windows 경로 전달 문제다. 최신 `backend/vision.py`를 기존 폴더의 같은 파일에 덮어쓰고 실행 창을 종료한 뒤 `start-windows.bat`로 다시 실행한다. 수정본은 `TESSDATA_PREFIX` 환경 변수로 경로를 전달한다. 기존 데이터 파일이 있다면 모델 다운로드나 비밀번호 설정을 반복할 필요가 없다.

### 기존 Windows 설정 인코딩 오류

이전 도우미는 Windows 기본 CP949로 `.env`를 저장해 한글 비밀번호에서 `UnicodeDecodeError: utf-8 ... byte 0xc0` 오류가 날 수 있었다. 수정된 `scripts/init_env.py`는 새 설정을 UTF-8로 저장하고, 기존의 정상적인 CP949 설정은 값을 바꾸지 않고 UTF-8로 복구한다. 기존 파일의 접근 권한을 유지하며 비밀번호를 출력하거나 다시 정하지 않는다. 알 수 없는 인코딩이나 불완전한 파일은 덮어쓰지 않는다.

이미 이 오류가 났다면 최신 소스의 `scripts/init_env.py`를 기존 설치 폴더의 같은 파일에 덮어쓴 뒤 기존 `setup-windows.bat`를 다시 실행한다. `.env`나 기존 설치 폴더를 삭제하지 않는다. 비밀번호와 `.env` 내용은 채팅에 보내지 않는다.

## 설치 (Ubuntu/Debian, CPU)

권장: Windows/Linux x86_64, Python 3.12, Node.js 22.9+ 또는 24, RAM 16GB 이상, 여유 디스크 12GB 이상. 새 모델만 약 3GB이며 기존 사용자는 추가 공간이 필요하다. CPU만으로 실행하지만 페이지마다 수분 걸릴 수 있다. 제공 실행기는 Windows/Linux x64용이며 Windows에서는 공식 Microsoft C++ 런타임도 확인한다.

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr fonts-noto-cjk curl git
# Node.js와 uv를 먼저 공식 방법으로 설치한다.
# https://nodejs.org/ / https://docs.astral.sh/uv/getting-started/installation/
git clone https://github.com/haeyunseop/manga-translator.git
cd manga-translator
bash scripts/install.sh
bash scripts/start.sh
```

클론 명령은 코드를 GitHub에 올린 뒤 사용할 수 있다. Codex 작업 공간의 코드는 자동으로 GitHub에 푸시되지 않는다. 이미 체크아웃된 작업 공간에서는 그 디렉터리에서 설치부터 실행한다.

설치는 Python 잠금 파일, PyTorch 공식 CPU 인덱스, npm 잠금 파일을 사용한다. 일본어 OCR 파일은 공식 저장소의 고정 커밋·SHA-256으로 검사한다. 모델은 고정 리비전·SHA-256으로, CPU 실행기는 공식 GitHub 릴리스의 고정 SHA-256으로 검증한다. 인증서 검증을 끄지 않는다. 첫 모델 다운로드에 인터넷이 필요하고, 이후 OCR은 `local_files_only=True`, 번역 실행기는 `--offline`으로 네트워크 없이 동작한다.

설치 스크립트는 기존 `.env`를 보존하며, 없으면 강한 임의 비밀번호와 세션 키를 생성한다. **자신의 머신에서 `.env`의 `MANGATRANS_PASSWORD`를 확인해 로그인**한다. 값을 채팅이나 Git에 붙여 넣지 않는다. 사이트는 로컬 포트 3000에서 접속하고, 백엔드 8000은 외부에 공개하지 않는다.

모델만 다시 준비하려면:

```bash
.venv/bin/python scripts/download_models.py
```

현재 Codex 환경에서는 게시 후 네트워크 차단이 해소되어 모델 다운로드와 검증을 완료했다. 새 환경에서 네트워크 제한이 있으면 다음 공식 배포처 접근을 확인한다: `huggingface.co`, `us.aws.cdn.hf.co`, `cdn-lfs.huggingface.co`, `cdn-lfs-us-1.hf.co`, `cdn-lfs.hf.co`, `cas-bridge.xethub.hf.co`, `cas-server.xethub.hf.co`, `transfer.xethub.hf.co`가 필요할 수 있다. 실제 오류가 알려 주는 공식 다운로드 도메인을 확인하고, 모르는 목적지나 전체 인터넷으로 허용 범위를 넓히지 않는다.

별도 폰트를 사용하려면 `.env`에 `MANGATRANS_FONT=/absolute/path/NotoSansCJK-Regular.ttc`를 지정한다. 기본 경로는 `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc`다. 세션 키·비밀번호 변경은 서버 재시작 후 적용되며 기존 로그인은 무효화된다.

## 실제 한 페이지 번역

1. 로그인 후 엔진 상태가 준비 완료인지 확인한다.
2. **테스트 페이지 번역**을 누른다. 앱이 자체 제작한 일본어 그림을 생성하고 OCR부터 순서대로 처리한다.
3. 완료되면 한국어 이미지가 나타난다. 원본 전환과 인식·번역 텍스트를 확인한다.
4. 번역 모델이 없거나 OCR이 실패하면 해당 오류가 표시된다. 처리 실패를 번역 완료로 계산하지 않는다.
5. 식자는 말풍선 윤곽·남은 그림 선을 피하는 마스크 안에서 픽셀 단위로 검증한다. 페이지 크기에 비례한 글꼴과 단어를 우선하는 줄바꿈을 사용한다. 들어가지 않는 번역은 갈색 윤곽과 가능한 경우 번호를 표시하고 이미지 아래에 전문을 표시한다. 작은 글씨로 무제한 축소하거나 내용을 잘라내지 않는다.
6. 이전 Tesseract OCR의 신뢰도가 55% 미만이거나 번역 반복·과도한 길이·출력 중단 등이 감지되면 해당 영역의 원문을 지우지 않는다. 뷰어와 서재에 확인 필요 상태가 표시된다. 이런 검사는 잘못된 의미·주어·문맥을 모두 검출하지 못하므로 번역 의미의 정확성을 보장하지 않는다.
7. 실제 이용 권한이 있는 파일은 이미지 업로드에서 선택한다. 최대 20페이지, 페이지당 15MB, 총 100MB, 페이지당 1,600만 화소. 선택 순서가 읽기 순서다.

문제가 있는 완료/실패 작업은 뷰어의 **진단 파일 저장**으로 ZIP을 만들 수 있다. 해당 작업의 원본·결과 PNG와 실제 OCR/번역 JSON만 포함하며 `.env`, 비밀번호, 세션 키, 서버 로그, 모델 캐시는 포함하지 않는다. 원본과 대사가 포함되므로 사용자가 직접 공유 여부를 결정한다. 읽기 위해 다운로드할 필요는 없다.

서버의 `data/`에 원본과 결과를 저장한다. 브라우저에 다운로드할 필요는 없지만 **서버 디스크는 사용**한다. 서재의 휴지통으로 완료/실패 작업을 삭제할 수 있다. 진행 중 작업 취소/삭제는 지원하지 않는다. 서버가 재시작되면 진행 중 작업은 실패로 표시하고 완료된 페이지는 보존한다. 자동 재시도·자동 재개는 하지 않는다.

## URL 어댑터와 지원 사이트

기본 허용 호스트는 **없다**. 특정 상용 만화 사이트를 지원한다고 주장하지 않는다. 본인 소유 또는 처리 허락을 받은 공개 자료의 호스트만 `.env`의 `MANGATRANS_ALLOWED_HOSTS`에 정확히 등록하고 재시작한다.

```dotenv
MANGATRANS_ALLOWED_HOSTS=my-art.example,images.my-art.example
```

지원하는 두 형식:

1. **이미지 직접 주소**: `https://images.my-art.example/page01.png` (PNG/JPEG/WebP)
2. **작품 JSON**: 다음 파일을 자신의 공개 HTTPS 호스트에서 `Content-Type: application/json`으로 제공

```json
{
  "title": "내가 그린 첫 번째 이야기",
  "license": "Self-authored; personal translation permitted",
  "pages": [
    "https://images.my-art.example/01.png",
    "https://images.my-art.example/02.png"
  ]
}
```

모든 페이지 호스트도 등록해야 한다. HTML 스크래핑, 로그인·유료벽·CAPTCHA·DRM 우회, 쿠키 전달, 리디렉션 추적, 사설망·메타데이터 주소 접근을 구현하지 않는다. DNS의 모든 주소를 검사하고 검증한 공인 IP에 연결을 고정하며, 원본 호스트의 TLS/SNI는 그대로 검증한다. 따라서 CDN 리디렉션 링크는 최종 파일 URL로 바꿔야 한다. 권리 확인 체크박스가 라이선스를 자동으로 보장해 주지는 않는다.

## 월 서버·API 요금 없이 스마트폰에서 사용

**권장: 집 PC에서 실행 + Tailscale 개인용 무료 요금제.** PC가 작업을 하고 스마트폰 Chrome은 결과만 읽는다. 전기·인터넷·기기 비용은 별도이며, 무료 요금제 조건과 제한은 서비스 제공자의 현재 정책을 확인한다.

1. PC와 Android에 [Tailscale 공식 앱](https://tailscale.com/download)을 설치하고 같은 개인 tailnet에 로그인한다.
2. `bash scripts/start.sh`로 로컬 서버를 실행한다.
3. PC에서 `tailscale serve --bg http://127.0.0.1:3000`을 실행한다. Tailscale이 안내하는 HTTPS 주소는 tailnet 사용자에게만 열린다. **Funnel이나 공유·공개 설정은 켜지 않는다.**
4. 안내된 주소에 맞춰 `.env`를 바꾸고 MangaTrans를 재시작한다:

```dotenv
MANGATRANS_SECURE_COOKIE=true
MANGATRANS_ORIGINS=https://your-pc.your-tailnet.ts.net
```

5. Android에서 Tailscale을 연결하고 Chrome으로 그 HTTPS 주소에 접속한다. MangaTrans 비밀번호도 필요하다. PC가 꺼지거나 절전 상태면 번역·열람이 중단된다.

이는 설치 방법이며 이 개발 환경에서 실제 Tailscale 배포를 수행·검증한 것은 아니다. 공개 배포가 필요하다면 별도의 HTTPS 역방향 프록시·접근 제한·업로드 크기 제한·로그 정책을 준비해야 한다. Vercel 등의 무료 정적/서버리스 호스팅에 이 CPU 모델과 장시간 워커를 그대로 올릴 수 있다고 가정하지 않는다. 누구에게나 제공되는 영구 무료 GPU/서버를 약속하지 않는다.

## 개발·검증

```bash
# 터미널 1: API
.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
# 터미널 2: 웹
cd frontend
npm run dev
```

```bash
# 저장소 루트
.venv/bin/python -m pytest -q
# 실제 모델 설치 후 2개 추론 검사를 실행. 모델 없을 때만 skip하며 성공으로 계산하지 않는다.
.venv/bin/python -m pytest -q -m real_model -s
cd frontend
npm run build
npm run typecheck
# 서버 둘을 실행한 상태. Linux Chromium을 사용하는 설정.
CHROMIUM_PATH=/usr/bin/chromium npx playwright test
npm audit
```

다른 OS에서는 `CHROMIUM_PATH`를 실제 Chromium 경로로 지정하거나 Playwright 설정에서 설치된 브라우저를 선택한다. 번들 브라우저를 사용하려면 공식 Playwright 설치 절차에 따라 설치한다.

보안/URL 테스트는 네트워크 전송을 대체해 위험한 주소와 잘못된 형식이 차단되는지 검사한다. 다중 페이지 워커 테스트의 번역기는 명시적인 **테스트 전용 stub**이며 모델 품질 증거가 아니다. 기존 회귀 검사는 명시적인 Tesseract/NLLB 설정으로 실행한다. 새 기본 MangaOCR/Qwen은 별도 실제 세로쓰기 실행과 모바일 브라우저의 데모·두 페이지 업로드로 확인했다. 제품에 가짜 번역기는 없다. 인터넷 URL 어댑터는 소유·허가된 실제 외부 원본이 제공되면 별도의 실사용 검증이 필요하다.

## 주요 파일

```text
frontend/app/          모바일 UI와 뷰어
backend/app.py        인증·업로드·작업·이미지 API
backend/vision.py     OCR → 로컬 번역 → 클리닝 → 한글 식자
backend/sources.py    공개 HTTPS 이미지/매니페스트 어댑터
backend/worker.py     순차 페이지 처리·즉시 공개
backend/store.py      SQLite 작업 상태
scripts/              설치·모델 검증 다운로드·시작
```

코드는 [MIT](LICENSE). MangaOCR·Qwen3(Apache-2.0), llama.cpp(MIT), Tesseract/학습 데이터(Apache-2.0), 선택적 NLLB 600M 가중치(CC-BY-NC-4.0, 개인·비상업용), 선택적 M2M100/fairseq(MIT), OpenCV(Apache-2.0), Pillow(HPND), Noto CJK(SIL OFL) 등 모델·라이브러리·폰트의 별도 라이선스도 따른다. 입력 작품의 권리는 해당 권리자에게 있다. 이 저장소의 테스트 그림은 자체 생성된 작품이며 MIT 조건으로 사용 가능하다.
