# ChatGPT Plus 공식 연동 검증 기록

확인일: 2026-10-15. 사용자 API 키·ChatGPT 세션·쿠키·기존 Codex 토큰을 읽거나 추출하지 않았다.

## 수정한 결론

**공식 Sign in with ChatGPT에서 로컬 오픈소스 앱에 ChatGPT 플랜 사용을 허가하는 기능이 존재한다.** 초기에는 Codex 저장소만 확인하고 상세 문서 접근이 차단되어 범용 연동 계약을 확인하지 못했다. 환경 게시 후 공식 SIWC 문서를 직접 확인해 초기 판단을 수정했다. 일반 API 결제가 Plus에 포함되지 않는다는 설명만으로 이 별도의 공식 기능까지 불가능하다고 판단하면 안 된다.

다만 **MangaTrans에는 아직 이 OAuth 연동을 구현·연결·실계정 검증하지 않았다.** 현재 제품의 번역 경로는 NLLB 600M CPU 모델이다. Plus 연동 완료라고 주장하지 않는다.

## 직접 확인한 공식 문서

- [SIWC 개요](https://developers.openai.com/siwc)와 [로컬 OSS 앱](https://developers.openai.com/siwc/token-sharing-open-source): 로컬 오픈소스 앱의 ChatGPT 플랜 사용을 지원한다. 유료 또는 원격 호스팅 앱은 별도 신청을 안내한다.
- [등록과 로그인](https://developers.openai.com/siwc/token-sharing-open-source/sign-in): 최초 dynamic_agent_client 등록, 발급 client ID 저장, 영구 호스트 ID, state/nonce, PKCE S256, 127.0.0.1 loopback callback, ID 토큰 서명·issuer·audience·만료·nonce 및 chatgpt.tokens.use.direct 권한 검증을 요구한다. 이 직접 흐름은 client secret이나 파트너 API 키를 요구하지 않는다.
- [모델과 추론](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference): 승인된 OAuth access token으로 공개 /v1/models를 조회하고 선택된 모델의 공개 /v1/responses를 호출한다. store:false, stream:true와 response.completed 확인이 필요하다. 비공식 backend-api를 사용하지 않는다.
- [자체 호스팅 VM](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms): loopback callback은 브라우저가 실행되는 PC로 돌아간다. 같은 앱의 정식 OAuth 완료 후 보호된 자격 정보를 VM에 안전하게 전달하는 공식 절차가 있다. 채팅으로 토큰을 보내는 방법이 아니다.
- [미리보기 제한](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations): 스트리밍·지원 입력·금지된 요청 필드를 명시한다. 지원 모델은 사용자 계정별로 조회한다.
- [다른 앱에서 ChatGPT 플랜 사용](https://help.openai.com/articles/20001542)과 [ChatGPT Plus](https://help.openai.com/en/articles/6950777-what-is-chatgpt-plus): 별도 동의와 앱별 허용량, 플랜 사용 및 크레딧 설정을 설명한다.

## 현재 제품과 남은 작업

무료 기본 동작을 위해 로컬 모델을 유지한다. 공식 Plus 연동을 추가하려면 PC 측 OAuth, 토큰 보관·회전·권한 검사, 계정별 모델 선택, 사용량·동의 UI, 연결 해제와 스트리밍 실패 테스트가 필요하다. 사용자의 실제 OAuth 동의 없이는 Plus 추론을 검증할 수 없다.

기존 Codex 자격 정보를 빌리거나 다른 앱의 client ID를 재사용하거나, 비공식 세션을 가져오거나, 유료 API로 자동 전환하지 않는다. OAuth 자격 증명을 채팅으로 요청하지 않는다.
