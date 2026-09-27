@echo off
rem Deploy Exam Buddy to the Alexa-hosted skill.
rem
rem Copies lambda\ and the interaction model into the hosted skill repo
rem (cloned once with "ask init --hosted-skill-id ...") and pushes it,
rem which deploys the code and builds the voice model.
rem
rem Usage:  deploy.bat [path-to-hosted-repo]
rem         default path: ..\ExamBuddy

setlocal
set "SRC=%~dp0"
set "HOSTED=%~1"
if "%HOSTED%"=="" set "HOSTED=%SRC%..\ExamBuddy"

if not exist "%HOSTED%\.git" (
    echo Hosted skill repo not found at "%HOSTED%".
    echo Clone it first:  ask init --hosted-skill-id amzn1.ask.skill.YOUR-ID
    exit /b 1
)

echo === Pulling latest code from GitHub
git -C "%SRC%." pull --ff-only || goto :fail

where python >nul 2>nul
if %errorlevel%==0 (
    echo === Checking question bank
    python "%SRC%scripts\validate_bank.py" || goto :fail
    python "%SRC%scripts\build.py" --check || goto :fail
) else (
    echo Python not found, skipping question bank checks.
)

rem master deploys to the development stage (the Test tab); prod is the
rem live stage and must not be pushed to directly.
for /f %%b in ('git -C "%HOSTED%" rev-parse --abbrev-ref HEAD') do set "BRANCH=%%b"
if /i not "%BRANCH%"=="master" (
    echo Hosted repo is on branch "%BRANCH%", expected master.
    echo Run:  git -C "%HOSTED%" checkout master
    exit /b 1
)

echo === Copying code and interaction model
robocopy "%SRC%lambda" "%HOSTED%\lambda" /E /XD __pycache__ /NFL /NDL /NJH /NJS /NP
if errorlevel 8 goto :fail
robocopy "%SRC%skill-package\interactionModels" "%HOSTED%\skill-package\interactionModels" /E /NFL /NDL /NJH /NJS /NP
if errorlevel 8 goto :fail

echo === Pushing to the Alexa-hosted repo
for /f %%h in ('git -C "%SRC%." rev-parse --short HEAD') do set "REV=%%h"
git -C "%HOSTED%" add -A || goto :fail
git -C "%HOSTED%" diff --cached --quiet
if %errorlevel%==0 (
    echo Nothing changed since the last deploy.
    exit /b 0
)
git -C "%HOSTED%" commit -q -m "Deploy Exam Buddy %REV%" || goto :fail
git -C "%HOSTED%" push origin master || goto :fail

echo.
echo Pushed. Deployment and model build take a minute or two;
echo watch the Code and Build tabs in the Alexa developer console.
exit /b 0

:fail
echo.
echo Deploy FAILED - see the error above.
exit /b 1
