# v3.76 공개 영상 목록 런타임 후보

이 복사본은 v3.74를 기반으로 공식 목록·영상 원문의 증거를 담는 선택적 sourceProof 필드를 지원한다. 주간 자동 배치에는 짝이 맞는 앱 overlay가 필요하다. 기존 검수표는 그대로 두며 sourceProof는 실재생 검수로 해석하지 않는다. 피스TV 선두 방송에는 공개 Vimeo oEmbed 확인 1회가 추가되어 아래 v3.74 기준 최대 요청 수는 75회에서 76회가 된다. 운영 방식은 기존안이고 이 후보는 로컬에서만 검증했다.

2026-11-15. 가족예배 앱 v3.73의 12개 공식 목록과 공개 재생 검수표를 재사용한다. seed.json은 기존 정적 목록과 동일한 37,715바이트 JSON이다. 이전 앱 이용자에게 기존 영상이 사라지지 않도록 152개 분류 항목과 기존 검수 근거를 함께 보관한다. 영상·가족 자료·앱 본체·키는 포함하지 않는다.

## 운영 방식

GitHub의 표준 ubuntu-latest 실행자가 토요일 19:30 UTC(한국 일요일 04:30)에 공개 원문을 수집한다. 최대 원문 요청은 피스TV 목록 1+상세 8, YouTube 목록 11+상세 55, 총 75회다. 무료 Worker의 Cron당 CPU 10ms, 외부 요청 50회에 전체 수집을 한 번에 넣을 수 없다. 512KiB로 제한된 공개 결과 한 파일을 Worker가 6시간마다 1회 읽고 KV에 반영한다. GitHub 수집이 지연되면 다음 동기화 때 반영한다. 수집기는 Linux의 Python 표준 라이브러리와 프로세스 내 메모리 DB를 쓴다. 영속 상태는 catalog-state 브랜치의 archive.json 및 Git 이력이다. Windows 실행자, 개인 DB, Cloudflare API 토큰을 CI에 제공할 필요가 없다. [Worker 한도](https://developers.cloudflare.com/workers/platform/limits/) · [GitHub Actions 과금 조건](https://docs.github.com/en/billing/concepts/product-billing/github-actions)

각 공급원은 기존 목록 식별자·목록 소유자·게시일 확인 방식을 사용한다. 피스TV는 제목·한국어 목록·상세 등록일을 대조한다. 리디렉션은 따르지 않는다. 새 영상은 직접 선택용 메타데이터로 들어간다. 자동 선곡 검수표는 배포된 seed와 일치해야 한다. 부분 수집은 확인된 항목만 병합한다. 로그인·429·실패에는 마지막 자료와 마지막 정상 확인 시각을 유지한다. 모든 공급원 실패, 후보 크기 초과, 검증 실패 시 게시를 중단한다.

CI는 공개 전용 저장소 하나의 contents:write만 요청하며 고정된 catalog-state 브랜치에 archive.json만 fast-forward push한다. GitHub 토큰 자체는 브랜치 단위 권한이 아니므로 소유자가 기본 브랜치 보호와 전용 저장소 분리를 적용해야 한다. CI는 동시에 한 번만 게시한다. 현재·직전 상태는 한 Git 커밋과 한 KV 값으로 전환한다. KV 읽기의 지역별 시차가 있으므로 전체 지역 동시 전환은 보장하지 않는다. 각 응답은 한 버전의 전체 JSON이다. [KV 일관성](https://developers.cloudflare.com/kv/concepts/how-kv-works/)

## 소유자 적용 순서

1. 공개 영상 메타데이터 전용 GitHub 저장소를 준비하고 이 패키지만 기본 브랜치에 넣는다. 기본 브랜치에서 catalog-state 브랜치를 한 번 만든다. archive.json이 없는 첫 실행은 seed에서 시작한다. 기본 브랜치를 보호하고, Actions가 전용 저장소의 catalog-state에 쓰도록 허용한다. 기존 앱 저장소나 가족 파일을 복사하지 않는다.
2. GitHub Actions의 **Collect public media → Run workflow**를 기본 브랜치에서 실행한다. catalog-state/archive.json에 revision, current, previous가 생겼는지 확인한다. 주간 자동 실행은 워크플로가 기본 브랜치에 있어야 한다. 공용 저장소 무료 표준 실행자 적용 여부와 조직 정책은 소유자 계정에서 확인한다.
3. Cloudflare에서 무료 Workers·KV 가용량을 확인하고 전용 KV namespace 하나를 만든다. wrangler.toml의 id와 CATALOG_REPO를 각각 namespace ID와 실제 owner/repository로 교체한다. 소유자의 로컬 Wrangler에서 이 폴더를 기준으로 wrangler deploy를 실행한다. Cron 설정은 매 6시간의 37분(UTC)이다. 공개 Worker 주소는 비활성화돼 있다.
4. 기존 Pages 프로젝트의 functions/weekly-public-archive.json.js를 이 패키지의 동명 파일로 적용한다. 서비스 바인딩 이름 MEDIA_READER의 대상으로 family-worship-public-media를 지정한다. 기존 정적 weekly-public-archive.json을 유지하고 Pages에 다시 배포한다. 저장소 기반 빌드 또는 Functions를 지원하는 Wrangler Pages 배포를 사용한다. 기존 앱 JS의 같은 출처 상대 경로가 그대로 동작한다. [Pages 바인딩](https://developers.cloudflare.com/pages/functions/bindings/)
5. 첫 Cron 실행 후 Pages의 /weekly-public-archive.json에 GET 또는 HEAD를 보내 X-Catalog-State가 current인지 확인한다. previous는 직전 버전 복구, seed는 초기값 또는 두 버전 사용 불가다. 해당 헤더가 없으면 정적 대체 경로를 확인한다. POST는 405여야 한다. Worker CPU·오류·KV 사용량과 게시 지연을 첫 실행에서 확인한다.

## 복구

KV 저장 실패는 기존 값을 보존한다. 현재 버전의 해시가 맞지 않으면 직전 정상본을 읽고, 다음 정상 동기화가 같은 revision도 복구한다. 두 버전이 모두 손상되면 내장 seed로 응답한다. Pages 바인딩 실패 시 기존 정적 파일을 제공한다. 수집 오류는 각 분류의 status·checked·lastSuccess·observation에서 확인한다. 공급원 차단 시 로그인을 시도하거나 재생 검수 상태를 바꾸지 않는다.

운영자가 내용 자체를 되돌리려면 예약 수집을 잠시 중지하고 catalog-state의 마지막 정상 커밋에서 current를 가져온다. 새 archive.json의 revision은 현재보다 1 크게, previous는 지금 current, current는 복원할 정상본으로 설정한다. 기본 브랜치 코드로 node verify-publication.mjs 복원파일경로를 실행하고 catalog-state에 일반 커밋으로 게시한다. 다음 동기화에서 반영된 것을 확인한 후 예약 수집을 재개한다. Git 이력 강제 되감기나 KV 삭제는 필요 없다.

## 검증

python collector/test.py와 node test.mjs는 오프라인 모의 수집, 429·로그인·봇 차단, 두 번의 버전 전환, 검수표 변경 차단, 저장 실패, 복구, Pages 읽기·쓰기 거절을 검사한다. node test-runtime.cjs는 로컬 Miniflare 4 모듈 경로를 인자로 받아 실제 workerd의 scheduled 및 fetch 처리와 로컬 KV를 검사한다. 계정 연결, 클라우드 실행 시간, 운영 GitHub IP에서 공급원의 응답, 실제 예약 실행과 Pages 배포는 미검증이다. 무료 제공량 초과나 차단 시 이전 자료로 서비스하며 유료 플랜 전환은 소유자가 결정한다.
