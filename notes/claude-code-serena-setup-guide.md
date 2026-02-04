# Complete Guide: Installing Claude Code and Serena MCP Server on Ubuntu 25.10

This guide walks you through installing Claude Code, the `uv` package manager, and configuring Serena as an MCP server that automatically starts when Claude Code launches in a project directory.

---

## Table of Contents
1. [Prerequisites](#1-prerequisites)
2. [Install Claude Code](#2-install-claude-code)
3. [Authenticate Claude Code](#3-authenticate-claude-code)
4. [Install the uv Package Manager](#4-install-the-uv-package-manager)
5. [Configure Serena as an MCP Server](#5-configure-serena-as-an-mcp-server)
6. [Validation and Testing](#6-validation-and-testing)
7. [Troubleshooting](#7-troubleshooting)
8. [Configuration Reference](#8-configuration-reference)

---

## 1. Prerequisites

Before starting, ensure your system meets these requirements:

| Requirement | Specification |
|-------------|---------------|
| Operating System | Ubuntu 25.10 (or Ubuntu 20.04+) |
| RAM | 4GB minimum |
| Network | Internet connection required |
| Shell | Bash or Zsh recommended |

### Update Your System

```bash
sudo apt update && sudo apt upgrade -y
```

### Install Essential Dependencies

```bash
sudo apt install -y curl git
```

---

## 2. Install Claude Code

Claude Code offers a **native installer** (recommended) that doesn't require Node.js. This is the preferred installation method.

### Step 2.1: Run the Native Installer

Open your terminal and execute:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

This command downloads and runs the official installer script, which:
- Downloads the Claude Code binary
- Installs it to `~/.local/bin/claude`
- Adds the binary location to your PATH

### Step 2.2: Reload Your Shell Configuration

After installation, reload your shell configuration to update your PATH:

```bash
# For Bash users:
source ~/.bashrc

# For Zsh users:
source ~/.zshrc
```

Alternatively, close and reopen your terminal.

### Step 2.3: Verify the Installation

Run the following commands to confirm Claude Code is installed correctly:

```bash
# Check the version
claude --version

# Run diagnostics
claude doctor
```

The `claude doctor` command checks your installation and reports any issues.

**Expected output**: You should see version information and no critical errors from the diagnostics.

---

## 3. Authenticate Claude Code

Claude Code requires authentication to connect to Anthropic's API.

### Step 3.1: Start Claude Code

Navigate to any directory and launch Claude Code:

```bash
cd ~
claude
```

### Step 3.2: Complete Authentication

On first launch, Claude Code will guide you through authentication. You have several options:

| Authentication Method | Description |
|----------------------|-------------|
| **Claude Console (Default)** | Connect via OAuth with your Anthropic Console account. Requires active billing at console.anthropic.com |
| **Claude Pro/Max Plan** | Use your Claude.ai subscription (includes both web and CLI access) |
| **Enterprise (Bedrock/Vertex)** | Connect via AWS Bedrock or Google Vertex AI |

Follow the on-screen prompts to:
1. Open the authentication URL in your browser
2. Log in to your Anthropic account
3. Authorize Claude Code

### Step 3.3: Verify Authentication

After authentication, test that Claude Code works:

```bash
claude
```

You should see the Claude Code interface ready to accept commands.

Type `/exit` to quit Claude Code for now.

---

## 4. Install the uv Package Manager

Serena requires `uv` (and its `uvx` command) to run. The `uv` package manager is a fast Python package installer written in Rust.

### Step 4.1: Install uv

Run the official installer script:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Step 4.2: Reload Your Shell Configuration

```bash
# For Bash users:
source ~/.bashrc

# For Zsh users:
source ~/.zshrc
```

### Step 4.3: Verify uv Installation

```bash
# Check uv version
uv --version

# Verify uvx is available
uvx --help
```

**Expected output**: Version information for `uv` and help text for `uvx`.

---

## 5. Configure Serena as an MCP Server

Now you'll configure Serena to work with Claude Code. There are two configuration approaches:

| Approach | Use Case |
|----------|----------|
| **Global (User-level)** | Serena available in all projects automatically |
| **Per-Project** | Serena configured for specific projects only |

For your requirement (auto-start when Claude Code launches in a project directory), we'll use the **Global configuration with project-from-cwd**.

### Step 5.1: Add Serena as a Global MCP Server

Run this command to add Serena with user-level scope:

```bash
claude mcp add --scope user serena -- uvx --from git+https://github.com/oraios/serena serena start-mcp-server --context=claude-code --project-from-cwd
```

**What this command does:**
- `claude mcp add`: Adds a new MCP server configuration
- `--scope user`: Makes it available across all projects (stored in `~/.claude.json`)
- `serena`: The name/identifier for this MCP server
- `uvx --from git+https://github.com/oraios/serena`: Uses uvx to run Serena directly from GitHub
- `serena start-mcp-server`: The command to start Serena's MCP server
- `--context=claude-code`: Uses the Claude Code optimized context (disables tools that duplicate Claude Code's built-in capabilities)
- `--project-from-cwd`: Automatically detects and activates the project based on the current working directory

### Step 5.2: Verify the Configuration

Check that Serena was added successfully:

```bash
claude mcp list
```

You should see `serena` listed as a configured MCP server.

### Step 5.3: Understanding the Configuration Files

The configuration is stored in `~/.claude.json`. You can view it with:

```bash
cat ~/.claude.json
```

The structure should include something like:

```json
{
  "mcpServers": {
    "serena": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/oraios/serena",
        "serena",
        "start-mcp-server",
        "--context=claude-code",
        "--project-from-cwd"
      ]
    }
  }
}
```

---

## 6. Validation and Testing

### Step 6.1: Create a Test Project

```bash
mkdir -p ~/test-serena-project
cd ~/test-serena-project
git init  # Serena uses .git to detect project roots
```

### Step 6.2: Start Claude Code

```bash
claude
```

### Step 6.3: Check MCP Server Status

Inside Claude Code, run:

```
/mcp
```

**Expected output**: You should see `serena: connected` (or similar) indicating the MCP server started successfully.

### Step 6.4: Test Serena Tools

Try asking Claude to use Serena's capabilities:

```
List the available Serena tools
```

Or:

```
Use Serena to analyze the current project structure
```

### Step 6.5: Check the Serena Dashboard (Optional)

Serena runs a web dashboard by default. Open your browser to:

```
http://localhost:24282/dashboard/index.html
```

This dashboard shows logs and allows you to monitor Serena's activity.

---

## 7. Troubleshooting

### Problem: `uvx` command not found

**Solution**: Ensure uv is in your PATH:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Problem: Serena fails to start

**Solution 1**: Check if uvx can run Serena manually:

```bash
uvx --from git+https://github.com/oraios/serena serena start-mcp-server --help
```

**Solution 2**: Ensure you have Python 3.8+ installed:

```bash
python3 --version
```

If not installed:

```bash
sudo apt install -y python3 python3-pip
```

### Problem: Claude Code doesn't see Serena

**Solution**: Verify the MCP configuration:

```bash
claude mcp list
claude mcp get serena
```

If Serena is missing, re-add it using the command from Step 5.1.

### Problem: Serena shows as "disconnected"

**Solution 1**: Restart Claude Code completely (exit and restart)

**Solution 2**: Check for port conflicts. Serena uses port 24282 by default. Ensure nothing else is using it:

```bash
lsof -i :24282
```

### Problem: PATH issues with Claude Code

**Solution**: Run Claude's diagnostic:

```bash
claude doctor
```

And follow any recommendations. You may need to add paths manually:

```bash
echo 'export PATH="$HOME/.local/bin:$HOME/.claude/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

---

## 8. Configuration Reference

### Key File Locations

| File | Purpose |
|------|---------|
| `~/.local/bin/claude` | Claude Code binary |
| `~/.claude/settings.json` | Global Claude Code settings |
| `~/.claude.json` | MCP server configurations (user scope) |
| `.mcp.json` (in project) | Project-specific MCP configurations |
| `~/.claude/CLAUDE.md` | Global instructions for Claude Code |

### Alternative: Per-Project Configuration

If you prefer to configure Serena for specific projects only:

```bash
cd /path/to/your/project
claude mcp add serena -- uvx --from git+https://github.com/oraios/serena serena start-mcp-server --context claude-code --project "$(pwd)"
```

This creates a `.mcp.json` file in the project directory.

### Removing Serena

To remove the Serena MCP server configuration:

```bash
# Remove from user scope
claude mcp remove serena

# Or remove from a specific project
cd /path/to/project
claude mcp remove serena
```

### Updating Serena

Serena automatically uses the latest version from GitHub when run with `uvx --from git+https://github.com/oraios/serena`. To force a fresh download:

```bash
uvx cache clean
```

---

## Summary

You have now:

1. ✅ Installed Claude Code using the native installer
2. ✅ Authenticated with your Anthropic account
3. ✅ Installed the `uv` package manager
4. ✅ Configured Serena as a global MCP server
5. ✅ Enabled automatic startup when Claude Code launches in any project directory

Serena will now automatically start whenever you run `claude` in any directory, providing enhanced code analysis and editing capabilities through the Language Server Protocol integration.

---

## Resources

| Resource | URL |
|----------|-----|
| Claude Code Documentation | https://code.claude.com/docs |
| Serena GitHub Repository | https://github.com/oraios/serena |
| Serena User Guide | https://oraios.github.io/serena |
| uv Documentation | https://docs.astral.sh/uv |
| MCP Protocol Specification | https://modelcontextprotocol.io |
