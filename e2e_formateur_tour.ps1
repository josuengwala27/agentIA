$ErrorActionPreference = "Continue"
$Base = "http://127.0.0.1:8000"
$Root = "C:\Users\josue\Documents\agent-formation"
$Sample = Join-Path $Root "sample_cours.txt"
$results = @{}
$failDetails = New-Object System.Collections.Generic.List[string]
$script:token = $null
$script:docId = $null
$script:tempDocId = $null
$script:H = $null

function Assert-True($cond, $msg) {
  if (-not $cond) { throw $msg }
}

function Get-AuthHeaders($tok) {
  return @{ Authorization = ("Bearer " + $tok); "Content-Type" = "application/json" }
}

function Send-Multipart($uri, $tok, $fields, $fileField, $filePath, $timeout) {
  $boundary = [guid]::NewGuid().ToString()
  $LF = "`r`n"
  $enc = [System.Text.Encoding]::UTF8
  $parts = New-Object System.Collections.Generic.List[byte]
  foreach ($key in $fields.Keys) {
    $chunk = "--$boundary$LF" + "Content-Disposition: form-data; name=`"$key`"$LF$LF" + "$($fields[$key])$LF"
    $parts.AddRange($enc.GetBytes($chunk))
  }
  if ($fileField -and $filePath) {
    $fileName = [IO.Path]::GetFileName($filePath)
    $header = "--$boundary$LF" + "Content-Disposition: form-data; name=`"$fileField`"; filename=`"$fileName`"$LF" + "Content-Type: text/plain$LF$LF"
    $parts.AddRange($enc.GetBytes($header))
    $parts.AddRange([IO.File]::ReadAllBytes($filePath))
    $parts.AddRange($enc.GetBytes($LF))
  }
  $parts.AddRange($enc.GetBytes("--$boundary--$LF"))
  $body = $parts.ToArray()
  $resp = Invoke-WebRequest -Uri $uri -Method POST -Headers @{ Authorization = ("Bearer " + $tok) } -ContentType ("multipart/form-data; boundary=" + $boundary) -Body $body -TimeoutSec $timeout -UseBasicParsing
  return ($resp.Content | ConvertFrom-Json)
}

Write-Host "=== A. Prep ==="
try {
  $health = Invoke-RestMethod -Uri "$Base/api/health" -Method GET -TimeoutSec 30 -UseBasicParsing
  Write-Host ("Health: " + ($health | ConvertTo-Json -Compress -Depth 5))
  Assert-True ($null -ne $health) "health empty"

  $loginBody = '{"email":"formateur@demo.local","password":"trainer123"}'
  $login = Invoke-RestMethod -Uri "$Base/api/auth/login/json" -Method POST -Body $loginBody -ContentType "application/json" -TimeoutSec 30 -UseBasicParsing
  $script:token = $login.access_token
  Assert-True ($script:token -and $script:token.Length -gt 10) "no access_token"
  Write-Host ("Login OK tokenLen=" + $script:token.Length)
  $script:H = Get-AuthHeaders $script:token

  try {
    Invoke-RestMethod -Uri "$Base/api/chat/conversations" -Method DELETE -Headers $script:H -TimeoutSec 30 -UseBasicParsing | Out-Null
    Write-Host "Chat history cleared"
  } catch {
    Write-Host ("Clear chat note: " + $_.Exception.Message)
  }

  $docs = Invoke-RestMethod -Uri "$Base/api/documents" -Method GET -Headers $script:H -TimeoutSec 30 -UseBasicParsing
  $docsArr = @($docs)
  Write-Host ("Documents count: " + $docsArr.Count)
  $indexed = @($docsArr | Where-Object { $_.status -eq "indexed" })
  if ($indexed.Count -gt 0) {
    $main = $indexed | Where-Object { $_.title -match "curite" } | Select-Object -First 1
    if (-not $main) { $main = $indexed[0] }
    $script:docId = $main.id
    Write-Host ("Using existing indexed doc id=" + $script:docId + " title=" + $main.title)
  } else {
    Write-Host "No indexed docs - will upload in B"
  }
  $results["A"] = "PASS"
} catch {
  $results["A"] = "FAIL"
  $failDetails.Add("A: " + $_.Exception.Message)
  Write-Host ("A FAIL: " + $_.Exception.Message)
  if ($_.ErrorDetails) { Write-Host $_.ErrorDetails.Message }
}

