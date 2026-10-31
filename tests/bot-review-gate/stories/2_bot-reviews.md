# 2. [Bot reviews](test_2_bot-reviews.py)

## 2.1 bot reviews

### 2.1.1 accepts codex when copilot has not started

### 2.1.2 waits for both current head reviews

### 2.1.3 accepts reviews within thirty minutes

### 2.1.4 keeps timed out reviews pending

## 2.2 bot reviews

### 2.2.1 rejects missing or malformed codex evidence

### 2.2.2 rejects a spoofed bot summary

### 2.2.3 requires code review instead of security review

### 2.2.4 rechecks a new codex review request after quota denial

### 2.2.5 uses newer review state after a codex quota denial

### 2.2.6 ignores a copilot quota denial for an older head

### 2.2.7 waits for a copilot retry after quota denial

### 2.2.8 observes newer codex summary edits

### 2.2.9 rejects invalid copilot review states

### 2.2.10 rejects a dismissed quota response

### 2.2.11 ignores codex quota denial without current head context

### 2.2.12 recognizes insufficient remaining copilot quota
