# 1. [Gating on pull request readiness](test_1_pr-readiness.py)

## 1.1 waiting for the pr to leave draft

### 1.1.1 proceeds to the copilot gate once the pr leaves draft

### 1.1.2 leaves no status when the pr never leaves draft

### 1.1.3 fails the job when the draft state is never readable

### 1.1.4 treats a pr read as draft even when later reads error
