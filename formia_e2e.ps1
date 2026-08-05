$ErrorActionPreference = "Continue"
$base = "http://127.0.0.1:8000"
$script:report = [System.Collections.Generic.List[string]]::new()
$script:failures = [System.Collections.Generic.List[string]]::new()

function Add-Result($step, $pass, $reason) {
  $status = if ($pass) { "PASS" } else { "FAIL" }
  $line = "- Step $step : $status — $reason"
  $script:report.Add($line) | Out-Null
  if (-not $pass) { $script:failures.Add("Step $step") | Out-Null }
  Write-Output $line
}

function Login-Json($email, $password) {
  $body = (@{ email = $email; password = $password } | ConvertTo-Json)
  $tok = Invoke-RestMethod -Uri "$base/api/auth/login/json" -Method POST -Body $body -ContentType "application/json; charset=utf-8" -TimeoutSec 30
  if (-not $tok.access_token) { throw "no access_token" }
  return @{ Authorization = "Bearer $($tok.access_token)" }
}

# Step 0
try {
  $h = Invoke-RestMethod -Uri "$base/api/health" -Method GET -TimeoutSec 30
  Add-Result "0 Health" $true ("ok status=" + $h.status)
} catch {
  Add-Result "0 Health" $false $_.Exception.Message
  Write-Output "API DOWN"
  Write-Output "overall: ALL FAIL (API down)"
  exit 1
}

# Step 1
$hdr = $null
try {
  $hdr = Login-Json "formateur@demo.local" "trainer123"
  try {
    Invoke-WebRequest -Uri "$base/api/chat/conversations" -Method DELETE -Headers $hdr -TimeoutSec 30 | Out-Null
  } catch {
    $code = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 0 }
    if ($code -ne 204) { throw $_ }
  }
  $convs = Invoke-RestMethod -Uri "$base/api/chat/conversations" -Method GET -Headers $hdr -TimeoutSec 30
  $cnt = @($convs).Count
  Add-Result "1 Clear chat" ($cnt -eq 0) ("conversations count=$cnt")
} catch {
  Add-Result "1 Clear chat" $false $_.Exception.Message
}

# Step 2
$docId = $null
$iaOk = $true
try {
  if (-not $hdr) { throw "no trainer token" }
  $docs = Invoke-RestMethod -Uri "$base/api/documents" -Method GET -Headers $hdr -TimeoutSec 30
  $indexed = @($docs | Where-Object { $_.status -eq "indexed" })
  if ($indexed.Count -ge 1) {
    $docId = [string]$indexed[0].id
    Add-Result "2 Documents" $true ("indexed=$($indexed.Count) docId=$docId")
  } else {
    Add-Result "2 Documents" $false "no indexed document — IA tests skipped"
    $iaOk = $false
  }
} catch {
  Add-Result "2 Documents" $false $_.Exception.Message
  $iaOk = $false
}

# Step 3
if ($iaOk -and $hdr -and $docId) {
  try {
    $chatBody = (@{ message = "Quels sont les principes de prevention?"; document_id = $docId } | ConvertTo-Json)
    $chat = Invoke-RestMethod -Uri "$base/api/chat" -Method POST -Headers $hdr -Body $chatBody -ContentType "application/json; charset=utf-8" -TimeoutSec 180
    $ans = [string]$chat.answer
    $cites = @($chat.citations)
    $bad = $ans -match "aucun contenu index"
    $ok = (-not $bad) -and ($cites.Count -ge 1)
    $preview = if ($ans.Length -gt 200) { $ans.Substring(0,200) } else { $ans }
    Write-Output ("CHAT_PREVIEW: " + $preview)
    Write-Output ("CITATIONS: " + $cites.Count)
    Add-Result "3 Chat RAG" $ok ("citations=$($cites.Count); no-index-msg=$(-not $bad)")
  } catch {
    $detail = if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
    Add-Result "3 Chat RAG" $false $detail
  }
} else {
  Add-Result "3 Chat RAG" $false "skipped (no indexed doc or token)"
}

