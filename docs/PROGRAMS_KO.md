# 프로그램별 실행 및 검증 안내

## DLCP Research Studio V17.2

ZIP을 모두 풀고 `DLCP_Research_Studio_V17_2.exe`를 실행합니다. CSV 또는 바이어스별 폴더를 불러오고 입력 열·단위·면적·유전율·AC amplitude 기준을 확인한 다음 분석 및 내보내기를 수행합니다.

DLCP 다항식 피팅, 농도·폭 계산과 EIS 등가회로 피팅을 지원합니다. 바이어스 간 공통 모델과 피팅 진단을 확인하세요. 2026-10-08 테스트 73개 및 EXE 합성 2바이어스 자가검사가 통과했습니다. Cj/Cother 추출의 식별 가능성과 물리적 의미는 자동 피팅만으로 보증하지 않습니다.

## MFIA DLCP Control 1.4

ZIP을 풀고 `MFIA_DLCP_Control_1_4.exe`를 실행합니다. MFIA 연결, 장비 식별, 전압 범위, 주파수와 AC amplitude 표현 및 저장 위치를 확인한 뒤 사용합니다.

패키지 기록은 테스트 74개 통과/1 skip입니다. EXE GUI는 빌드 환경의 Tcl 접근 오류로 검증되지 않았으므로, 첫 사용 시 초기 화면과 설정을 확인해야 합니다. 사용자 보고의 610포인트 약 75분 취득은 실사용 사례이며 모든 조건의 처리 시간이나 정확도를 의미하지 않습니다. R²는 피팅 품질 지표입니다. 원격 제어 개발본 1.5는 이번 배포에 포함하지 않았습니다.

## Measurement Plot Studio 2.1.1

ZIP을 모두 풀고 `Measurement_Plot_Studio.exe`를 실행합니다. **`_internal` 폴더를 EXE 옆에 유지하세요.** CSV·폴더를 추가하고 열 매핑과 입력 단위를 확인한 뒤 C–V/C–F/I–V/DLCP/EIS 보기를 선택합니다. PNG/SVG/PDF와 그래프 설정을 저장할 수 있습니다.

`examples_synthetic`은 합성 예제입니다. 테스트 33개, GUI·내보내기 및 EXE 자가검사가 통과했습니다. 기본 로그는 EXE 옆 `output/plot_studio.log`에 생성됩니다.

## 배포 범위

세 프로그램은 Python 없이 사용하는 Windows x64 배포본입니다. 기존 EXE 바이트는 유지하고 배포 ZIP에서 개발용 소스, 실행 로그와 연구 데이터 fixture를 제외했습니다. 검증 요약과 SHA-256은 ZIP 내부 또는 Release의 `SHA256SUMS.txt`를 확인하세요.

현재 저장소의 Python 코드는 과거 V7입니다. 최신 소스 공개 및 재현 가능한 빌드 환경 공개는 별도 작업입니다. 소스·합성 데이터·공개 가능한 화면 예시를 추가할 때 연구 자료의 공개 범위를 확인합니다.
