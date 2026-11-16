# Final check. Run from the project root with the virtual environment active:
#     .\scripts\verify.ps1
$ErrorActionPreference = "Continue"

Write-Host "1/4 Running the test suite..."
python -m pytest -q
if ($LASTEXITCODE -ne 0) { Write-Host "TESTS FAILED. Fix them before anything else."; exit 1 }

Write-Host "`n2/4 Checking that the web app imports..."
python -c "from app.main import app; print('app imports OK')"
if ($LASTEXITCODE -ne 0) { Write-Host "APP DOES NOT IMPORT."; exit 1 }

Write-Host "`n3/4 Running the pipeline from the command line on a sample with planted problems..."
python -m app.cli run sample_data/insurance/policies_bad.csv --rules sample_data/insurance/policies_bad.rules.json --show-rejected 3
Write-Host "CLI exit code: $LASTEXITCODE (1 is correct here: the sample has problems on purpose)"
if ($LASTEXITCODE -ne 1) { Write-Host "UNEXPECTED CLI RESULT."; exit 1 }

Write-Host "`n4/4 Git state..."
git status --short
Write-Host "`nAll checks passed."