# Step 4
if ($iaOk -and $hdr -and $docId) {
  try {
    $genBody = (@{ document_id = $docId; exercise_type = "qcm"; question_count = 3; title = "QCM E2E" } | ConvertTo-Json)
    $ex = Invoke-RestMethod -Uri "$base/api/exercises/generate" -Method POST -Headers $hdr -Body $genBody -ContentType "application/json; charset=utf-8" -TimeoutSec 180
    $exerciseId = [string]$ex.id
    $qs = @($ex.questions)
    if ($qs.Count -lt 1) { throw "no questions generated" }
    $q0 = $qs[0]
    $qid = [string]$q0.id
    if (-not $qid) { $qid = [string]$q0.question_id }
    $ansIdx = 0
    if ($null -ne $q0.correct_index) { $ansIdx = [int]$q0.correct_index }
    # answers is object map question_id -> answer
    $answersMap = @{}
    $answersMap[$qid] = $ansIdx
    $attemptBody = (@{ answers = $answersMap; duration_seconds = 30 } | ConvertTo-Json -Depth 6)
    Write-Output ("ATTEMPT_BODY: " + $attemptBody)
    $attempt = Invoke-RestMethod -Uri "$base/api/exercises/$exerciseId/attempts" -Method POST -Headers $hdr -Body $attemptBody -ContentType "application/json; charset=utf-8" -TimeoutSec 180
    $score = $attempt.score
    $scoreOk = $null -ne $score -and ($score -is [ValueType] -or "$score" -match '^-?\d')
    Add-Result "4 QCM generate+submit" $scoreOk ("exerciseId=$exerciseId score=$score")
  } catch {
    $detail = if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
    Add-Result "4 QCM generate+submit" $false $detail
  }
} else {
  Add-Result "4 QCM generate+submit" $false "skipped (no indexed doc)"
}

# Step 5
try {
  if (-not $hdr) { throw "no token" }
  $dt = Invoke-RestMethod -Uri "$base/api/dashboard/trainer" -Method GET -Headers $hdr -TimeoutSec 60
  $dl = Invoke-RestMethod -Uri "$base/api/dashboard/learner" -Method GET -Headers $hdr -TimeoutSec 60
  $idx = $dt.indexed_documents
  if ($null -eq $idx) { $idx = $dt.stats.indexed_documents }
  if ($null -eq $idx) { $idx = $dl.indexed_documents }
  $ok5 = ($null -ne $idx) -and ([int]$idx -ge 1)
  Add-Result "5 Dashboards" $ok5 ("indexed_documents=$idx trainer+learner OK")
} catch {
  $detail = if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
  Add-Result "5 Dashboards" $false $detail
}

