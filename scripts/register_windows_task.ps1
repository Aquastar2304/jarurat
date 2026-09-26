# Registers a Windows Task Scheduler job that runs the pipeline every day.
# Usage (from the project folder, in PowerShell):
#   .\scripts\register_windows_task.ps1            # default 09:00
#   .\scripts\register_windows_task.ps1 -At 18:30
# Remove with:  Unregister-ScheduledTask -TaskName "LeadGenAutomation" -Confirm:$false

param([string]$At = "09:00")

$project = Split-Path -Parent $PSScriptRoot
$python  = (Get-Command python).Source

$action  = New-ScheduledTaskAction -Execute $python -Argument "main.py" -WorkingDirectory $project
$trigger = New-ScheduledTaskTrigger -Daily -At $At
Register-ScheduledTask -TaskName "LeadGenAutomation" -Action $action -Trigger $trigger `
    -Description "Collects, cleans and exports organisation leads to output/leads.xlsx" -Force

Write-Host "Task 'LeadGenAutomation' registered to run daily at $At from $project"
