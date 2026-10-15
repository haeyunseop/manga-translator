# 과거 네트워크 차단 (해결됨)

**해결됨:** 최신 환경 게시 후 공식 CDN이 HTTP 200으로 응답했고 NLLB 다운로드·해시 검증, 전체 설치, 실제 번역·식자 검사가 성공했다. 아래는 과거 진단이며 현재 추가 허용이나 반복 게시가 필요하다는 뜻이 아니다.

아래는 2026-10-15의 해결 전 기록이다.

- 게시된 설정 버전: `81d5b6c8-ca6a-48a6-a4b8-a4511bf19576~cecfgver_6ad057c97f0081959819dc1f8908713a`
- 현재 초안: 없음. 게시된 `network_policy.egress_rules`에 `us.aws.cdn.hf.co`가 포함됨.
- `huggingface.co`: HTTP 200. 공식 M2M100 config/generation config 다운로드·검증 성공.
- `cas-server.xethub.hf.co`: 연결 성공, 루트 경로 HTTP 404. 서비스 루트가 없다는 응답이며 프록시 차단이 아님.
- `us.aws.cdn.hf.co`: TLS 연결 전에 프록시의 CONNECT 응답 HTTP 403, 본문 `Domain forbidden`.
- 공식 Hugging Face Python 다운로드: 같은 ProxyError로 실패. 실제 418M 가중치는 설치되지 않음.
- 공식 Xet 다운로드도 같은 CDN을 사용하므로 해결되지 않음. TLS 검증/체크섬 검증을 해제하지 않았고 프록시를 우회하지 않았음.
- 백엔드 검증: 40 passed, 1 real-model skipped. 번역 성공으로 계산하지 않음.

이는 “허용 목록에 주소를 아직 넣지 않았다”는 상태가 아니다. 저장된 설정과 실행 머신의 정책 반영 또는 플랫폼 차단을 확인해야 한다. 동일한 게시를 반복해도 해결된다고 안내하지 않는다. 현재 노출된 도구에는 네트워크 사이드카 재시작/정책 갱신 기능이 없다.

정상화 후 저장소 루트에서 `.venv/bin/python scripts/download_models.py`와 `.venv/bin/python -m pytest -q -m real_model -s`를 실행하고, 실제 한국어 최종 이미지와 뷰어 전환을 확인한다. 이 기록에는 비밀번호, OAuth 토큰, 환경 변수 값, 서명된 다운로드 URL을 포함하지 않았다.
