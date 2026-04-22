@echo off
setlocal

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

:MENU
cls
echo.
echo  +======================================================+
echo  :  Webtoon Review Chatbot - Dev Launcher               :
echo  +======================================================+
echo  :                                                      :
echo  :   1.  전체 시작 (DB + Redis + Backend + Frontend)    :
echo  :   2.  인프라만 (DB + Redis)                          :
echo  :   3.  백엔드만 (FastAPI dev server)                  :
echo  :   4.  프론트엔드만 (Next.js dev server)              :
echo  :   5.  DB 마이그레이션 (Alembic upgrade head)         :
echo  :                                                      :
echo  :   6.  백엔드 테스트 (pytest)                         :
echo  :   7.  프론트엔드 테스트 (vitest)                     :
echo  :   8.  전체 테스트 (backend + frontend)               :
echo  :   9.  프론트엔드 빌드 (next build)                   :
echo  :                                                      :
echo  :  10.  Docker 전체 시작 (compose up)                  :
echo  :  11.  Docker 전체 종료 (compose down)                :
echo  :  12.  Docker 로그 (compose logs -f)                  :
echo  :                                                      :
echo  :  13.  초기 설정 (패키지 설치 + .env + DB 마이그레이션):
echo  :                                                      :
echo  :   0.  종료                                           :
echo  :                                                      :
echo  +======================================================+
echo.
set /p "CHOICE=  선택 [0-13]: "

if "%CHOICE%"=="1" goto ALL_START
if "%CHOICE%"=="2" goto INFRA
if "%CHOICE%"=="3" goto BACKEND
if "%CHOICE%"=="4" goto FRONTEND
if "%CHOICE%"=="5" goto MIGRATE
if "%CHOICE%"=="6" goto TEST_BACKEND
if "%CHOICE%"=="7" goto TEST_FRONTEND
if "%CHOICE%"=="8" goto TEST_ALL
if "%CHOICE%"=="9" goto BUILD_FRONTEND
if "%CHOICE%"=="10" goto DOCKER_UP
if "%CHOICE%"=="11" goto DOCKER_DOWN
if "%CHOICE%"=="12" goto DOCKER_LOGS
if "%CHOICE%"=="13" goto INIT_SETUP
if "%CHOICE%"=="0" goto EXIT
echo  잘못된 입력입니다.
timeout /t 2 /nobreak >nul 2>&1
goto MENU


:: ========================================================
:: 1. 전체 시작
:: ========================================================
:ALL_START
echo.
call :KILL_PORT 8000
call :KILL_PORT 3000
echo  [1/3] 인프라 시작 (DB + Redis)...
call :START_INFRA
echo  [2/3] 백엔드 시작...
start "Backend" /d "%ROOT%\backend" cmd /k "call .venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo    Backend: http://localhost:8000
echo    API Docs: http://localhost:8000/docs
timeout /t 3 /nobreak >nul 2>&1
echo  [3/3] 프론트엔드 시작...
start "Frontend" /d "%ROOT%\frontend" cmd /k "npm run dev"
echo    Frontend: http://localhost:3000
echo.
echo  전체 시작 완료! 각 창을 닫으면 서버가 종료됩니다.
echo.
pause
goto MENU


:: ========================================================
:: 2. 인프라만
:: ========================================================
:INFRA
echo.
call :START_INFRA
echo.
echo  인프라 시작 완료!
echo   DB: localhost:5432  Redis: localhost:6379
echo.
pause
goto MENU


:: ========================================================
:: 3. 백엔드만
:: ========================================================
:BACKEND
echo.
call :KILL_PORT 8000
echo  백엔드 시작 중...
cd /d "%ROOT%\backend"
if not exist ".venv\Scripts\activate.bat" (
    echo  venv이 없습니다. 13번 초기 설정을 먼저 실행하세요.
    pause
    goto MENU
)
call .venv\Scripts\activate.bat
echo    http://localhost:8000
echo    http://localhost:8000/docs
echo    Ctrl+C로 종료
echo.
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pause
goto MENU


