# LM Studio Project Manager

A CLI tool for discovering, benchmarking, and managing LM Studio models with RooCode integration.

## Overview

LM Studio Project Manager helps you:

- Discover models available in your LM Studio instance
- Benchmark models against predefined tasks with smart timeout handling
- Save model performance data
- Generate RooCode mode configurations based on model capabilities

## Requirements

- Python 3.10+ (required for latest type hints)
- LM Studio running locally (default: http://localhost:1234)
- Rich library for UI components
- Requests library for API communication

Dependencies can be installed via:
```bash
pip install -r requirements.txt
```

## Installation

1. Clone this repository:
```
git clone https://github.com/yourusername/rooBroker.git
cd rooBroker
```

2. Install dependencies:
```
pip install -r requirements.txt
```

## Usage

Run the main application:

```
python main.py
```

### Main Menu Options

1. **Discover & Benchmark Models**: Connects to your LM Studio instance, discovers available models, and runs benchmarks on selected models.
2. **Manual Save Model State (Optional)**: Explicitly saves the current model state to `.modelstate.json` (note: state is automatically saved during benchmarking).
3. **Update Roomodes**: Generates or updates the `.roomodes` configuration file based on benchmarked models.
4. **Run All Steps**: Execute the complete workflow (discover, benchmark, update).
5. **Exit**: Quit the application.

## Workflow

The typical workflow is:

1. Start LM Studio and load your models
2. Run `python main.py`
3. Select option 1 to discover and benchmark models
4. When prompted, select which models to benchmark (or "all")
5. After each model benchmark, decide whether to continue with the next model (5-second timeout)
6. Select option 3 to update RooCode modes
7. Your models will now be available as modes in RooCode

## Project Structure

The project follows a modular architecture with clear domain separation:

### Core Modules
- `core/benchmarking.py`: Provider-agnostic benchmarking system
- `core/discovery.py`: Model discovery logic
- `core/mode_management.py`: RooCode mode generation and updates
- `core/proxy.py`: Context optimization proxy
- `core/state.py`: State management system

### Interface Layer
- `interfaces/base.py`: Base protocol for model providers
- `interfaces/lmstudio/`: LM Studio specific implementation
- `interfaces/ollama/`: Ollama integration (in development)

### Entry Points
- `main_cli.py`: Command-line interface
- `main_interactive.py`: Interactive menu interface

## State Files

- `.modelstate.json`: Stores model information and benchmark results
- `.roomodes`: RooCode configuration file with custom modes based on your models

## Benchmarking System

Models are evaluated across multiple task types and difficulty levels:

### Task Types
- **Statement Level**: Single line or statement-level code generation
- **Function Level**: Complete function implementation with proper typing
- **Class Level**: Full class implementation with OOP principles
- **Algorithm Level**: Complex algorithm and data structure implementation
- **Context Testing**: Context window utilization evaluation

### Difficulty Levels
- **Basic**: Entry-level tasks requiring fundamental programming knowledge
- **Intermediate**: Tasks requiring good programming practices and type safety
- **Advanced**: Complex tasks requiring expert knowledge and optimization

### Evaluation Metrics
- **Code Quality**:
  - Conciseness and efficiency
  - Readability and maintainability
  - Documentation completeness
  - Type hint compliance (Python 3.11+)
  - Error handling implementation
- **Model Capabilities**:
  - Context window utilization
  - Task completion accuracy
  - Response generation speed
  - Problem-solving approach

## Features

### Comprehensive Model Evaluation
- **Structured Benchmarking**: Models are evaluated across multiple task types and difficulty levels
- **Type Safety Focus**: Validates Python 3.10+ type hint compliance
- **Code Quality Metrics**: Evaluates conciseness, readability, documentation, and error handling
- **Context Window Testing**: Optimizes model performance through context window utilization tests

### Smart Management
- **Provider-Agnostic Design**: Core logic works with multiple model providers (LM Studio, Ollama)
- **State Management**: Automatic state persistence with comprehensive metrics
- **Smart Timeouts**: Dynamic timeout adjustment based on model size and task complexity:
  - 120s for large models (7B+ parameters)
  - 60s for medium models
  - 30s for smaller models

### Interactive UI Options
- **CLI Interface**: Quick command-line operations
- **Rich Interactive Menu**: Full-featured interface with:
  - Real-time progress tracking
  - Detailed performance metrics
  - Visual benchmark results
  - Model comparison tools

### Example Menu

```
╭────────── Main Menu ───────────╮
│ LM Studio Project Manager      │
│ 1. Discover & Benchmark Models │
│ 2. Manual Save Model State     │
│ 3. Update Roomodes             │
│ 4. Run All Steps               │
│ 5. View Benchmark Results      │
│ 6. Launch Context Proxy        │
│ 7. Exit                        │
╰────────────────────────────────╯
```

## Prompt Optimization and RooCode Integration

When a model struggles with a benchmark task, the system:
1. Analyzes the failure using another model
2. Generates an improved prompt
3. Tests the improved prompt
4. Stores successful prompt strategies in the model state
5. Integrates these strategies into the RooCode mode's custom instructions

This means your RooCode modes will contain specific guidance on how to best prompt each model based on its performance characteristics.

## Troubleshooting

- Ensure LM Studio is running and accessible at http://localhost:1234
- If no models are discovered, check the LM Studio API status
- For benchmark failures with larger models, the system will automatically use longer timeouts
- If you encounter "HTTPConnectionPool" errors, try running fewer models at once or increase available resources
- For visual UI issues, make sure the Rich library is correctly installed (`pip install rich`)

# LM Studio Context Optimizer for Roo Code

This utility allows you to maximize context window usage when using LM Studio with Roo Code by providing a transparent proxy that automatically optimizes each request.

## Problem Solved

When Roo Code makes API calls to LM Studio, it doesn't automatically maximize the available context window for each model. This limits the effectiveness of models, especially for complex tasks that require large context.

## Solution

This project provides a transparent HTTP proxy that sits between Roo Code and LM Studio. The proxy:

1. Runs on a different port (default: 1235)
2. Intercepts all API calls to LM Studio
3. Automatically adjusts the `max_tokens` parameter based on each model's actual context window size
4. Forwards the optimized requests to LM Studio
5. Returns responses back to Roo Code

The best part is that you don't need to modify Roo Code at all - you simply point it to the proxy instead of directly to LM Studio.

## Usage

### 1. Start the Context Optimizer Proxy

Run the following command to start the proxy:

```bash
python main.py proxy
```

By default, the proxy runs on port 1235. You can specify a different port:

```bash
python main.py proxy --port 8765
```

You should see output like:

```
Starting LM Studio context optimization proxy...
Updated model context cache with X models
LM Studio Context Optimizer Proxy running on port 1235
Point Roo Code to use http://localhost:1235 instead of http://localhost:1234
```

### 2. Configure Roo Code to Use the Proxy

In your Roo Code configuration:

1. Open Roo Code settings in VS Code
2. Find the LM Studio configuration section
3. Change the API base URL from `http://localhost:1234` to `http://localhost:1235` (or your custom port)
4. Save the settings

### 3. Use Roo Code Normally

Now Roo Code will send all requests through the proxy, which will automatically optimize the context window usage for each model. You don't need to change anything else in your workflow.

## How It Works

The proxy:

1. Caches information about each model's maximum context window size
2. Intercepts chat completion requests
3. Calculates the optimal `max_tokens` parameter (typically reserving 25% of the context window for the response)
4. Modifies the request to use these optimal settings
5. Forwards the request to the actual LM Studio endpoint
6. Returns the unmodified response back to Roo Code

This ensures that each model is used to its maximum capacity without requiring any changes to Roo Code or LM Studio.

## Additional Features

### Discover Models

List all available models in LM Studio along with their context window sizes:

```bash
python main.py discover
```

### Benchmark Models

Run benchmark tests on all available models:

```bash
python main.py benchmark
```

### Update Room Modes

Update the Roo Code `.roomodes` file with model information and benchmarks:

```bash
python main.py update
```

## Notes

- Keep both LM Studio and the proxy running simultaneously
- The proxy needs to be restarted if you change models in LM Studio
- Configuration is cached for 5 minutes, so any model changes will be detected automatically after that time

# Custom Modes in RooCode

Roo Code allows you to create custom modes to tailor Roo's behavior to specific tasks or workflows. Custom modes can be either global (available across all projects) or project-specific (defined within a single project). Each mode—including custom ones—remembers the last model you used with it, automatically selecting that model when you switch to the mode. This lets you maintain different preferred models for different types of tasks without manual reconfiguration.

## Mode-Specific Instruction File Locations

You can provide instructions for custom modes using dedicated files or directories within your workspace. This allows for better organization and version control compared to only using the JSON `customInstructions` property.

**Preferred Method: Directory (`.roo/rules-{mode-slug}/`)**

```
.
├── .roo/
│   └── rules-docs-writer/  # Example for mode slug "docs-writer"
│       ├── 01-style-guide.md
│       └── 02-formatting.txt
└── ... (other project files)
```

**Fallback Method: Single File (`.roorules-{mode-slug}`)**

```
.
├── .roorules-docs-writer  # Example for mode slug "docs-writer"
└── ... (other project files)
```

The directory method takes precedence if it exists and contains files. See *Mode-Specific Instructions via Files/Directories* for details.

## Why Use Custom Modes?

- **Specialization:** Create modes optimized for specific tasks, like "Documentation Writer," "Test Engineer," or "Refactoring Expert"
- **Safety:** Restrict a mode's access to sensitive files or commands. For example, a "Review Mode" could be limited to read-only operations
- **Experimentation:** Safely experiment with different prompts and configurations without affecting other modes
- **Team Collaboration:** Share custom modes with your team to standardize workflows

## Overview of Custom Modes Interface

Roo Code's interface for creating and managing custom modes.

### What's Included in a Custom Mode?

Custom modes allow you to define:

- **A unique name and slug:** For easy identification
- **A role definition:** Placed at the beginning of the system prompt, this defines Roo's core expertise and personality for the mode. This placement is crucial as it shapes Roo's fundamental understanding and approach to tasks
- **Custom instructions:** Added near the end of the system prompt, these provide specific guidelines that modify or refine Roo's behavior for the mode. You can define these using the `customInstructions` JSON property, and/or by adding instruction files to a dedicated directory (see below). The preferred method for file-based instructions is now using a `.roo/rules-{mode-slug}/` directory, which allows for better organization and takes precedence over the older `.roorules-{mode-slug}` file method. This structured placement allows for more nuanced control over Roo's responses.
- **Allowed tools:** Which Roo Code tools the mode can use (e.g., read files, write files, execute commands)
- **File restrictions:** (Optional) Limit file access to specific file types or patterns (e.g., only allow editing `.md` files)

## Custom Mode Configuration (JSON Format)

Both global and project-specific configurations use the same JSON format. Each configuration file contains a `customModes` array of mode definitions:

```json
{
  "customModes": [
    {
      "slug": "mode-name",
      "name": "Mode Display Name",
      "roleDefinition": "Mode's role and capabilities",
      "groups": ["read", "edit"],
      "customInstructions": "Additional guidelines"
    }
  ]
}
```

### Required Properties

- **slug**
  - A unique identifier for the mode
  - Use lowercase letters, numbers, and hyphens
  - Keep it short and descriptive
  - Example: `"docs-writer"`, `"test-engineer"`
- **name**
  - The display name shown in the UI
  - Can include spaces and proper capitalization
  - Example: `"Documentation Writer"`, `"Test Engineer"`
- **roleDefinition**
  - Detailed description of the mode's role and capabilities
  - Defines Roo's expertise and personality for this mode
  - Example: `"You are a technical writer specializing in clear documentation"`
- **groups**
  - Array of allowed tool groups
  - Available groups: `"read"`, `"edit"`, `"browser"`, `"command"`, `"mcp"`
  - Can include file restrictions for the `"edit"` group

#### File Restrictions Format

```json
["edit", {
  "fileRegex": "\\.md$",
  "description": "Markdown files only"
}]
```

#### Understanding File Restrictions

The `fileRegex` property uses regular expressions to control which files a mode can edit:

- `\.md$` - Match files ending in ".md"
- `\.(test|spec)\.(js|ts)$` - Match test files (e.g., "component.test.js")
- `\.(js|ts)$` - Match JavaScript and TypeScript files

**Common regex patterns:**

- `\.` - Match a literal dot
- `(a|b)` - Match either "a" or "b"
- `$` - Match the end of the filename

## Optional Properties

- **customInstructions**
  - Additional behavioral guidelines for the mode
  - Example: `"Focus on explaining concepts and providing examples"`
- **apiConfiguration**
  - Optional settings to customize the AI model and parameters for this mode
  - Allows optimizing the model selection for specific tasks
  - Example: `{ "model": "gpt-4", "temperature": 0.2 }`

## Mode-Specific Instructions via Files/Directories

In addition to the `customInstructions` property in JSON, you can provide mode-specific instructions via files in your workspace. This is particularly useful for:

- Organizing lengthy or complex instructions into multiple, manageable files.
- Managing instructions easily with version control.
- Allowing non-technical team members to modify instructions without editing JSON.

There are two ways Roo Code loads these instructions, with a clear preference for the newer directory-based method:

### 1. Preferred Method: Directory-Based Instructions (`.roo/rules-{mode-slug}/`)

- **Structure:** Create a directory named `.roo/rules-{mode-slug}/` in your workspace root. Replace `{mode-slug}` with your mode's slug (e.g., `.roo/rules-docs-writer/`).
- **Content:** Place one or more files (e.g., `.md`, `.txt`) containing your instructions inside this directory. You can organize instructions further using subdirectories; Roo Code reads files recursively, appending their content to the system prompt in alphabetical order based on filename.
- **Loading:** All instruction files found within this directory structure will be loaded and applied to the specified mode.

### 2. Fallback (Backward Compatibility): File-Based Instructions (`.roorules-{mode-slug}`)

- **Structure:** If the `.roo/rules-{mode-slug}/` directory does not exist or is empty, Roo Code will look for a single file named `.roorules-{mode-slug}` in your workspace root (e.g., `.roorules-docs-writer`).
- **Loading:** If found, the content of this single file will be loaded as instructions for the mode.

**Precedence:**

The directory-based method (`.roo/rules-{mode-slug}/`) takes precedence. If this directory exists and contains files, any corresponding root-level `.roorules-{mode-slug}` file will be ignored for that mode.

This ensures that projects migrated to the new directory structure behave predictably, while older projects using the single-file method remain compatible.

**Combining with JSON `customInstructions`:**

Instructions loaded from either the directory or the fallback file are combined with the `customInstructions` property defined in the mode's JSON configuration. Typically, the content from the files/directories is appended after the content from the JSON `customInstructions` property.

## Configuration Precedence

Mode configurations are applied in this order:

1. Project-level mode configurations (from `.roomodes`)
2. Global mode configurations (from `custom_modes.json`)
3. Default mode configurations

This means that project-specific configurations will override global configurations, which in turn override default configurations.

> **Note on Instruction Files:** Within the loading of mode-specific instructions from the filesystem, the directory `.roo/rules-{mode-slug}/` takes precedence over the single file `.roorules-{mode-slug}` found in the workspace root.

## Creating Custom Modes

You have three options for creating custom modes:

### 1. Ask Roo! (Recommended)

You can quickly create a basic custom mode by asking Roo Code to do it for you. For example:

> Create a new mode called "Documentation Writer". It should only be able to read files and write Markdown files.

Roo Code will guide you through the process. However, for fine-tuning modes or making specific adjustments, you'll want to use the Prompts tab or manual configuration methods described below.

**Custom Mode Creation Settings**

When enabled, Roo allows you to create custom modes using prompts like 'Make me a custom mode that...'. Disabling this reduces your system prompt by about 700 tokens when this feature isn't needed. When disabled you can still manually create custom modes using the + button above or by editing the related config JSON.

- **Enable Custom Mode Creation Through Prompts setting:**
  - You can find this setting within the prompt settings by clicking the ⚙️ icon in the Roo Code top menu bar.

### 2. Using the Prompts Tab

- **Open Prompts Tab:** Click the ⚙️ icon in the Roo Code top menu bar
- **Create New Mode:** Click the ➕ button to the right of the Modes heading
- **Fill in Fields:**
  - Name: Enter a display name for the mode
  - Slug: Enter a lowercase identifier (letters, numbers, and hyphens only)
  - Save Location: Choose Global (via `custom_modes.json`, available across all workspaces) or Project-specific (via `.roomodes` file in project root)
  - Role Definition: Define Roo's expertise and personality for this mode (appears at the start of the system prompt)
  - Available Tools: Select which tools this mode can use
  - Custom Instructions: (Optional) Add behavioral guidelines specific to this mode (appears at the end of the system prompt)
- **Create Mode:** Click the "Create Mode" button to save your new mode

> **Note:** File type restrictions can only be added through manual configuration.

### 3. Manual Configuration

You can configure custom modes by editing JSON files through the Prompts tab:

- Both global and project-specific configurations can be edited through the Prompts tab:
  - **Open Prompts Tab:** Click the ⚙️ icon in the Roo Code top menu bar
  - **Access Settings Menu:** Click the ⋮ button to the right of the Modes heading
  - **Choose Configuration:**
    - Select "Edit Global Modes" to edit `custom_modes.json` (available across all workspaces)
    - Select "Edit Project Modes" to edit `.roomodes` file (in project root)
  - **Edit Configuration:** Modify the JSON file that opens
  - **Save Changes:** Roo Code will automatically detect the changes

## Example Configurations

Each example shows different aspects of mode configuration:

**Basic Documentation Writer**

```json
{
  "customModes": [{
    "slug": "docs-writer",
    "name": "Documentation Writer",
    "roleDefinition": "You are a technical writer specializing in clear documentation",
    "groups": [
      "read",
      ["edit", { "fileRegex": "\\.md$", "description": "Markdown files only" }]
    ],
    "customInstructions": "Focus on clear explanations and examples"
  }]
}
```

**Test Engineer with File Restrictions**

```json
{
  "customModes": [{
    "slug": "test-engineer",
    "name": "Test Engineer",
    "roleDefinition": "You are a test engineer focused on code quality",
    "groups": [
      "read",
      ["edit", { "fileRegex": "\.(test|spec)\.(js|ts)$", "description": "Test files only" }]
    ]
  }]
}
```

**Project-Specific Mode Override**

```json
{
  "customModes": [{
    "slug": "code",
    "name": "Code (Project-Specific)",
    "roleDefinition": "You are a software engineer with project-specific constraints",
    "groups": [
      "read",
      ["edit", { "fileRegex": "\.(js|ts)$", "description": "JS/TS files only" }]
    ],
    "customInstructions": "Focus on project-specific JS/TS development"
  }]
}
```

By following these instructions, you can create and manage custom modes to enhance your workflow with Roo-Code.

## Understanding Regex in Custom Modes

Regex patterns in custom modes let you precisely control which files Roo can edit:

### Basic Syntax

When you specify `fileRegex` in a custom mode, you're creating a pattern that file paths must match:

```json
["edit", { "fileRegex": "\\.md$", "description": "Markdown files only" }]
```

#### Important Rules

- **Double Backslashes:** In JSON, backslashes must be escaped with another backslash. So `.md$` becomes `\.md$`
- **Path Matching:** Patterns match against the full file path, not just the filename
- **Case Sensitivity:** Regex patterns are case-sensitive by default

### Common Pattern Examples

| Pattern | Matches | Doesn't Match |
|---------|---------|--------------|
| `\.md$` | readme.md, docs/guide.md | script.js, readme.md.bak |
| `^src/.*` | src/app.js, src/components/button.tsx | lib/utils.js, test/src/mock.js |
| `\.(css|scss)$` | styles.css, theme.scss | styles.less, styles.css.map |
| `docs/.*\.md$` | docs/guide.md, docs/api/reference.md | guide.md, src/docs/notes.md |
| `^(?!.*(test|spec)).*\.js$` | app.js, utils.js | app.test.js, utils.spec.js |

#### Pattern Building Blocks

- `\.` - Match a literal dot (period)
- `$` - Match the end of the string
- `^` - Match the beginning of the string
- `.*` - Match any character (except newline) zero or more times
- `(a|b)` - Match either "a" or "b"
- `(?!...)` - Negative lookahead (exclude matches)

### Testing Your Patterns

- Test it on sample file paths to ensure it matches what you expect
- Remember that in JSON, each backslash needs to be doubled (`\d` becomes `\\d`)
- Start with simpler patterns and build complexity gradually

> **Tip:**
> Let Roo Build Your Regex Patterns
>
> Instead of writing complex regex patterns manually, you can ask Roo to create them for you! Simply describe which files you want to include or exclude:
>
> Create a regex pattern that matches JavaScript files but excludes test files
>
> Roo will generate the appropriate pattern with proper escaping for JSON configuration.

## Creating Benchmark Tasks

Benchmarks are defined in JSON files placed in the `benchmarks/` directory. You can organize benchmarks into subdirectories (e.g., `benchmarks/python/`, `benchmarks/sql/`).

### Benchmark JSON Structure

Each benchmark file must conform to the schema defined in `roo_types/benchmark_schemas.py::BenchmarkTask`. Below are the main fields:

- **`id`** (string, required): Unique identifier for the benchmark.
- **`name`** (string, required): Human-readable name of the benchmark.
- **`type`** (string, required): Task type. Supported values:
  - `statement`
  - `function`
  - `class`
  - `algorithm`
  - `context`
- **`difficulty`** (string, required): Difficulty level. Supported values:
  - `basic`
  - `intermediate`
  - `advanced`
- **`prompt`** (string, required): The user prompt for the task.
- **`system_prompt`** (string, optional): The system message to set the context/role for the model.
- **`evaluation_method`** (string, required): Method to evaluate the model's response.
- **`test_cases`** (list, required): List of test cases for evaluation.
- **`temperature`** (float, optional): Sampling temperature for the model.
- **`tags`** (list of strings, optional): Tags for categorizing the benchmark.

### Evaluation Methods and Test Case Structure

Each `evaluation_method` requires a specific structure for the `test_cases` field:

1.  **`string_contains`**:
    *   Checks if the `expected` string is present in the model's response. Useful for simple QA or keyword checks.
    *   Example:
        ```json
        [{"expected": "Expected Phrase"}]
        ```
2.  **`exec_check_state`**:
    *   Executes the generated code snippet and checks if specified variables in the final state match the `expected` dictionary.
    *   Example:
        ```json
        [{"input": {"x": 5}, "expected": {"x": 10, "y": 5}}]
        ```
3.  **`exec_call_func`**:
    *   Executes code defining a function, calls the function with `input` arguments, and checks if the return value matches `expected`.
    *   Example:
        ```json
        [{"input": {"n": 5}, "expected": 25}]
        ```
4.  **`eval_expression`**:
    *   Executes the generated code and checks if a resulting variable (determined during evaluation) matches the `expected` value. Useful for list comprehensions or simple assignments.
    *   Example:
        ```json
        [{"expected": [0, 4, 16, 36, 64]}]
        ```
5.  **`class_eval`**:
    *   Executes code defining a class, instantiates it, runs a `sequence` of method calls, and checks if the result of the final call matches `expected`.
    *   Example:
        ```json
        [{"sequence": ["push(1)", "pop()"], "expected": 1}]
        ```

### Validation

New benchmark files must conform to the schema. Use `load_benchmarks_from_directory` in `core/benchmarking.py` to validate benchmarks. Refer to existing files in the `benchmarks/` directory for examples.