Write-Host ""
Write-Host "=== B. Upload ==="
try {
  if (-not $script:docId) {
    Assert-True (Test-Path $Sample) ("sample missing: " + $Sample)
    $fields = @{ title = "Securite au travail" }
    # Use proper French title via unicode
    $fields = @{}
    $fields["title"] = ([string]([char]0x0053) + "ecurite au travail")
    # Better: use UTF8 bytes decoded title
    $titleBytes = [byte[]](0x53,0xC3,0xA9,0x63,0x75,0x72,0x69,0x74,0xC3,0xA9,0x20,0x61,0x75,0x20,0x74,0x72,0x61,0x76,0x61,0x69,0x6C)
    $titleFr = [System.Text.Encoding]::UTF8.GetString($titleBytes)
    $up = Send-Multipart "$Base/api/documents/upload" $script:token @{ title = $titleFr } "file" $Sample 180
    Write-Host ("Upload: " + ($up | ConvertTo-Json -Compress -Depth 6))
    Assert-True ($up.status -eq "indexed") ("upload status=" + $up.status + " not indexed")
    $script:docId = $up.id
    Write-Host ("Uploaded main docId=" + $script:docId)
  } else {
    Write-Host ("Skip main upload, docId=" + $script:docId)
  }

  $tempPath = Join-Path $Root "temp_delete.txt"
  Set-Content -Path $tempPath -Value "fichier temporaire a supprimer" -Encoding UTF8
  $up2 = Send-Multipart "$Base/api/documents/upload" $script:token @{ title = "Temp delete test" } "file" $tempPath 180
  $script:tempDocId = $up2.id
  Write-Host ("Temp doc id=" + $script:tempDocId + " status=" + $up2.status)
  Assert-True ($script:tempDocId) "tempDocId missing"
  $results["B"] = "PASS"
} catch {
  $results["B"] = "FAIL"
  $failDetails.Add("B: " + $_.Exception.Message)
  Write-Host "B FAIL FULL ERROR:"
  Write-Host $_.Exception.ToString()
  if ($_.ErrorDetails) { Write-Host $_.ErrorDetails.Message }
  Write-Host "STOP after B upload failure per instructions (continuing other sections if possible)"
}

Write-Host ""
Write-Host "=== C. Chat ==="
try {
  Assert-True ($script:docId) "no docId for chat"
  $chatBody = (@{ message = "Quels sont les principes de prevention?"; document_id = $script:docId } | ConvertTo-Json)
  $chat = Invoke-RestMethod -Uri "$Base/api/chat" -Method POST -Headers $script:H -Body $chatBody -TimeoutSec 180 -UseBasicParsing
  $ans = [string]$chat.answer
  $preview = $ans.Substring(0, [Math]::Min(150, $ans.Length))
  Write-Host ("Answer first 150: " + $preview)
  Assert-True ($ans -notmatch "aucun contenu index") "answer contains aucun contenu indexe"
  $citCount = @($chat.citations).Count
  Write-Host ("citations.Count=" + $citCount)
  Assert-True ($citCount -ge 1) "citations.Count less than 1"
  $results["C"] = "PASS"
} catch {
  $results["C"] = "FAIL"
  $failDetails.Add("C: " + $_.Exception.Message)
  Write-Host ("C FAIL: " + $_.Exception.Message)
  if ($_.ErrorDetails) { Write-Host $_.ErrorDetails.Message }
}

