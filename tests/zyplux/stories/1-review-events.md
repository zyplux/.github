# 1. [Refreshing bot review gates from GitHub events](1-review-events.test.ts)

## 1.1 authenticating webhook deliveries

### 1.1.1 rejects forged deliveries before contacting GitHub

### 1.1.2 rejects malformed signed events

### 1.1.3 ignores repositories outside the organisation

### 1.1.4 respects the review ruleset exclusions

## 1.2 refreshing the aggregate review gate

### 1.2.1 refreshes thread resolution and reopening

### 1.2.2 refreshes posted and edited reviews

### 1.2.3 refreshes ready pull requests

### 1.2.4 refreshes bot summary edits and explicit review requests

### 1.2.5 refreshes Copilot check activity

### 1.2.6 refreshes a later Copilot workflow start

### 1.2.7 exposes dispatch failures for investigation

### 1.2.8 refreshes removed review requests

### 1.2.9 forwards the webhook head without fetching the pull request

## 1.3 ignoring unrelated activity

### 1.3.1 acknowledges irrelevant events without dispatching

### 1.3.2 exposes health without accepting other routes

### 1.3.3 ignores unrelated checks and workflows
