---
name: create-pr
description: Create a branch, commit changes, and open a pull request
disable-model-invocation: true
context: fork
agent: git-worker
allowed-tools: Bash
---

# Create PR Workflow

When invoked, delegate the following git operations to the git-worker subagent:

1. **Create a feature branch** from the current branch
2. **Commit all staged changes** with a descriptive message
3. **Push the branch** to the remote repository
4. **Create a pull request** using the GitHub CLI or git platform API

The subagent will handle all git operations independently and report back with:
- Branch name created
- Commit hash
- PR URL

Do not perform these operations yourself—always delegate to the git-worker subagent.