Write-Host ""
Write-Host "=== D. Exercises ==="
try {
  Assert-True ($script:docId) "no docId for exercises"
  $topicBytes = [byte[]](0x70,0x72,0xC3,0xA9,0x76,0x65,0x6E,0x74,0x69,0x6F,0x6E)
  $topicFr = [System.Text.Encoding]::UTF8.GetString($topicBytes)
  $exBody = (@{ document_id = $script:docId; exercise_type = "qcm"; question_count = 3; topic = $topicFr; title = "QCM prevention E2E" } | ConvertTo-Json)
  $ex = Invoke-RestMethod -Uri "$Base/api/exercises/generate" -Method POST -Headers $script:H -Body $exBody -TimeoutSec 180 -UseBasicParsing
  Write-Host ("Exercise id=" + $ex.id + " questions=" + @($ex.questions).Count)
  $topics = @($ex.questions | ForEach-Object { $_.topic })
  Write-Host ("Topics: " + ($topics -join ", "))
  $withTopic = @($ex.questions | Where-Object { $_.topic }).Count
  Assert-True ($withTopic -eq @($ex.questions).Count) "missing topic fields"
  $answers = @{}
  foreach ($q in $ex.questions) {
    $answers[[string]$q.id] = $q.correct_index
  }
  $attBody = (@{ answers = $answers } | ConvertTo-Json)
  $att = Invoke-RestMethod -Uri ("$Base/api/exercises/" + $ex.id + "/attempts") -Method POST -Headers $script:H -Body $attBody -TimeoutSec 60 -UseBasicParsing
  Write-Host ("Score: " + $att.score + "/" + $att.max_score)
  Assert-True ($att.score -eq $att.max_score) ("score " + $att.score + " != max " + $att.max_score)
  $results["D"] = "PASS"
} catch {
  $results["D"] = "FAIL"
  $failDetails.Add("D: " + $_.Exception.Message)
  Write-Host ("D FAIL: " + $_.Exception.Message)
  if ($_.ErrorDetails) { Write-Host $_.ErrorDetails.Message }
}

