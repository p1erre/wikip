# CLI Design Document

## Overview

This document explains the design decisions for the video-to-book CLI system.

## Two-Phase Approach

### Phase 1: Runner CLI (✅ Implemented)
**File**: `src/cli/runner.py`

**Purpose**: Simple tool/agent runner for testing and automation

**Design Decisions**:

1. **Minimal Dependencies**
   - Uses only Python stdlib (argparse)
   - No heavy UI libraries
   - Fast startup time
   - **Why**: Keep it lightweight for scripting and CI/CD

2. **Argparse over Click/Typer**
   - **Considered**: Click (popular), Typer (modern), argparse (stdlib)
   - **Chose**: argparse
   - **Why**: 
     - No external dependencies
     - Sufficient for our needs
     - Everyone knows it
     - Future-proof (stdlib)

3. **Subcommand Structure**
   ```
   vtb
   ├── tools          # Individual tool testing
   │   ├── extract-id
   │   ├── get-metadata
   │   ├── get-transcript
   │   └── download
   └── agent          # Complete workflows
       └── analyze
   ```
   - **Why**: Clear separation of concerns
   - Tools = atomic operations
   - Agents = complex workflows

4. **JSON Output Flag**
   - `--json` on each command
   - **Why**: Scriptability
   - Enables piping to jq, use in CI/CD
   - Machine-readable output

5. **Exit Codes**
   - 0 = success
   - 1 = error
   - **Why**: Unix conventions, script-friendly

### Phase 2: Interactive CLI (🚧 Planned)
**File**: `src/cli/interactive.py`

**Purpose**: Claude Code-style conversational interface

**Planned Design**:

1. **Rich Terminal UI**
   - Dependencies: rich, prompt_toolkit, textual (TBD)
   - **Why**: Better UX for exploration
   - Streaming responses
   - Syntax highlighting
   - Interactive prompts

2. **Conversational Flow**
   ```
   You: Analyze this video
   Agent: [streams response]
   You: Save that to a file
   Agent: [executes, confirms]
   ```
   - **Why**: Natural interaction
   - Lower barrier to entry
   - Better for learning

3. **Session Management**
   - Save/restore conversations
   - Command history
   - Context awareness
   - **Why**: Resume work, learn from history

4. **Advanced Features**
   - File operations
   - Code execution (sandboxed)
   - Multi-turn reasoning
   - **Why**: Full agent capabilities

## Why Separate CLIs?

### Comparison

| Aspect | Runner | Interactive |
|--------|--------|-------------|
| **Dependencies** | Minimal | Heavy |
| **Startup** | Instant | Slower |
| **Use Case** | Testing/Scripts | Exploration |
| **Output** | Text/JSON | Rich/Streaming |
| **Learning Curve** | Low | Medium |
| **Automation** | Excellent | Poor |
| **UX** | Basic | Excellent |

### Decision Rationale

**Separate is better because**:

1. **Different Dependencies**
   - Runner: No deps beyond stdlib
   - Interactive: rich, prompt_toolkit, etc.
   - Don't force heavy deps on scripters

2. **Different Use Cases**
   - Runner: CI/CD, scripts, quick tests
   - Interactive: Learning, exploration, complex workflows
   - Each optimized for its purpose

3. **Maintenance**
   - Can update independently
   - Clear boundaries
   - Easier to test

4. **Migration Path**
   - Start with runner (simple)
   - Graduate to interactive (advanced)
   - Both can coexist

## Implementation Details

### Runner CLI Architecture

```python
# Entry point
main()
  ↓
create_parser()  # Build argparse structure
  ↓
args.func(args)  # Call appropriate command function
  ↓
cmd_extract_id() / cmd_get_metadata() / etc.
  ↓
tool.invoke()    # Call actual tool
  ↓
print_result()   # Format output (text or JSON)
```

### Key Functions

**print_result()**
- Handles both text and JSON output
- Consistent formatting
- Error highlighting

**cmd_* functions**
- One per tool/agent
- Thin wrappers around actual implementations
- Handle argument extraction
- Return exit codes

**create_parser()**
- Builds entire command structure
- Uses subparsers for hierarchy
- Adds help text
- Sets up argument validation

### Wrapper Script

**File**: `vtb`

```python
#!/usr/bin/env python3
if sys.argv[1] == "chat":
    from src.cli.interactive import main
else:
    from src.cli.runner import main
```

**Why**:
- Convenience
- Single entry point
- Route to appropriate CLI
- Can add more modes later

## Future Enhancements

### Runner CLI

1. **Config File Support**
   ```bash
   vtb --config my-config.yaml tools extract-id <url>
   ```

2. **Batch Mode**
   ```bash
   vtb tools extract-id --batch urls.txt
   ```

3. **Output Formats**
   ```bash
   vtb tools get-metadata abc --format yaml
   ```

4. **Verbose Mode**
   ```bash
   vtb -v tools download abc  # Show progress
   ```

### Interactive CLI

1. **Streaming Implementation**
   ```python
   async for chunk in agent.stream(message):
       console.print(chunk)
   ```

2. **Rich Console**
   ```python
   from rich.console import Console
   from rich.markdown import Markdown
   
   console = Console()
   console.print(Markdown(response))
   ```

3. **Prompt Toolkit**
   ```python
   from prompt_toolkit import PromptSession
   
   session = PromptSession()
   user_input = await session.prompt_async("You: ")
   ```

4. **Session Persistence**
   ```python
   # Save conversation
   session.save("conversation.json")
   
   # Restore later
   session = Session.load("conversation.json")
   ```

## Testing Strategy

### Runner CLI

```python
# Unit tests
def test_cmd_extract_id():
    args = Namespace(url="...", json=False)
    result = cmd_extract_id(args)
    assert result == 0

# Integration tests
def test_cli_extract_id():
    result = subprocess.run([
        "python", "-m", "src.cli.runner",
        "tools", "extract-id", "https://..."
    ])
    assert result.returncode == 0
```

### Interactive CLI

```python
# Mock user input
@patch('prompt_toolkit.PromptSession.prompt_async')
async def test_conversation(mock_prompt):
    mock_prompt.return_value = "Analyze video X"
    # Test conversation flow
```

## Documentation

### User Documentation
- **CLI_GUIDE.md**: Complete user guide
- Examples for each command
- Troubleshooting
- Tips & tricks

### Developer Documentation
- **This file**: Design decisions
- Code comments: Implementation details
- Docstrings: API documentation

## Lessons Learned

### What Worked Well

1. **Argparse for runner**
   - Simple, no dependencies
   - Good enough for our needs
   - Easy to test

2. **Separate CLIs**
   - Clear separation of concerns
   - Each optimized for its use case
   - No compromises

3. **JSON output**
   - Extremely useful for scripting
   - Easy to implement
   - Users love it

### What We'd Do Differently

1. **Could use Click**
   - Better help formatting
   - Easier nested commands
   - But adds dependency

2. **Could combine CLIs**
   - Single entry point
   - Modes instead of separate files
   - But more complex

## Conclusion

The two-CLI approach provides:
- ✅ Simple tool for testing (runner)
- ✅ Future-ready for rich UX (interactive)
- ✅ No compromises on either
- ✅ Clear migration path

**Current status**: Runner CLI complete and tested
**Next step**: Implement interactive CLI when needed
