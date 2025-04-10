# LM Studio Project Manager

A CLI tool for discovering, benchmarking, and managing LM Studio models with RooCode integration.

## Overview

LM Studio Project Manager helps you:

- Discover models available in your LM Studio instance
- Benchmark models against predefined tasks with smart timeout handling
- Save model performance data
- Generate RooCode mode configurations based on model capabilities

## Requirements

- Python 3.8+
- LM Studio running locally (default: http://localhost:1234)
- Rich library (`pip install rich`)
- Requests library (`pip install requests`)

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

## Files

- `main.py`: Main CLI interface
- `lmstudio_model_discovery.py`: Functions for discovering and benchmarking models
- `lmstudio_modelstate.py`: State management functions
- `lmstudio_roomodes.py`: RooCode mode generation

## State Files

- `.modelstate.json`: Stores model information and benchmark results
- `.roomodes`: RooCode configuration file with custom modes based on your models

## Benchmarks

Models are tested against three levels of tasks:

- **Simple**: Basic arithmetic (e.g., "What is 7 * 8?")
- **Moderate**: Simple function creation (e.g., "Write a Python function to square a number")  
- **Complex**: Code refactoring (e.g., "Refactor a loop to use list comprehension")

## Example

```
╭──────── Main Menu ────────╮
│ LM Studio Project Manager │
│ 1. Discover & Benchmark Models │
│ 2. Manual Save Model State (Optional) │
│ 3. Update Roomodes        │
│ 4. Run All Steps          │
│ 5. Exit                   │
╰───────────────────────────╯
```

## Advanced Features

- **Adaptive Prompting**: The system uses one model to improve prompts for another model
- **Performance Profiling**: Models are scored across different complexity levels
- **Custom Instructions**: Generated RooCode modes include performance data and prompt improvement tips
- **Interactive Benchmarking**: After each model is benchmarked, you can decide whether to continue with remaining models (5-second timeout)
- **Automatic State Management**: Model state is automatically saved after each benchmark
- **Smart Timeout Management**: Automatically adjusts request timeouts based on model size:
  - 120 seconds (2 minutes) for large models (7B, 13B, 32B parameters)
  - 60 seconds (1 minute) for medium-sized models
  - 30 seconds for smaller models
- **Detailed Visual Progress**: Rich UI with progress bars, status indicators, and real-time feedback during benchmarking
- **Prompt Optimization Tracking**: Failed prompts are analyzed and improved versions are saved for future use

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