Write-Host ""
Write-Host "=== E. Languages ==="
try {
  $gBody = '{"text":"Je suis aller au centre hier."}'
  $gram = Invoke-RestMethod -Uri "$Base/api/languages/grammar" -Method POST -Headers $script:H -Body $gBody -TimeoutSec 180 -UseBasicParsing
  Write-Host ("Grammar corrected: " + $gram.corrected_text)
  Assert-True ($gram.corrected_text) "no corrected_text"

  $cBody = (@{ document_id = $script:docId; question_count = 2 } | ConvertTo-Json)
  $comp = Invoke-RestMethod -Uri "$Base/api/languages/comprehension" -Method POST -Headers $script:H -Body $cBody -TimeoutSec 180 -UseBasicParsing
  $hasQ = @($comp.questions).Count -gt 0
  $hasP = [bool]$comp.passage
  Write-Host ("Comprehension hasQuestions=" + $hasQ + " hasPassage=" + $hasP)
  Assert-True ($hasQ -or $hasP) "no questions or passage"

  $boundary3 = [guid]::NewGuid().ToString()
  $LF = "`r`n"
  $enc = [System.Text.Encoding]::UTF8
  $pronText = "Bonjour, ceci est un test de pronunciation."
  $bodyStr = "--$boundary3$LF" + "Content-Disposition: form-data; name=`"reference_text`"$LF$LF" + "$pronText$LF" + "--$boundary3--$LF"
  $body3 = $enc.GetBytes($bodyStr)
  $resp3 = Invoke-WebRequest -Uri "$Base/api/languages/pronunciation" -Method POST -Headers @{ Authorization = ("Bearer " + $script:token) } -ContentType ("multipart/form-data; boundary=" + $boundary3) -Body $body3 -TimeoutSec 180 -UseBasicParsing
  $pron = $resp3.Content | ConvertFrom-Json
  Write-Host ("Pronunciation: " + ($pron | ConvertTo-Json -Compress -Depth 5))
  Assert-True ($null -ne $pron.accuracy) "accuracy missing"
  Write-Host ("accuracy=" + $pron.accuracy)
  $results["E"] = "PASS"
} catch {
  $results["E"] = "FAIL"
  $failDetails.Add("E: " + $_.Exception.Message)
  Write-Host ("E FAIL: " + $_.Exception.Message)
  if ($_.ErrorDetails) { Write-Host $_.ErrorDetails.Message }
}

Write-Host ""
Write-Host "=== F. Dashboard ==="
try {
  $learner = Invoke-RestMethod -Uri "$Base/api/dashboard/learner" -Method GET -Headers $script:H -TimeoutSec 60 -UseBasicParsing
  $trainer = Invoke-RestMethod -Uri "$Base/api/dashboard/trainer" -Method GET -Headers $script:H -TimeoutSec 60 -UseBasicParsing
  Write-Host ("Learner: " + ($learner | ConvertTo-Json -Compress -Depth 6))
  Write-Host ("Trainer: " + ($trainer | ConvertTo-Json -Compress -Depth 6))
  $idx = $trainer.indexed_documents
  if ($null -eq $idx) { $idx = $learner.indexed_documents }
  $attc = $trainer.attempts_count
  if ($null -eq $attc) { $attc = $learner.attempts_count }
  Write-Host ("indexed_documents=" + $idx + " attempts_count=" + $attc)
  Assert-True ($idx -ge 1) "indexed_documents less than 1"
  Assert-True ($attc -ge 1) "attempts_count less than 1"
  $results["F"] = "PASS"
} catch {
  $results["F"] = "FAIL"
  $failDetails.Add("F: " + $_.Exception.Message)
  Write-Host ("F FAIL: " + $_.Exception.Message)
  if ($_.ErrorDetails) { Write-Host $_.ErrorDetails.Message }
}

Write-Host ""
Write-Host "=== G. Delete safety ==="
try {
  Assert-True ($script:tempDocId) "tempDocId missing"
  $delTemp = Invoke-WebRequest -Uri ("$Base/api/documents/" + $script:tempDocId) -Method DELETE -Headers @{ Authorization = ("Bearer " + $script:token) } -TimeoutSec 60 -UseBasicParsing
  Write-Host ("DELETE temp status=" + $delTemp.StatusCode)
  Assert-True ($delTemp.StatusCode -eq 204) "temp delete not 204"

  $docsAfter = @((Invoke-RestMethod -Uri "$Base/api/documents" -Method GET -Headers $script:H -TimeoutSec 30 -UseBasicParsing))
  $tempGone = -not ($docsAfter | Where-Object { $_.id -eq $script:tempDocId })
  $mainStill = $docsAfter | Where-Object { $_.id -eq $script:docId }
  Assert-True ($tempGone) "temp still present"
  Assert-True ($mainStill) "main doc missing after temp delete"
  Write-Host ("Temp gone, main still present id=" + $script:docId)

  $delMain = Invoke-WebRequest -Uri ("$Base/api/documents/" + $script:docId) -Method DELETE -Headers @{ Authorization = ("Bearer " + $script:token) } -TimeoutSec 60 -UseBasicParsing
  Write-Host ("DELETE main status=" + $delMain.StatusCode)
  Assert-True ($delMain.StatusCode -eq 204) "main delete not 204"

  Assert-True (Test-Path $Sample) "sample missing for re-upload"
  $titleBytes = [byte[]](0x53,0xC3,0xA9,0x63,0x75,0x72,0x69,0x74,0xC3,0xA9,0x20,0x61,0x75,0x20,0x74,0x72,0x61,0x76,0x61,0x69,0x6C)
  $titleFr = [System.Text.Encoding]::UTF8.GetString($titleBytes)
  $up4 = Send-Multipart "$Base/api/documents/upload" $script:token @{ title = $titleFr } "file" $Sample 180
  Write-Host ("Re-upload id=" + $up4.id + " status=" + $up4.status + " title=" + $up4.title)
  Assert-True ($up4.status -eq "indexed") "re-upload not indexed"
  $finalDocs = @((Invoke-RestMethod -Uri "$Base/api/documents" -Method GET -Headers $script:H -TimeoutSec 30 -UseBasicParsing))
  $finalIndexed = @($finalDocs | Where-Object { $_.status -eq "indexed" })
  Assert-True ($finalIndexed.Count -ge 1) "no final indexed doc"
  Write-Host ("Final indexed: " + (($finalIndexed | ForEach-Object { ([string]$_.id) + ":" + $_.title }) -join "; "))
  $results["G"] = "PASS"
} catch {
  $results["G"] = "FAIL"
  $failDetails.Add("G: " + $_.Exception.Message)
  Write-Host ("G FAIL: " + $_.Exception.Message)
  if ($_.ErrorDetails) { Write-Host $_.ErrorDetails.Message }
  try {
    if ($script:token -and (Test-Path $Sample)) {
      $check = @((Invoke-RestMethod -Uri "$Base/api/documents" -Method GET -Headers $script:H -TimeoutSec 30 -UseBasicParsing))
      $left = @($check | Where-Object { $_.status -eq "indexed" })
      if ($left.Count -eq 0) {
        Write-Host "Emergency re-upload..."
        $titleBytes = [byte[]](0x53,0xC3,0xA9,0x63,0x75,0x72,0x69,0x74,0xC3,0xA9,0x20,0x61,0x75,0x20,0x74,0x72,0x61,0x76,0x61,0x69,0x6C)
        $titleFr = [System.Text.Encoding]::UTF8.GetString($titleBytes)
        Send-Multipart "$Base/api/documents/upload" $script:token @{ title = $titleFr } "file" $Sample 180 | Out-Null
      }
    }
  } catch {
    Write-Host ("Emergency upload failed: " + $_.Exception.Message)
  }
}

Write-Host ""
Write-Host "=== H. CSV ==="
try {
  $csvResp = Invoke-WebRequest -Uri "$Base/api/dashboard/trainer/export.csv" -Method GET -Headers @{ Authorization = ("Bearer " + $script:token) } -TimeoutSec 60 -UseBasicParsing
  Write-Host ("CSV status=" + $csvResp.StatusCode)
  Assert-True ($csvResp.StatusCode -eq 200) "CSV status not 200"
  $csvText = [string]$csvResp.Content
  $firstLine = ($csvText -split "`n")[0]
  Write-Host ("CSV header: " + $firstLine)
  Assert-True ($csvText -match "attempt_id") "missing attempt_id header"
  $results["H"] = "PASS"
} catch {
  $results["H"] = "FAIL"
  $failDetails.Add("H: " + $_.Exception.Message)
  Write-Host ("H FAIL: " + $_.Exception.Message)
  if ($_.ErrorDetails) { Write-Host $_.ErrorDetails.Message }
}

Write-Host ""
Write-Host "======== REPORT ========"
foreach ($k in @("A","B","C","D","E","F","G","H")) {
  $v = $results[$k]
  if (-not $v) { $v = "FAIL (not run)" }
  Write-Host ($k + " : " + $v)
}
$failCount = 0
foreach ($k in @("A","B","C","D","E","F","G","H")) {
  if ($results[$k] -ne "PASS") { $failCount++ }
}
if ($failCount -eq 0) {
  Write-Host "OVERALL: ALL PASS"
} else {
  Write-Host "OVERALL: FAILURES"
  foreach ($d in $failDetails) { Write-Host $d }
}
