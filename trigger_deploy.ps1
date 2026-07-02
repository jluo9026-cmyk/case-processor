$token = "rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt"
$service = "srv-d916j377f7vs73d6h240"
$body = @{clearCache = "clear"} | ConvertTo-Json
$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}
Write-Host "Checking current deploy status..."
try {
    $result = Invoke-RestMethod -Uri "https://api.render.com/v1/services/$service/deploys?limit=1" -Headers $headers
    Write-Host "Last deploy status: $($result[0].deploy.status)"
    Write-Host "Last deploy created: $($result[0].deploy.createdAt)"
} catch {
    Write-Host "Error checking status: $_"
}

Write-Host "`nTriggering new deploy..."
try {
    $result = Invoke-RestMethod -Uri "https://api.render.com/v1/services/$service/deploys" -Method Post -Body $body -Headers $headers
    Write-Host "Deploy triggered successfully!"
    Write-Host "Deploy ID: $($result.id)"
    Write-Host "Status: $($result.status)"
} catch {
    Write-Host "Error triggering deploy: $_"
}

Write-Host "`nDone! Check https://dashboard.render.com/web/$service for progress"
</write_to_file>