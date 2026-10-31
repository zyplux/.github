# 2. [Bot reviews](test_2_bot-reviews.py)

## 2.1 bot reviews

### 2.1.1 accepts codex when copilot has not started

### 2.1.2 waits for both current head reviews

### 2.1.3 checks pending reviews once

### 2.1.4 accepts completion on a later event

## 2.2 bot reviews

### 2.2.1 rejects missing or malformed codex evidence

### 2.2.2 rejects a spoofed bot summary

### 2.2.3 requires both codex reviews

### 2.2.4 rechecks a new codex review request after quota denial

### 2.2.5 uses newer review state after a codex quota denial

### 2.2.6 ignores a copilot quota denial for an older head

### 2.2.7 waits for a copilot retry after quota denial

### 2.2.8 observes newer codex summary edits

### 2.2.9 rejects invalid copilot review states

### 2.2.10 rejects a dismissed quota response

### 2.2.11 ignores codex quota denial without current head context

### 2.2.12 recognizes insufficient remaining copilot quota

### 2.2.13 accepts completed codex summary without unresolved finding flag

### 2.2.14 waits for both codex reviews in either completion order

### 2.2.15 fails when either codex review fails

### 2.2.16 requires both codex reviews on the current head
