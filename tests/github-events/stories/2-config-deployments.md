# 2. [Deploying Worker config from validated GitHub events](2-config-deployments.test.ts)

## 2.1 dispatching Worker config updates

### 2.1.1 selects the environment from its configured repository

### 2.1.2 skips updates when the workers directory is unchanged

### 2.1.3 handles an initial push without a previous tree

## 2.2 restricting deployment authority

### 2.2.1 ignores unsuccessful CI and unconfigured sources

### 2.2.2 ignores repositories absent from the environment selectors

### 2.2.3 refuses an ambiguous environment selector
