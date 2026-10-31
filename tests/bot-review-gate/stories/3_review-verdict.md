# 3. [Review verdict](test_3_review-verdict.py)

## 3.1 review verdict

### 3.1.1 requires clean reviews from every participating bot

### 3.1.2 links success to the review evidence

### 3.1.3 ignores earlier reviews when the other bot passes

### 3.1.4 invalidates success when a second review starts

## 3.2 review verdict

### 3.2.1 blocks unresolved findings from either bot

### 3.2.2 counts only unresolved bot threads

### 3.2.3 observes thread resolution on the next event

### 3.2.4 paginates review threads before passing

### 3.2.5 accepts resolved findings in the codex summary

### 3.2.6 quota denial does not erase known codex findings

### 3.2.7 accepts a clean current head review after resolving older findings

### 3.2.8 invalidates success when a second review finds issues

### 3.2.9 blocks security findings without summary finding flags

## 3.3 review verdict

### 3.3.1 codex failures do not count as unavailability