:: ========================================================
:: 4. 프론트엔드만
:: ========================================================
:FRONTEND
echo.
call :KILL_PORT 3000
echo  프론트엔드 시작 중...
cd /d "%ROOT%\frontend"
if not exist "node_modules" (
    echo  node_modules이 없습니다. 13번 초기 설정을 먼저 실행하세요.
    pause
    goto MENU
)
echo    http://localhost:3000
echo    Ctrl+C로 종료
echo.
npm run dev
pause
goto MENU


:: ========================================================
:: 5. DB 마이그레이션
:: ========================================================
:MIGRATE
echo.
echo  Alembic 마이그레이션 실행 중...
cd /d "%ROOT%\backend"
call .venv\Scripts\activate.bat
alembic upgrade head
if errorlevel 1 (
    echo  마이그레이션 실패. DB가 실행 중인지 확인하세요.
) else (
    echo  마이그레이션 완료!
)
echo.
pause
goto MENU


:: ========================================================
:: 6. 백엔드 테스트
:: ========================================================
:TEST_BACKEND
echo.
echo  백엔드 테스트 실행 중...
cd /d "%ROOT%\backend"
call .venv\Scripts\activate.bat
pytest tests/ -v --tb=short --cov=app --cov-report=term-missing
echo.
pause
goto MENU


:: ========================================================
:: 7. 프론트엔드 테스트
:: ========================================================
:TEST_FRONTEND
echo.
echo  프론트엔드 테스트 실행 중...
cd /d "%ROOT%\frontend"
npx vitest run
echo.
pause
goto MENU


:: ========================================================
:: 8. 전체 테스트
:: ========================================================
:TEST_ALL
echo.
echo  === 백엔드 테스트 ===
cd /d "%ROOT%\backend"
call .venv\Scripts\activate.bat
pytest tests/ -v --tb=short
set "BE_RESULT=%ERRORLEVEL%"
echo.
echo  === 프론트엔드 테스트 ===
cd /d "%ROOT%\frontend"
npx vitest run
set "FE_RESULT=%ERRORLEVEL%"
echo.
echo  === 프론트엔드 빌드 ===
npx next build
set "BUILD_RESULT=%ERRORLEVEL%"
echo.
echo  ======================================
echo    결과 요약
echo  ======================================
if %BE_RESULT% EQU 0 (echo   Backend  테스트: PASS) else (echo   Backend  테스트: FAIL)
if %FE_RESULT% EQU 0 (echo   Frontend 테스트: PASS) else (echo   Frontend 테스트: FAIL)
if %BUILD_RESULT% EQU 0 (echo   Frontend 빌드:  PASS) else (echo   Frontend 빌드:  FAIL)
echo  ======================================
echo.
pause
goto MENU


:: ========================================================
:: 9. 프론트엔드 빌드
:: ========================================================
:BUILD_FRONTEND
echo.
echo  프론트엔드 프로덕션 빌드 중...
cd /d "%ROOT%\frontend"
npx next build
if errorlevel 1 (
    echo  빌드 실패.
) else (
    echo  빌드 성공!
)
echo.
pause
goto MENU


:: ========================================================
:: 10. Docker 전체 시작
:: ========================================================
:DOCKER_UP
echo.
echo  Docker Compose 전체 시작...
cd /d "%ROOT%"
docker compose up -d
echo.
echo  실행 상태:
docker compose ps
echo.
echo   DB:         localhost:5432
echo   Redis:      localhost:6379
echo   Backend:    http://localhost:8000
echo   Frontend:   http://localhost:3000
echo   Grafana:    http://localhost:3002
echo   Langfuse:   http://localhost:3001
echo   Prometheus: http://localhost:9090
echo.
pause
goto MENU


:: ========================================================
:: 11. Docker 전체 종료
:: ========================================================
:DOCKER_DOWN
echo.
echo  Docker Compose 종료 중...
cd /d "%ROOT%"
docker compose down
echo  종료 완료!
echo.
pause
goto MENU


:: ========================================================
:: 12. Docker 로그
:: ========================================================
:DOCKER_LOGS
echo.
echo  Docker Compose 로그 (Ctrl+C로 종료)...
cd /d "%ROOT%"
docker compose logs -f --tail=50
pause
goto MENU


