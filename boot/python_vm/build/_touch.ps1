$files = @(
  'F:\Pension Person Details\UmerOS\boot\python_vm\Programs\main.c',
  'F:\Pension Person Details\UmerOS\boot\python_vm\VM\vm.c',
  'F:\Pension Person Details\UmerOS\boot\python_vm\Compiler\compiler.c'
)
foreach ($f in $files) {
  (Get-Item $f).LastWriteTime = Get-Date
  Write-Host "Touched: $f"
}
