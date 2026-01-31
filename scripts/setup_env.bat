@echo off
echo Setting up environment...
if not exist .env (
    echo Creating .env from template...
    copy .env.template .env
)
echo Installing dependencies...
pip install -r requirements.txt
echo Setup complete.
pause