:: ========================================================
:: 13. 초기 설정
:: ========================================================
:INIT_SETUP
echo.
echo  +======================================+
echo  :       초기 개발 환경 설정            :
echo  +======================================+
echo.

echo  [1/6] .env 파일 확인...
if not exist "%ROOT%\backend\.env" (
    if exist "%ROOT%\.env.example" (
        copy "%ROOT%\.env.example" "%ROOT%\backend\.env" >nul
        echo    .env.example 복사 완료
        echo    backend/.env 파일에서 SECRET_KEY 등을 수정하세요!
    ) else (
        echo    .env.example이 없습니다. 수동으로 backend/.env를 생성하세요.
    )
) else (
    echo    backend/.env 이미 존재 - 건너뜀
)

echo  [2/6] Python 가상환경 확인...
cd /d "%ROOT%\backend"
if not exist ".venv\Scripts\activate.bat" (
    echo    가상환경 생성 중...
    python -m venv .venv
    echo    .venv 생성 완료
) else (
    echo    .venv 이미 존재 - 건너뜀
)

echo  [3/6] Python 패키지 설치 중...
call .venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
echo    pip install 완료

echo  [4/6] Node.js 패키지 설치 중...
cd /d "%ROOT%\frontend"
if not exist "node_modules" (
    npm install
    echo    npm install 완료
) else (
    echo    node_modules 이미 존재 - 건너뜀
)

echo  [5/6] 인프라 시작 (DB + Redis)...
call :START_INFRA

echo  [6/6] DB 마이그레이션...
cd /d "%ROOT%\backend"
call .venv\Scripts\activate.bat
alembic upgrade head
if errorlevel 1 (
    echo    마이그레이션 실패 - DB 준비 후 5번으로 재시도
) else (
    echo    마이그레이션 완료
)

echo.
echo  ======================================
echo    초기 설정 완료!
echo  ======================================
echo.
echo   다음 단계:
echo    1. backend/.env 파일에서 SECRET_KEY 등 환경변수 확인
echo    2. 메뉴 1번으로 전체 시작
echo    3. http://localhost:3000 접속
echo.
pause
goto MENU


:: ========================================================
:: 유틸: 인프라 시작
:: ========================================================
:START_INFRA
cd /d "%ROOT%"

if not exist "backend\.env" (
    if exist ".env.example" (
        copy ".env.example" "backend\.env" >nul
        echo    .env.example 자동 복사됨
    )
)

if not exist ".env" (
    if exist "backend\.env" (
        copy "backend\.env" ".env" >nul
    )
)

docker compose up -d db redis
echo    DB/Redis 헬스체크 대기 중...

set /a "WAIT=0"
:WAIT_LOOP
if %WAIT% GEQ 30 (
    echo    헬스체크 타임아웃. docker compose ps 로 상태를 확인하세요.
    goto :eof
)
docker compose ps db 2>nul | findstr "healthy" >nul 2>&1
if not errorlevel 1 (
    echo    DB ready
    docker compose ps redis 2>nul | findstr "healthy" >nul 2>&1
    if not errorlevel 1 (
        echo    Redis ready
        goto :eof
    )
)
timeout /t 2 /nobreak >nul 2>&1
set /a "WAIT+=2"
goto WAIT_LOOP


:: ========================================================
:: 유틸: 포트 점유 프로세스 종료
:: ========================================================
:KILL_PORT
:: %~1 = port number
set "_KILL_FOUND=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%~1 " ^| findstr "LISTEN" 2^>nul') do (
    if not "%%a"=="0" (
        taskkill /F /PID %%a >nul 2>&1
        set "_KILL_FOUND=1"
    )
)
if "%_KILL_FOUND%"=="1" (
    echo    Port %~1 - 기존 프로세스 종료됨.
    timeout /t 1 /nobreak >nul 2>&1
) else (
    echo    Port %~1 - 사용 가능.
)
goto :eof


:: ========================================================
:EXIT
echo.
echo  종료합니다.
endlocal
pause
exit /b 0
