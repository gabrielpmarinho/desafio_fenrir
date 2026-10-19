@echo off
rem Rotina diaria da Mesa (Terminal Fenrir) para o Agendador de Tarefas do Windows.
rem Roda puxar_precos -> liquidar_semana (1o dia util da semana) -> fechar_dia,
rem recupera dias perdidos e grava tudo em logs\rotina_AAAA-MM.log.
rem Registrar a tarefa: ver README, secao "Rotina da Mesa".

setlocal
cd /d "%~dp0.."

rem Python do ambiente do projeto. Se usar venv, troque por: .venv\Scripts\python.exe
set PYTHON=python

if not exist logs mkdir logs
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM"') do set MES=%%i
set LOG=logs\rotina_%MES%.log

set PYTHONIOENCODING=utf-8
echo ===== %date% %time% ===== >> "%LOG%"
%PYTHON% manage.py rotina_diaria >> "%LOG%" 2>&1
set CODIGO=%ERRORLEVEL%
rem Backup mesmo se a rotina falhou: o que ja estava gravado continua valendo.
%PYTHON% manage.py backup_banco >> "%LOG%" 2>&1
if not %CODIGO%==0 echo [FALHA] codigo %CODIGO% >> "%LOG%"
exit /b %CODIGO%