# Step 6
if ($hdr) {
  $gOk=$false; $cOk=$false; $pOk=$false
  $gReason=""; $cReason=""; $pReason=""
  try {
    $gBody = '{"text":"Je suis aller au centre hier.","language":"fr"}'
    $g = Invoke-RestMethod -Uri "$base/api/languages/grammar" -Method POST -Headers $hdr -Body $gBody -ContentType "application/json; charset=utf-8" -TimeoutSec 180
    $gOk = [bool]$g.corrected_text
    $gReason = "corrected_text present=$gOk val=$($g.corrected_text)"
  } catch { $gReason = $(if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }) }
  if ($iaOk -and $docId) {
    try {
      $cBody = (@{ document_id = $docId; question_count = 2 } | ConvertTo-Json)
      $c = Invoke-RestMethod -Uri "$base/api/languages/comprehension" -Method POST -Headers $hdr -Body $cBody -ContentType "application/json; charset=utf-8" -TimeoutSec 180
      $cOk = (@($c.questions).Count -ge 1) -or [bool]$c.passage
      $cReason = "questions=$(@($c.questions).Count) passage=$([bool]$c.passage)"
    } catch { $cReason = $(if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }) }
  } else { $cReason = "skipped no doc" }
  try {
    $boundary = [guid]::NewGuid().ToString()
    $LF = "`r`n"
    $bodyLines = "--$boundary$LF" + "Content-Disposition: form-data; name=`"reference_text`"$LF$LF" + "Bonjour je m appelle Marie.$LF" + "--$boundary--"
    $bytes = [Text.Encoding]::UTF8.GetBytes($bodyLines)
    $p = Invoke-RestMethod -Uri "$base/api/languages/pronunciation" -Method POST -Headers $hdr -ContentType "multipart/form-data; boundary=$boundary" -Body $bytes -TimeoutSec 180
    $pOk = $null -ne $p.accuracy
    $pReason = "accuracy=$($p.accuracy)"
  } catch { $pReason = $(if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }) }
  Add-Result "6 Languages" ($gOk -and $cOk -and $pOk) ("grammar:$gReason | comp:$cReason | pron:$pReason")
} else {
  Add-Result "6 Languages" $false "no token"
}

# Step 7
try {
  $lHdr = Login-Json "apprenant@demo.local" "learner123"
  $ldocs = Invoke-RestMethod -Uri "$base/api/documents" -Method GET -Headers $lHdr -TimeoutSec 30
  $lex = Invoke-RestMethod -Uri "$base/api/exercises" -Method GET -Headers $lHdr -TimeoutSec 30
  $docsOk = @($ldocs).Count -ge 1
  $chatOk = $false
  $chatReason = ""
  if ($iaOk -and $docId) {
    try {
      $cb = (@{ message = "Resume le document"; document_id = $docId } | ConvertTo-Json)
      $ch = Invoke-RestMethod -Uri "$base/api/chat" -Method POST -Headers $lHdr -Body $cb -ContentType "application/json; charset=utf-8" -TimeoutSec 180
      $chatOk = ([string]$ch.answer) -notmatch "aucun contenu index"
      $chatReason = "chat ok=$chatOk"
    } catch { $chatReason = $(if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }) }
  } else { $chatReason = "chat skipped" }
  $upload403 = $false
  $uploadDetail = ""
  try {
    $boundary = [guid]::NewGuid().ToString()
    $LF = "`r`n"
    $bodyLines = "--$boundary$LF" + "Content-Disposition: form-data; name=`"file`"; filename=`"e2e.txt`"$LF" + "Content-Type: text/plain$LF$LF" + "test e2e$LF" + "--$boundary--"
    $bytes = [Text.Encoding]::UTF8.GetBytes($bodyLines)
    Invoke-WebRequest -Uri "$base/api/documents/upload" -Method POST -Headers $lHdr -ContentType "multipart/form-data; boundary=$boundary" -Body $bytes -TimeoutSec 30 | Out-Null
    $uploadDetail = "upload unexpectedly succeeded"
  } catch {
    $resp = $_.Exception.Response
    $code = if ($resp) { [int]$resp.StatusCode } else { 0 }
    $upload403 = ($code -eq 403)
    $uploadDetail = "status=$code"
    if (-not $upload403 -and $_.ErrorDetails.Message) {
      $upload403 = $_.ErrorDetails.Message -match "403|Forbidden|interdit|permission"
      $uploadDetail = $_.ErrorDetails.Message
    }
  }
  Add-Result "7 Learner role" ($docsOk -and $chatOk -and $upload403) ("docs=$(@($ldocs).Count) exercises=$(@($lex).Count) $chatReason upload403=$upload403 ($uploadDetail)")
} catch {
  $detail = if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
  Add-Result "7 Learner role" $false $detail
}

# Step 8
try {
  $aHdr = Login-Json "admin@demo.local" "admin123"
  $r1 = Invoke-WebRequest -Uri "$base/api/dashboard/trainer" -Method GET -Headers $aHdr -TimeoutSec 60
  $r2 = Invoke-WebRequest -Uri "$base/api/documents" -Method GET -Headers $aHdr -TimeoutSec 30
  $ok8 = ($r1.StatusCode -eq 200) -and ($r2.StatusCode -eq 200)
  Add-Result "8 Admin role" $ok8 ("trainer_dash=$($r1.StatusCode) documents=$($r2.StatusCode)")
} catch {
  $detail = if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
  Add-Result "8 Admin role" $false $detail
}

Write-Output "---- REPORT ----"
$script:report | ForEach-Object { $_ }
if ($script:failures.Count -eq 0) {
  Write-Output "overall: ALL PASS"
} else {
  Write-Output ("overall: FAILURES — " + ($script:failures -join ", "))
}
