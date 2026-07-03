# 3. [Reporting the Copilot review verdict](test_3_review-verdict.py)

## 3.1 a clean completed review

### 3.1.1 posts the success status when the review is clean

### 3.1.2 links the success status to the copilot run details

## 3.2 an unsuccessful copilot run conclusion

### 3.2.1 blocks with the conclusion without counting threads

## 3.3 unresolved copilot threads

### 3.3.1 blocks the merge while copilot comments stay unresolved

### 3.3.2 counts only unresolved threads authored by copilot

### 3.3.3 fails the job when the threads cannot be queried

### 3.3.4 posts the verdict even when no review matches the head sha

### 3.3.5 posts the verdict even when the review reads keep erroring
