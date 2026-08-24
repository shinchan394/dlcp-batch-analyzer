# DLCP Batch Analyzer

바이어스별 DLCP CSV를 한 번에 처리하는 Windows GUI입니다. 외부 Python 패키지 없이 Tkinter로 동작하도록 만들었습니다.

## 기능

- 여러 CSV/TSV 파일 일괄 입력
- Bias 폴더 하나 또는 여러 Bias 폴더가 들어 있는 상위 폴더를 선택하면 하위 CSV를 재귀적으로 일괄 입력
- 상대 유전상수 `epsilon_r`와 소자 면적 `cm²`를 한 번 설정하면 이후 추가 CSV에 자동 상속
- 파일명이 `DC Bias Vac_...csv`인 경우 앞의 전압을 DC bias, 뒤의 전압을 Vac로 자동 인식
- CSV에 Vac 열이 없으면 파일명 Vac를 x축으로 사용
- 두 개 이상의 반복 capacitance 행 또는 capacitance 열은 자동 평균
- CSV에서 Vac와 capacitance 열 선택 또는 `[Auto-average capacitance]` 선택
- 논문 기준 `dV`는 peak-to-peak로 취급하며, 입력이 peak amplitude 또는 RMS amplitude이면 자동으로 peak-to-peak로 변환
- 각 파일의 `C(dV_pp) = C0 + C1·dV_pp + C2·dV_pp²` order-2 least-squares fitting
- 파일 내부 raw/smoothed/fitted capacitance와 fit derivative 출력
- Bias 순서의 `C0`, `C1` smoothing 및 bias derivative 출력
- `N_CV = 2C³/(q·epsilon·A²·dC/dV)` 자동 계산
- `N_DL = C0³/(2q·epsilon·A²·C1)` 및 부호 진단용 signed/absolute 값 출력
- `W = epsilon·epsilon0·A/C0` depletion width를 nm 단위로 출력
- CSV 내부 `bias_V`가 있으면 단일 nominal bias group에서도 `C vs bias_V` derivative로 N_CV를 계산
- 여러 bias group을 넣으면 `|N_CV| / |N_DL|`을 `W (nm)`에 대해 overlay하는 log-y 그래프 제공 (`10^16`–`10^19 cm^-3` 고정 눈금)
- Summary 표/CSV에서는 불필요한 File 열을 제거하고 Bias별 결과만 표시
- 분석한 Bias 결과를 메모리에 누적 보관하여 현재 CSV를 삭제해도 summary와 preview에서 다시 선택 가능
- profile 그래프는 별도 창에서 열리며, 발표/논문용 1600×1000 PNG로 저장 가능
- 요약 CSV, 파일별 detail CSV, 입력 설정 기록 저장
- 10개 Vac CSV를 같은 DC bias group으로 묶어 하나의 DLCP polynomial fitting으로 처리
- CSV를 파일당 한 번만 파싱하고 preview/batch 사이에 캐시하여 반복 실행 속도 개선

## 실행

```powershell
python dlcp_gui.py
```

Windows에서 단일 EXE를 만들려면 PyInstaller가 설치된 환경에서 다음을 실행합니다.

```powershell
.\build_exe.ps1
```

생성 파일은 `dist\DLCP_Batch_Analyzer.exe`입니다.

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
