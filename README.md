## 실행 화면
![DLCP Batch Analyzer](screenshots/main.png)# DLCP Batch Analyzer

DLCP 측정 데이터를 빠르게 일괄 분석하기 위해 만든 Windows GUI 프로그램입니다.

## 프로젝트 배경
기존에는 여러 Bias/Vac 조건의 CSV 데이터를 개별적으로 정리하고
fitting과 carrier density 계산을 반복해야 했습니다.

이 반복 작업을 줄이고 분석 실수를 줄이기 위해
CSV 자동 인식, polynomial fitting, N_CV / N_DL 계산,
profile 시각화를 하나의 프로그램으로 통합했습니다.

## 주요 기능
- 여러 CSV/TSV 일괄 분석
- 파일명에서 DC Bias / Vac 자동 인식
- DLCP 2차 polynomial fitting
- N_CV / N_DL 자동 계산
- depletion width 계산
- bias profile 그래프 생성
- 분석 결과 CSV 저장
- Windows EXE 빌드 지원

## 사용 기술
- Python
- Tkinter
- CSV 데이터 처리
- Numerical fitting
- PyInstaller
- Git / GitHub

## 문제 해결
### 1. 반복 CSV 처리 자동화
기존에는 각 Vac 데이터를 수동으로 입력해야 했습니다.

파일명 규칙을 파싱해 Bias와 Vac를 자동 추출하도록 구현했습니다.

### 2. 여러 capacitance 데이터 처리
CSV 구조가 파일마다 조금씩 다른 문제를 해결하기 위해
capacitance 행/열을 자동 탐색하고 반복 측정값은 평균 처리하도록 구현했습니다.

### 3. N_CV / N_DL 계산
분석 과정에서 단위와 voltage convention이 결과에 영향을 주기 때문에
GUI에서 capacitance unit과 Vac convention을 명시하도록 설계했습니다.

## 실행 방법

python dlcp_gui.py

## EXE 빌드

.\build_exe.ps1

## 테스트

python test_dlcp.py

## 향후 개선
- 입력 CSV 포맷 자동 판별 강화
- fitting quality 지표 추가
- GUI UX 개선
- 여러 측정 결과 비교 기능 추가

## 실제 장비 CSV 사용 순서

1. `Bias 폴더 추가`를 누르고 한 Bias 폴더를 선택하거나, 여러 Bias 폴더가 들어 있는 공통 상위 폴더를 한 번 선택합니다. 하위의 CSV가 모두 추가되며, 파일명이 `-175mV 20mV...`, `-175mV 40mV...` 형식이면 Bias와 Vac가 자동 입력됩니다. 개별 CSV는 `CSV 추가`로도 넣을 수 있습니다.
2. x 열에서 `[Filename] Vac`를 선택하고, y 열에서 `[Auto-average capacitance]`를 선택합니다.
3. C unit을 실제 CSV 단위로 지정합니다. `capacitance_F`라면 `F`입니다.
4. epsilon_r, Area를 입력한 뒤 `전체 파일에 ε/Area 적용`을 누릅니다. 이후 추가하는 CSV도 이 소자값을 자동으로 유지하며, Bias/Vac는 파일명에서 자동 인식합니다.
5. `분석 실행`을 누르면 10개 파일이 하나의 Bias group으로 묶여 평균 capacitance 10점을 만들고 order-2 fitting을 수행합니다.
6. 현재 CSV를 삭제해도 분석 결과는 유지됩니다. 왼쪽 Preview의 `저장된 Bias preview`에서 기존 Bias를 다시 선택할 수 있습니다.
7. 여러 Bias 결과가 누적된 뒤 `N_CV / N_DL vs W 그래프`를 누르면 새 창에서 `10^16`–`10^19 cm^-3` 로그축 overlay plot을 열고 PNG로 저장할 수 있습니다. 로그축 특성상 그래프는 Summary의 absolute density를 사용하며, signed 값은 CSV에 별도로 보존됩니다.

서로 다른 DC bias의 10개 세트를 같이 추가하면 파일명에서 bias별로 자동 그룹화되어 nominal bias 기준 N_CV를 계산합니다. 한 group만 있는 경우에는 CSV 내부 `bias_V`를 이용한 local N_CV를 fallback으로 사용하며, summary의 `N_CV_method` 열에서 계산 방법을 확인할 수 있습니다.

## 주의

입력 capacitance 단위를 GUI에서 정확히 지정해야 하며, 내부 계산은 F와 SI 단위로 변환됩니다. 논문 본문은 Eq. (11)-(12)의 `dV`를 peak-to-peak voltage라고 명시하지만, 장비 화면의 `Vac`는 peak 또는 RMS amplitude로 표시될 수 있으므로 GUI에서 입력 convention을 선택해야 합니다. `[Filename] Vac`를 선택하면 파일명에서 읽은 Vac가 사용됩니다. `N_DL`의 signed와 absolute 값을 모두 저장해 C1 부호 convention을 확인할 수 있게 했습니다. `N_CV`는 bias별 `C0`를 smoothing한 뒤 `dC/dV`를 계산하므로, smoothing window를 너무 크게 설정하면 공간 profile이 과도하게 평활화될 수 있습니다.
